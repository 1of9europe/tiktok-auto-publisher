import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict
import time

class TrendHunter:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('TrendHunter')
        
    def find_trends(self) -> List[Dict]:
        """
        Détecte les tendances actuelles sur TikTok et autres plateformes.
        Returns:
            List[Dict]: Liste des tendances avec leurs métadonnées
        """
        try:
            trends = []
            
            # Récupération des tendances TikTok
            tiktok_trends = self._get_tiktok_trends()
            trends.extend(tiktok_trends)
            
            # Récupération des tendances Reddit
            reddit_trends = self._get_reddit_trends()
            trends.extend(reddit_trends)
            
            # Sauvegarde des tendances
            self._save_trends(trends)
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la détection des tendances: {str(e)}")
            raise
            
    def _get_tiktok_trends(self) -> List[Dict]:
        """
        Récupère les tendances de TikTok via web scraping
        """
        try:
            trends = []
            url = "https://www.tiktok.com/discover"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Note: Cette partie devra être adaptée en fonction de la structure HTML de TikTok
            trending_tags = soup.find_all('div', {'class': 'trending-tag'})
            
            for tag in trending_tags:
                trend = {
                    'platform': 'tiktok',
                    'type': 'hashtag',
                    'name': tag.text.strip(),
                    'timestamp': datetime.now().isoformat(),
                    'metadata': {}
                }
                trends.append(trend)
                
            return trends
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances TikTok: {str(e)}")
            return []
            
    def _get_reddit_trends(self) -> List[Dict]:
        """
        Récupère les tendances de Reddit
        """
        try:
            trends = []
            url = "https://www.reddit.com/r/trending.json"
            headers = {
                'User-Agent': 'TikTokAutoBot/1.0'
            }
            
            response = requests.get(url, headers=headers)
            data = response.json()
            
            for trend in data.get('data', {}).get('children', []):
                trend_data = trend.get('data', {})
                trend = {
                    'platform': 'reddit',
                    'type': 'topic',
                    'name': trend_data.get('title', ''),
                    'timestamp': datetime.now().isoformat(),
                    'metadata': {
                        'url': trend_data.get('url', ''),
                        'score': trend_data.get('score', 0)
                    }
                }
                trends.append(trend)
                
            return trends
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances Reddit: {str(e)}")
            return []
            
    def _save_trends(self, trends: List[Dict]):
        """
        Sauvegarde les tendances dans un fichier JSON
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(__file__).parent / 'data'
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / f'trends_{timestamp}.json'
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(trends, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Tendances sauvegardées dans {output_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des tendances: {str(e)}")
            raise 