import os
import shutil
import socket
import subprocess
import time
from urllib.parse import urlparse
import pysrt
from openai import OpenAI
from auto_anki.config import CONFIG

def _endpoint_is_available(base_url, timeout=1.0):
    parsed = urlparse(base_url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _ensure_local_ai(base_url):
    """Inicia o OmniRoute local quando o endpoint configurado estiver offline."""
    if _endpoint_is_available(base_url):
        return

    parsed = urlparse(base_url)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(f"O serviço de IA não está acessível em {base_url}.")

    command = shutil.which("omniroute.cmd") or shutil.which("omniroute")
    if not command:
        raise RuntimeError(
            "O OmniRoute está desligado e o comando 'omniroute' não foi encontrado. "
            "Instale ou inicie o OmniRoute antes de processar."
        )

    port = parsed.port or 20128
    print("IA local desligada. Iniciando OmniRoute...")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if os.name == "nt" and command.lower().endswith((".cmd", ".bat")):
        args = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command]
    else:
        args = [command]
    args.extend(["serve", "--daemon", "--no-open", "--no-tray", "--port", str(port)])

    try:
        result = subprocess.run(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creation_flags, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"Não foi possível iniciar o OmniRoute: {e}") from e

    if result.returncode != 0:
        raise RuntimeError("O OmniRoute não pôde ser iniciado automaticamente.")

    for _ in range(30):
        if _endpoint_is_available(base_url):
            print("OmniRoute iniciado e pronto para traduzir.")
            return
        time.sleep(1)
    raise RuntimeError("O OmniRoute foi iniciado, mas não ficou disponível em até 30 segundos.")

def translate_srt(srt_path, work_dir):
    if not srt_path or not os.path.exists(srt_path):
        raise FileNotFoundError(f"Arquivo de legendas não encontrado: {srt_path}")
    
    print("Traduzindo legendas com IA local (Omniroute)...")
    _ensure_local_ai(CONFIG['translation']['base_url'])
    subs = pysrt.open(srt_path, encoding='utf-8')
    
    if len(subs) == 0:
        print("Aviso: Arquivo de legendas vazio. Verifique a transcrição.")
        # Retornar o arquivo original sem tradução para não crashar
        translated_srt = os.path.join(work_dir, "translated.srt")
        subs.save(translated_srt, encoding='utf-8')
        return translated_srt
    
    try:
        client = OpenAI(
            base_url=CONFIG['translation']['base_url'],
            api_key=CONFIG['translation']['api_key']
        )
        model = CONFIG['translation']['model']
    except Exception as e:
        raise RuntimeError(f"Erro ao configurar cliente de tradução: {e}") from e
    
    for i, sub in enumerate(subs, 1):
        last_error = None
        for attempt in range(1, 4):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a highly accurate translator. The source is English. Translate it to Brazilian Portuguese (pt-BR). Output ONLY the translated text, without formatting, quotes, explanations, or the English original."},
                        {"role": "user", "content": sub.text}
                    ],
                    temperature=0.1
                )
                translated_text = response.choices[0].message.content.strip()
                if not translated_text:
                    raise ValueError("A IA retornou uma tradução vazia.")
                sub.text = translated_text
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f"\nFalha ao traduzir linha {i} (tentativa {attempt}/3): {e}")

        if last_error is not None:
            raise RuntimeError(
                f"Não foi possível traduzir a linha {i}. O processo foi interrompido para não criar cards com legendas incorretas."
            ) from last_error
        print(f"Traduzida linha {i}/{len(subs)}", end="\r")

    print()
    translated_srt = os.path.join(work_dir, "translated.srt")
    subs.save(translated_srt, encoding='utf-8')
    print(f"Tradução concluída: {translated_srt}")
    return translated_srt
