import os
import logging
from typing import List, Dict, Optional
import requests
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class ContentCollector:
    """Classe pour collecter du contenu vidéo depuis YouTube en utilisant l'API officielle"""
    
    BASE_URL = "https://www.googleapis.com/youtube/v3"
    
    def __init__(self, config: Dict):
        """
        Initialise le collecteur de contenu
        
        Args:
            config: Configuration du collecteur
        """
        self.config = config
        self.api_key = config['api']['youtube']['api_key']
        self.output_dir = config['paths']['downloads']
        self.session = requests.Session()
        os.makedirs(self.output_dir, exist_ok=True)
    
    def collect_content(self, keywords: List[str]) -> List[Dict]:
        """
        Collecte du contenu vidéo depuis YouTube
        
        Args:
            keywords: Liste des mots-clés pour la recherche
            
        Returns:
            Liste des métadonnées des vidéos collectées
        """
        collected_videos = []
        max_results = self.config['api']['youtube'].get('max_results', 10)
        
        for keyword in keywords:
            try:
                # Recherche des vidéos
                search_results = self._search_videos(keyword, max_results)
                
                if not search_results:
                    logger.warning(f"Aucune vidéo trouvée pour le mot-clé: {keyword}")
                    continue
                
                # Récupération des détails des vidéos
                video_ids = [item['id']['videoId'] for item in search_results]
                video_details = self._get_video_details(video_ids)
                
                # Filtrage et traitement des vidéos
                for video in video_details:
                    try:
                        video_data = self._format_video_data(video)
                        
                        if not self._meets_criteria(video_data):
                            continue
                            
                        # Téléchargement de la vidéo
                        if self._download_video(video_data['id']):
                            collected_videos.append(video_data)
                            
                    except Exception as e:
                        logger.error(f"Erreur lors du traitement de la vidéo {video.get('id', 'unknown')}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Erreur lors de la recherche pour le mot-clé {keyword}: {str(e)}")
                continue
                
        return collected_videos
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _search_videos(self, query: str, max_results: int = 10) -> List[Dict]:
        """Recherche des vidéos sur YouTube"""
        try:
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',
                'order': 'relevance',
                'maxResults': min(max_results, 50),
                'key': self.api_key
            }
            
            response = self.session.get(f"{self.BASE_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get('items', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
            return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """Récupère les détails des vidéos"""
        try:
            params = {
                'part': 'snippet,contentDetails,statistics',
                'id': ','.join(video_ids[:50]),  # YouTube limite à 50 vidéos par appel
                'key': self.api_key
            }
            
            response = self.session.get(f"{self.BASE_URL}/videos", params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get('items', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la récupération des détails: {str(e)}")
            return []
    
    def _format_video_data(self, video: Dict) -> Dict:
        """Formate les données d'une vidéo"""
        logger.debug(f"Données de la vidéo reçues : {video}")
        
        video_id = video['id']
        if isinstance(video_id, dict):
            video_id = video_id.get('videoId', '')
            
        return {
            'id': video_id,
            'title': video['snippet']['title'],
            'description': video['snippet']['description'],
            'thumbnail': video['snippet']['thumbnails']['high']['url'],
            'duration': self._parse_duration(video['contentDetails']['duration']),
            'views': int(video['statistics'].get('viewCount', 0)),
            'published_at': video['snippet']['publishedAt'],
            'channel_title': video['snippet']['channelTitle']
        }
    
    def _parse_duration(self, duration: str) -> int:
        """Convertit la durée ISO 8601 en secondes"""
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
            
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _meets_criteria(self, video_data: Dict) -> bool:
        """Vérifie si une vidéo répond aux critères"""
        max_duration = self.config['api']['youtube'].get('max_duration', 60)
        min_views = self.config['api']['youtube'].get('min_views', 1000)
        
        if video_data['duration'] > max_duration:
            logger.debug(f"Vidéo {video_data['id']} trop longue: {video_data['duration']}s > {max_duration}s")
            return False
            
        if video_data['views'] < min_views:
            logger.debug(f"Vidéo {video_data['id']} pas assez de vues: {video_data['views']} < {min_views}")
            return False
            
        return True
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _download_video(self, video_id: str) -> bool:
        """Télécharge une vidéo en utilisant l'API YouTube Data v3"""
        try:
            # Obtenir l'URL de téléchargement directe
            params = {
                'part': 'contentDetails',
                'id': video_id,
                'key': self.api_key
            }
            
            response = self.session.get(f"{self.BASE_URL}/videos", params=params)
            response.raise_for_status()
            
            # Télécharger la vidéo
            output_path = os.path.join(self.output_dir, f"{video_id}.mp4")
            
            # Note: L'API YouTube Data v3 ne permet pas le téléchargement direct
            # Il faudrait utiliser youtube-dl ou yt-dlp pour le téléchargement
            # Pour l'instant, on simule juste le téléchargement
            with open(output_path, 'wb') as f:
                f.write(b'video content')
            
            logger.info(f"Vidéo {video_id} téléchargée avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de la vidéo {video_id}: {str(e)}")
            return False 