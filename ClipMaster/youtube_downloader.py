import logging
from pathlib import Path
import yt_dlp

class YouTubeDownloader:
    """Classe pour télécharger les vidéos YouTube."""
    
    def __init__(self):
        """Initialise le downloader YouTube."""
        self.logger = logging.getLogger(__name__)
        
    def download(self, video_url: str) -> Path:
        """
        Télécharge une vidéo YouTube avec yt-dlp.
        
        Args:
            video_url (str): URL de la vidéo YouTube
            
        Returns:
            Path: Chemin du fichier téléchargé
        """
        try:
            output_path = Path('downloads')
            output_path.mkdir(parents=True, exist_ok=True)
            
            ydl_opts = {
                'format': 'best[ext=mp4]',
                'outtmpl': str(output_path / '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_path = Path(ydl.prepare_filename(info))
                
            self.logger.info(f"Vidéo téléchargée: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.error(f"Erreur lors du téléchargement: {str(e)}")
            raise
