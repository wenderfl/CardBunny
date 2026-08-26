import re
import json
import unicodedata
from openai import OpenAI
from auto_anki.anki_client import invoke_anki
from auto_anki.config import CONFIG

# Descrição de cada slot para a IA entender o que deve encontrar
SLOT_DESCRIPTIONS = {
    "audio":               "Campo que armazena o ARQUIVO DE ÁUDIO (mp3) da cena — usado para reproduzir som no card.",
    "clip":                "Campo que armazena o ARQUIVO DE VÍDEO (webm) da cena — usado para reproduzir o clipe no card.",
    "snapshot":            "Campo que armazena a IMAGEM (jpg/png) do frame da cena — usado como thumbnail/foto.",
    "english_subtitle":    "Campo que armazena o TEXTO/FRASE em INGLÊS da cena — frente do card ou expressão original.",
    "portuguese_subtitle": "Campo que armazena a TRADUÇÃO em PORTUGUÊS (pt-br) da cena — verso do card ou significado.",
    "index":               "Campo que armazena um IDENTIFICADOR ÚNICO do card (pode conter o nome do arquivo de vídeo).",
}

def normalize_string(s):
    """Remove acentos, caracteres especiais e deixa minúsculo."""
    if not s:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def _map_fields_with_ai(fields):
    """
    Usa a IA local (Omniroute) para mapear os campos do modelo Anki aos slots internos.
    Retorna um dict {slot: field_name} ou None em caso de falha.
    """
    try:
        client = OpenAI(
            base_url=CONFIG['translation']['base_url'],
            api_key=CONFIG['translation']['api_key']
        )
        model = CONFIG['translation']['model']

        # Construir o prompt com os nomes dos campos e as descrições dos slots
        slots_desc = "\n".join([f'  - "{slot}": {desc}' for slot, desc in SLOT_DESCRIPTIONS.items()])
        fields_list = "\n".join([f'  - "{f}"' for f in fields])

        prompt = f"""Você é um assistente especialista em Anki. Abaixo estão os campos de um modelo de card do Anki:

CAMPOS DISPONÍVEIS:
{fields_list}

SLOTS INTERNOS (que preciso preencher):
{slots_desc}

TAREFA: Analise semanticamente os nomes dos campos e mapeie cada CAMPO para o SLOT mais adequado.
- Cada slot deve receber no máximo UM campo.
- Slots que não tiverem um campo compatível devem ter valor null.
- Retorne APENAS um objeto JSON válido, sem explicações, sem markdown, sem blocos de código.

Formato de saída esperado:
{{"audio": "Nome do Campo", "clip": "Nome do Campo", "snapshot": "Nome do Campo", "english_subtitle": "Nome do Campo", "portuguese_subtitle": "Nome do Campo", "index": "Nome do Campo ou null"}}"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Você é um assistente técnico especializado em Anki. Responda APENAS com JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0  # Determinístico para mapeamento
        )

        raw = response.choices[0].message.content.strip()
        # Limpar possível markdown residual
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()

        result = json.loads(raw)

        # Validar que as chaves esperadas estão presentes
        expected_slots = set(SLOT_DESCRIPTIONS.keys())
        if not expected_slots.issubset(result.keys()):
            print("Aviso: resposta da IA incompleta, tentando fallback heurístico.")
            return None

        # Converter "null" string para None
        for k, v in result.items():
            if v == "null" or v == "" or (v not in fields and v is not None):
                result[k] = None

        return result

    except json.JSONDecodeError as e:
        print(f"Aviso: IA retornou JSON inválido ({e}). Tentando fallback heurístico.")
        return None
    except Exception as e:
        print(f"Aviso: IA indisponível para mapeamento de campos ({e}). Tentando fallback heurístico.")
        return None

def _map_fields_heuristic(fields):
    """
    Fallback: mapeia campos por palavras-chave quando a IA não está disponível.
    """
    mapping = {
        'audio': None,
        'clip': None,
        'snapshot': None,
        'english_subtitle': None,
        'portuguese_subtitle': None,
        'index': None
    }

    keywords = {
        'audio':               ['audio', 'som', 'sound', 'mp3'],
        'clip':                ['clip', 'video', 'media', 'webm'],
        'snapshot':            ['img', 'imag', 'picture', 'pic', 'foto', 'snapshot', 'screen'],
        'english_subtitle':    ['frase', 'expression', 'english', 'ingles', 'front', 'frente', 'texto', 'legenda'],
        'portuguese_subtitle': ['trad', 'meaning', 'portugues', 'back', 'verso', 'significado'],
        'index':               ['index', 'id', 'ordem'],
    }

    for original_field in fields:
        norm_field = normalize_string(original_field)
        for cat, kws in keywords.items():
            if mapping[cat] is None:
                for kw in kws:
                    if kw in norm_field:
                        mapping[cat] = original_field
                        break

    return mapping

def map_fields(model_name):
    """
    Mapeia os campos do modelo Anki aos slots internos do sistema.
    
    Slots internos e sua formatação final no card:
      - audio:               [sound:vid_...mp3]   (áudio mp3 com tag [sound:])
      - clip:                vid_...webm           (vídeo webm, apenas o nome do arquivo)
      - snapshot:            <img src="vid_...jpg"> (imagem do frame)
      - english_subtitle:    texto em inglês
      - portuguese_subtitle: texto em português
      - index:               [sound:vid_...webm]  (vídeo webm com tag [sound:])
    """
    print("Obtendo campos do modelo Anki...")
    fields = invoke_anki('modelFieldNames', modelName=model_name)
    if not fields:
        print(f"Erro: Não foi possível obter os campos do modelo '{model_name}'.")
        return {}

    print(f"Campos encontrados: {fields}")
    print("Mapeando campos com IA local (Omniroute)...")

    mapping = _map_fields_with_ai(fields)

    if mapping:
        print(f"Mapeamento via IA concluído: {mapping}")
    else:
        print("Usando mapeamento heurístico como fallback...")
        mapping = _map_fields_heuristic(fields)
        print(f"Mapeamento heurístico concluído: {mapping}")

    # Exibir resultado final de forma legível
    print("─── Mapeamento de Campos ───")
    for slot, field in mapping.items():
        status = f"→ \"{field}\"" if field else "→ [não encontrado]"
        print(f"  {slot:20s} {status}")
    print("───────────────────────────")

    return mapping

