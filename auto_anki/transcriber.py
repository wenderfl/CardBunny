import os
import datetime
from faster_whisper import WhisperModel
from auto_anki.config import CONFIG

def transcribe_video(video_path, work_dir):
    print("Iniciando transcrição local com Whisper...")
    print("Carregando cérebro da Inteligência Artificial... (Aguarde, pode demorar alguns minutos na primeira execução caso precise baixar o modelo)")

    if not video_path or not os.path.exists(video_path):
        raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")

    model_size = CONFIG['whisper']['model_size']
    device = CONFIG['whisper']['device']
    compute_type = CONFIG['whisper']['compute_type']
    cpu_threads = CONFIG['whisper'].get('cpu_threads', 4)
    
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type, cpu_threads=cpu_threads)
    except Exception as e:
        raise RuntimeError(f"Falha ao carregar o modelo Whisper '{model_size}': {e}")
    
    try:
        segments, info = model.transcribe(video_path, beam_size=5)
    except Exception as e:
        raise RuntimeError(f"Falha durante a transcrição do vídeo: {e}")
    
    srt_path = os.path.join(work_dir, "original.srt")
    try:
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
    except Exception as e:
        raise RuntimeError(f"Falha ao salvar o arquivo de legendas: {e}")
    
    print(f"Transcrição concluída: {srt_path}")
    return srt_path

def format_timestamp(seconds):
    td = datetime.timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds_int = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

