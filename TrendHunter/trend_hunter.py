import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import time
import pickle
from tenacity import retry, stop_after_attempt, wait_exponential
from .models import Trend, TrendMetadata

class TrendHunter:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        self.cache_dir = Path(__file__).parent / 'cache'
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_duration = 3600  # 1 heure en secondes
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('TrendHunter')
        
    def find_trends(self) -> List[Trend]:
        """
        Détecte les tendances actuelles sur TikTok et autres plateformes.
        Returns:
            List[Trend]: Liste des tendances avec leurs métadonnées
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _fetch_raw_trend_data(self, source: str = 'tiktok') -> Optional[Dict]:
        """
        Récupère les données brutes des tendances depuis l'API
        """
        start_time = time.time()
        self.logger.info(f"Début de la récupération des tendances depuis {source}")
        
        try:
            if source == 'tiktok':
                url = "https://www.tiktok.com/api/discover/trending"
                headers = {
                    **self.config['api']['tiktok']['headers'],
                    'Accept': 'application/json',
                    'Cookie': 'tt_webid_v2=1234567890'
                }
            else:
                raise ValueError(f"Source non supportée: {source}")
                
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Récupération terminée en {elapsed_time:.2f}s")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erreur lors de la requête API: {str(e)}")
            raise
            
    def _parse_trend_data(self, raw_data: Dict, source: str = 'tiktok') -> List[Dict]:
        """
        Parse les données brutes en format structuré
        """
        self.logger.info("Début du parsing des données")
        trends_data = []
        
        try:
            if source == 'tiktok':
                trending_items = raw_data.get('body', {}).get('challenge_list', [])
                
                for item in trending_items:
                    trend_data = {
                        'name': item.get('title', '').strip(),
                        'views': self._parse_views(item.get('stats', {}).get('view_count', 0)),
                        'videos': item.get('stats', {}).get('video_count', 0),
                        'description': item.get('description', ''),
                        'category': self._detect_category(item.get('title', ''))
                    }
                    trends_data.append(trend_data)
                    
            self.logger.info(f"Parsing terminé: {len(trends_data)} tendances extraites")
            return trends_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors du parsing: {str(e)}")
            return []
            
    def _transform_to_trend_objects(self, trends_data: List[Dict], source: str) -> List[Trend]:
        """
        Transforme les données parsées en objets Trend
        """
        self.logger.info("Début de la transformation en objets Trend")
        trends = []
        
        for data in trends_data:
            try:
                trend = Trend(
                    platform=source,
                    type='hashtag',
                    name=data['name'],
                    timestamp=datetime.now(),
                    metadata=TrendMetadata(
                        views=data['views'],
                        videos=data['videos'],
                        description=data['description'],
                        category=data['category']
                    )
                )
                trends.append(trend)
            except Exception as e:
                self.logger.warning(f"Erreur lors de la transformation d'une tendance: {str(e)}")
                continue
                
        self.logger.info(f"Transformation terminée: {len(trends)} objets Trend créés")
        return trends
        
    def _get_tiktok_trends(self) -> List[Trend]:
        """
        Récupère les tendances de TikTok avec gestion du cache et retry
        """
        # Vérifier le cache
        cached_trends = self._get_cached_trends('tiktok')
        if cached_trends:
            self.logger.info("Utilisation des tendances en cache")
            return cached_trends
            
        try:
            # Récupération des données
            raw_data = self._fetch_raw_trend_data('tiktok')
            if not raw_data:
                return self._get_backup_trends()
                
            # Parsing et transformation
            trends_data = self._parse_trend_data(raw_data, 'tiktok')
            if not trends_data:
                return self._get_backup_trends()
                
            trends = self._transform_to_trend_objects(trends_data, 'tiktok')
            
            # Mise en cache
            self._cache_trends(trends, 'tiktok')
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances TikTok: {str(e)}")
            return self._get_backup_trends()
            
    def _get_cached_trends(self, source: str) -> Optional[List[Trend]]:
        """
        Récupère les tendances depuis le cache
        """
        cache_file = self.cache_dir / f'{source}_trends.pkl'
        
        if not cache_file.exists():
            return None
            
        try:
            cache_time = cache_file.stat().st_mtime
            if time.time() - cache_time > self.cache_duration:
                return None
                
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                
            return [Trend(**trend) for trend in cached_data]
            
        except Exception as e:
            self.logger.warning(f"Erreur lors de la lecture du cache: {str(e)}")
            return None
            
    def _cache_trends(self, trends: List[Trend], source: str):
        """
        Met en cache les tendances
        """
        cache_file = self.cache_dir / f'{source}_trends.pkl'
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump([trend.dict() for trend in trends], f)
                
            self.logger.info(f"Tendances mises en cache dans {cache_file}")
            
        except Exception as e:
            self.logger.warning(f"Erreur lors de la mise en cache: {str(e)}")
            
    def _parse_views(self, views: any) -> int:
        """
        Parse le nombre de vues en entier
        """
        try:
            if isinstance(views, str):
                views = views.lower()
                if 'b' in views:
                    return int(float(views.replace('b', '')) * 1_000_000_000)
                elif 'm' in views:
                    return int(float(views.replace('m', '')) * 1_000_000)
                elif 'k' in views:
                    return int(float(views.replace('k', '')) * 1_000)
                return int(views)
            return int(views)
        except:
            return 0
            
    def _detect_category(self, title: str) -> Optional[str]:
        """
        Détecte la catégorie d'une tendance
        """
        categories = {
            'dance': ['dance', 'dancing', 'choreography'],
            'music': ['music', 'song', 'singing', 'artist'],
            'comedy': ['funny', 'comedy', 'humor', 'joke'],
            'food': ['food', 'cooking', 'recipe', 'eating'],
            'fashion': ['fashion', 'style', 'outfit', 'clothing'],
            'beauty': ['beauty', 'makeup', 'skincare', 'cosmetics'],
            'fitness': ['fitness', 'workout', 'exercise', 'gym'],
            'tech': ['tech', 'gaming', 'computer', 'phone']
        }
        
        title = title.lower()
        for category, keywords in categories.items():
            if any(keyword in title for keyword in keywords):
                return category
        return None
        
    def _get_backup_trends(self) -> List[Trend]:
        """
        Retourne une liste de tendances de backup
        """
        backup_trends = [
            {"name": "#fyp", "views": "1B+"},
            {"name": "#foryou", "views": "500M+"},
            {"name": "#viral", "views": "200M+"},
            {"name": "#trending", "views": "100M+"},
            {"name": "#dance", "views": "50M+"},
            {"name": "#music", "views": "40M+"},
            {"name": "#funny", "views": "30M+"},
            {"name": "#comedy", "views": "25M+"},
            {"name": "#tutorial", "views": "20M+"},
            {"name": "#food", "views": "15M+"}
        ]
        
        trends = []
        for trend in backup_trends:
            trends.append(Trend(
                platform='tiktok',
                type='hashtag',
                name=trend['name'],
                timestamp=datetime.now(),
                metadata=TrendMetadata(
                    views=self._parse_views(trend['views']),
                    source='backup',
                    category=self._detect_category(trend['name'])
                )
            ))
            
        self.logger.info("Utilisation des tendances de backup")
        return trends
        
    def _save_trends(self, trends: List[Trend]):
        """
        Sauvegarde les tendances dans un fichier JSON
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(__file__).parent / 'data'
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / f'trends_{timestamp}.json'
            
            # Conversion des objets Trend en dictionnaires avec sérialisation datetime
            trends_data = []
            for trend in trends:
                trend_dict = trend.dict()
                trend_dict['timestamp'] = trend_dict['timestamp'].isoformat()
                trends_data.append(trend_dict)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(trends_data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Tendances sauvegardées dans {output_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des tendances: {str(e)}")
            raise
            
    def _get_reddit_trends(self) -> List[Trend]:
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
                trends.append(Trend(
                    platform='reddit',
                    type='topic',
                    name=trend_data.get('title', ''),
                    timestamp=datetime.now(),
                    metadata=TrendMetadata(
                        url=trend_data.get('url', ''),
                        score=trend_data.get('score', 0)
                    )
                ))
                
            return trends
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des tendances Reddit: {str(e)}")
            return [] 