import os
import re
import glob
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

def is_valid_youtube_url(url):
    """Valida se a URL parece ser do YouTube antes de tentar baixar."""
    pattern = re.compile(
        r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+'
    )
    return bool(pattern.search(url))

def download_video(url, output_dir):
    # Limpar URL (remover espaços, newlines e URLs duplicadas)
    url = url.strip()
    
    # Detectar e corrigir URLs duplicadas coladas (ex: https://...https://...)
    if url.count('http') > 1:
        # Pegar apenas a primeira URL
        match = re.search(r'https?://[^\s]+', url)
        if match:
            url = match.group(0)
            print(f"URL duplicada detectada. Usando: {url}")
    
    if not is_valid_youtube_url(url):
        print(f"Erro: A URL fornecida não parece ser do YouTube: '{url}'")
        return None
    
    print(f"Baixando vídeo de {url}...")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best',
        'outtmpl': os.path.join(output_dir, 'video.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            if not info_dict:
                print("Erro: yt-dlp não retornou informações do vídeo.")
                return None
            
            # Resgate à prova de falhas: pega qualquer arquivo "video.*" que não seja temporário
            video_files = [f for f in glob.glob(os.path.join(output_dir, "video.*")) if not f.endswith('.part') and not f.endswith('.ytdl')]
            
            if video_files:
                return video_files[0]
            print("Erro: Arquivo de vídeo não encontrado após o download.")
            return None
            
    except DownloadError as e:
        msg = str(e)
        if "Private video" in msg:
            print("Erro: Este vídeo é privado e não pode ser baixado.")
        elif "Video unavailable" in msg or "unavailable" in msg.lower():
            print("Erro: Este vídeo não está disponível (pode ter sido removido).")
        elif "HTTP Error 429" in msg:
            print("Erro: Muitas requisições ao YouTube. Aguarde alguns minutos e tente novamente.")
        else:
            print(f"Erro ao baixar o vídeo: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado no download: {e}")
        return None

