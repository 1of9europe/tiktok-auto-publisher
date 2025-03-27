from pytube import YouTube, Search
import logging
from pathlib import Path
from typing import List, Dict
import json
import os
from datetime import datetime

class ContentCollector:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        self.downloads_dir = Path(self.config['paths']['downloads'])
        self.downloads_dir.mkdir(exist_ok=True)
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('ContentCollector')
        
    def collect_content(self, keywords: str) -> List[Dict]:
        """
        Recherche et télécharge des vidéos YouTube basées sur les mots-clés.
        Args:
            keywords (str): Mots-clés de recherche
        Returns:
            List[Dict]: Liste des vidéos téléchargées avec leurs métadonnées
        """
        try:
            self.logger.info(f"Recherche de vidéos pour: {keywords}")
            search = Search(keywords)
            
            videos = []
            for result in search.results[:self.config['api']['youtube']['max_results']]:
                try:
                    if result.views < self.config['api']['youtube']['min_views']:
                        continue
                        
                    video_data = self._process_video(result)
                    if video_data:
                        videos.append(video_data)
                        
                except Exception as e:
                    self.logger.error(f"Erreur lors du traitement de la vidéo {result.video_id}: {str(e)}")
                    continue
                    
            self._save_metadata(videos)
            return videos
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la collecte de contenu: {str(e)}")
            raise
            
    def _process_video(self, video: YouTube) -> Dict:
        """
        Traite et télécharge une vidéo YouTube
        """
        try:
            # Vérification de la durée
            if video.length > self.config['video_settings']['max_duration']:
                self.logger.info(f"Vidéo {video.video_id} trop longue, ignorée")
                return None
                
            # Préparation du nom de fichier
            safe_title = "".join(c for c in video.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_{video.video_id}.mp4"
            output_path = self.downloads_dir / filename
            
            # Téléchargement de la meilleure qualité compatible
            stream = video.streams.filter(
                progressive=True,
                file_extension='mp4'
            ).order_by('resolution').desc().first()
            
            if not stream:
                self.logger.warning(f"Aucun stream compatible trouvé pour {video.video_id}")
                return None
                
            # Téléchargement
            stream.download(output_path=str(self.downloads_dir), filename=filename)
            
            # Création des métadonnées
            video_data = {
                'id': video.video_id,
                'title': video.title,
                'author': video.author,
                'length': video.length,
                'views': video.views,
                'local_path': str(output_path),
                'download_date': datetime.now().isoformat(),
                'keywords': video.keywords if video.keywords else [],
                'description': video.description,
                'thumbnail_url': video.thumbnail_url
            }
            
            self.logger.info(f"Vidéo téléchargée avec succès: {filename}")
            return video_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de la vidéo {video.video_id}: {str(e)}")
            return None
            
    def _save_metadata(self, videos: List[Dict]):
        """
        Sauvegarde les métadonnées des vidéos téléchargées
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            metadata_dir = self.downloads_dir / 'metadata'
            metadata_dir.mkdir(exist_ok=True)
            
            metadata_file = metadata_dir / f'videos_{timestamp}.json'
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(videos, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Métadonnées sauvegardées dans {metadata_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des métadonnées: {str(e)}")
            raise 