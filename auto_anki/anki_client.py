import requests
from auto_anki.config import CONFIG

def invoke_anki(action, **params):
    request = {'action': action, 'version': 6, 'params': params}
    try:
        http_response = requests.post(CONFIG['anki']['url'], json=request, timeout=30)
        http_response.raise_for_status()
        response = http_response.json()
        if len(response) != 2:
            raise Exception('Response has an unexpected number of fields')
        if 'error' not in response:
            raise Exception('Response is missing required error field')
        if 'result' not in response:
            raise Exception('Response is missing required result field')
        if response['error'] is not None:
            raise Exception(response['error'])
        return response['result']
    except Exception as e:
        print(f"Erro ao comunicar com AnkiConnect: {e}")
        print(">>> AVISO: CERTIFIQUE-SE DE QUE O ANKI ESTÁ ABERTO! <<<")
        return None
