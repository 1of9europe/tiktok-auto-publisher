from typing import Dict, List, Optional
import requests
from datetime import datetime
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class YouTubeAPI:
    """Classe pour gérer les appels à l'API YouTube Data v3"""
    
    BASE_URL = "https://www.googleapis.com/youtube/v3"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def search_videos(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Recherche des vidéos YouTube avec les paramètres spécifiés
        
        Args:
            query: Mots-clés de recherche
            max_results: Nombre maximum de résultats (max 50)
            
        Returns:
            Liste des vidéos trouvées avec leurs métadonnées de base
        """
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
            
            if 'items' not in data:
                logger.warning(f"Aucune vidéo trouvée pour la recherche: {query}")
                return []
                
            return data['items']
            
        except requests.exceptions.RequestException as e:
            if response.status_code == 403:
                logger.error("Quota YouTube API dépassé ou clé API invalide")
            else:
                logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
            return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        Récupère les détails complets pour une liste de vidéos
        
        Args:
            video_ids: Liste des IDs YouTube
            
        Returns:
            Liste des détails des vidéos
        """
        try:
            # YouTube API limite à 50 vidéos par appel
            video_ids = video_ids[:50]
            
            params = {
                'part': 'snippet,contentDetails,statistics',
                'id': ','.join(video_ids),
                'key': self.api_key
            }
            
            response = self.session.get(f"{self.BASE_URL}/videos", params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'items' not in data:
                logger.warning(f"Aucun détail trouvé pour les vidéos: {video_ids}")
                return []
                
            return data['items']
            
        except requests.exceptions.RequestException as e:
            if response.status_code == 403:
                logger.error("Quota YouTube API dépassé ou clé API invalide")
            else:
                logger.error(f"Erreur lors de la récupération des détails: {str(e)}")
            return []
    
    def parse_duration(self, duration: str) -> float:
        """Convertit la durée ISO 8601 en secondes"""
        # Exemple: "PT1H2M10S" -> 3730 secondes
        import re
        
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
            
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def format_video_data(self, video: Dict) -> Dict:
        """Formate les données d'une vidéo pour le ContentCollector"""
        return {
            'id': video['id'],
            'title': video['snippet']['title'],
            'description': video['snippet']['description'],
            'thumbnail': video['snippet']['thumbnails']['high']['url'],
            'duration': self.parse_duration(video['contentDetails']['duration']),
            'views': int(video['statistics'].get('viewCount', 0)),
            'published_at': video['snippet']['publishedAt'],
            'channel_title': video['snippet']['channelTitle']
        } 