import re
import json
import unicodedata
from openai import OpenAI
from cardbunny.anki_client import invoke_anki
from cardbunny.config import CONFIG

# Description of each slot for the AI to understand what it should find
SLOT_DESCRIPTIONS = {
    "audio":               "Field that stores the AUDIO FILE (mp3) of the scene — used to play sound in the card.",
    "clip":                "Field that stores the VIDEO FILE (mp4) of the scene — used to play the clip in the card.",
    "snapshot":            "Field that stores the IMAGE (jpg/png) of the scene frame — used as thumbnail/photo.",
    "english_subtitle":    "Field that stores the ORIGINAL TEXT/PHRASE (source language) of the scene — front of the card.",
    "portuguese_subtitle": "Field that stores the TRANSLATION (target language) of the scene — back of the card or meaning.",
    "index":               "Field that stores a UNIQUE IDENTIFIER of the card (may contain the video filename).",
}

def normalize_string(s):
    """Removes accents, special characters and makes it lowercase."""
    if not s:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def _map_fields_with_ai(fields):
    """
    Uses local AI (Omniroute) to map Anki model fields to internal slots.
    Returns a dict {slot: field_name} or None on failure.
    """
    try:
        client = OpenAI(
            base_url=CONFIG['translation']['base_url'],
            api_key=CONFIG['translation']['api_key']
        )
        model = CONFIG['translation']['model']

        # Build the prompt with field names and slot descriptions
        slots_desc = "\n".join([f'  - "{slot}": {desc}' for slot, desc in SLOT_DESCRIPTIONS.items()])
        fields_list = "\n".join([f'  - "{f}"' for f in fields])

        prompt = f"""You are an Anki expert assistant. Below are the fields of an Anki card model:

AVAILABLE FIELDS:
{fields_list}

INTERNAL SLOTS (that I need to fill):
{slots_desc}

TASK: Semantically analyze the field names and map each FIELD to the most suitable SLOT.
- Each slot must receive at most ONE field.
- Slots without a compatible field must have a null value.
- Return ONLY a valid JSON object, without explanations, without markdown, without code blocks.

Expected output format:
{{"audio": "Field Name", "clip": "Field Name", "snapshot": "Field Name", "english_subtitle": "Field Name", "portuguese_subtitle": "Field Name", "index": "Field Name or null"}}"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a technical assistant specialized in Anki. Reply ONLY with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0  # Deterministic for mapping
        )

        raw = response.choices[0].message.content.strip()
        # Clean possible residual markdown
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
        raw = raw.strip()

        result = json.loads(raw)

        # Validate that the expected keys are present
        expected_slots = set(SLOT_DESCRIPTIONS.keys())
        if not expected_slots.issubset(result.keys()):
            print("Warning: AI response incomplete, trying heuristic fallback.")
            return None

        # Convert "null" string to None
        for k, v in result.items():
            if v == "null" or v == "" or (v not in fields and v is not None):
                result[k] = None

        return result

    except json.JSONDecodeError as e:
        print(f"Warning: AI returned invalid JSON ({e}). Trying heuristic fallback.")
        return None
    except Exception as e:
        print(f"Warning: AI unavailable for field mapping ({e}). Trying heuristic fallback.")
        return None

def _map_fields_heuristic(fields):
    """
    Fallback: maps fields by keywords when AI is unavailable.
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
        'clip':                ['clip', 'video', 'media', 'mp4'],
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
    Maps the Anki model fields to the internal system slots.
    
    Internal slots and their final formatting in the card:
      - audio:               [sound:vid_...mp3]   (mp3 audio with [sound:] tag)
      - clip:                vid_...mp4           (mp4 video, only the filename)
      - snapshot:            <img src="vid_...jpg"> (frame image)
      - english_subtitle:    original text
      - portuguese_subtitle: translated text
      - index:               [sound:vid_...mp4]  (mp4 video with [sound:] tag)
    """
    print("Getting Anki model fields...")
    fields = invoke_anki('modelFieldNames', modelName=model_name)
    if not fields:
        print(f"Error: Could not get fields for model '{model_name}'.")
        return {}

    print(f"Found fields: {fields}")
    print("Mapping fields with local AI (Omniroute)...")

    mapping = _map_fields_with_ai(fields)

    if mapping:
        print(f"Mapping via AI completed: {mapping}")
    else:
        print("Using heuristic mapping as fallback...")
        mapping = _map_fields_heuristic(fields)
        print(f"Heuristic mapping completed: {mapping}")

    # Display final result in a readable format
    print("─── Field Mapping ───")
    for slot, field in mapping.items():
        status = f"→ \"{field}\"" if field else "→ [not found]"
        print(f"  {slot:20s} {status}")
    print("───────────────────────────")

    return mapping
