import os
import pysrt
from openai import OpenAI
from auto_anki.config import CONFIG

def translate_srt(srt_path, work_dir):
    if not srt_path or not os.path.exists(srt_path):
        raise FileNotFoundError(f"Arquivo de legendas não encontrado: {srt_path}")
    
    print("Traduzindo legendas com IA local (Omniroute)...")
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
        print(f"Erro ao configurar cliente de IA: {e}")
        print("Usando legendas originais como fallback.")
        translated_srt = os.path.join(work_dir, "translated.srt")
        subs.save(translated_srt, encoding='utf-8')
        return translated_srt
    
    consecutive_errors = 0
    for i, sub in enumerate(subs, 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a highly accurate translator. Translate the following text to Brazilian Portuguese (pt-br). Output ONLY the translation, without any formatting, quotes, or additional text."},
                    {"role": "user", "content": sub.text}
                ],
                temperature=0.3
            )
            sub.text = response.choices[0].message.content.strip()
            consecutive_errors = 0
            print(f"Traduzida linha {i}/{len(subs)}", end="\r")
        except Exception as e:
            print(f"\nErro ao traduzir a linha {i}: {e}")
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("\nMuitos erros consecutivos de conexão com a IA local. Mantendo legendas originais para as linhas restantes.")
                break

    print()
    translated_srt = os.path.join(work_dir, "translated.srt")
    subs.save(translated_srt, encoding='utf-8')
    print(f"Tradução concluída: {translated_srt}")
    return translated_srt

