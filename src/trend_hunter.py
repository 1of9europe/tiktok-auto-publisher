import requests
import json
import logging
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

class TrendHunter:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def get_tiktok_trends(self):
        """Récupère les tendances de TikTok"""
        try:
            response = requests.get("https://www.tiktok.com/explore")
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                trends = []
                for tag in soup.find_all('div', class_='trending-tag'):
                    trends.append({
                        "tag": tag.find('a').text,
                        "views": self._parse_views(tag.find('span', class_='view-count').text)
                    })
                return trends
            return []
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances TikTok: {e}")
            return []
            
    def get_reddit_trends(self):
        """Récupère les tendances de Reddit"""
        try:
            response = requests.get(
                "https://www.reddit.com/r/all/top.json",
                headers={"User-Agent": "TrendHunter/1.0"}
            )
            if response.status_code == 200:
                data = response.json()
                topics = []
                for post in data['data']['children']:
                    post_data = post['data']
                    topics.append({
                        "topic": post_data['title'],
                        "upvotes": post_data['score'],
                        "comments": post_data['num_comments']
                    })
                return topics
            return []
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances Reddit: {e}")
            return []
            
    def find_trends(self):
        """Trouve les tendances sur différentes plateformes"""
        trends = {
            "tiktok": self.get_tiktok_trends(),
            "reddit": self.get_reddit_trends()
        }
        return trends
        
    def save_trends(self, trends, output_path):
        """Sauvegarde les tendances dans un fichier JSON"""
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(trends, f, indent=2)
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des tendances: {e}")
            
    def _parse_views(self, view_text):
        """Convertit le texte des vues en nombre"""
        try:
            number = float(view_text.split()[0].replace('M', '000000').replace('K', '000'))
            return int(number)
        except:
            return 0 