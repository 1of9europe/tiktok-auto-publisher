import requests
import logging
from pathlib import Path
from typing import Dict
import json
from datetime import datetime
import os

class AutoPublisher:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('AutoPublisher')
        
    def publish_video(self, video_path: str, metadata: Dict) -> Dict:
        """
        Publie une vidéo sur TikTok
        Args:
            video_path (str): Chemin vers la vidéo à publier
            metadata (Dict): Métadonnées de la vidéo
        Returns:
            Dict: Résultat de la publication
        """
        try:
            self.logger.info(f"Préparation de la publication de la vidéo: {video_path}")
            
            # Vérification de la taille du fichier
            if not self._check_file_size(video_path):
                raise ValueError("La taille de la vidéo dépasse la limite autorisée")
                
            # Préparation des données pour l'API TikTok
            post_data = self._prepare_post_data(video_path, metadata)
            
            # Simulation de la publication (à remplacer par l'API TikTok réelle)
            response = self._mock_tiktok_api(post_data)
            
            # Sauvegarde du rapport de publication
            self._save_publish_report(response, video_path)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la publication: {str(e)}")
            raise
            
    def _check_file_size(self, video_path: str) -> bool:
        """
        Vérifie si la taille du fichier est conforme aux limites de TikTok
        """
        try:
            file_size = Path(video_path).stat().st_size
            max_size = self.config['video_settings']['max_file_size']
            
            return file_size <= max_size
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de la taille du fichier: {str(e)}")
            raise
            
    def _prepare_post_data(self, video_path: str, metadata: Dict) -> Dict:
        """
        Prépare les données pour la publication
        """
        try:
            if metadata is None:
                raise ValueError("Les métadonnées ne peuvent pas être None")
                
            # Limitation du nombre de hashtags
            hashtags = metadata.get('hashtags', [])[:self.config['api']['tiktok']['max_hashtags']]
            
            # Préparation de la description
            description = metadata.get('description', '')
            if len(description) > self.config['api']['tiktok']['max_description_length']:
                description = description[:self.config['api']['tiktok']['max_description_length']] + "..."
                
            # Construction des données de publication
            post_data = {
                'video_file': video_path,
                'title': metadata.get('title', ''),
                'description': description,
                'hashtags': hashtags,
                'privacy_level': 'public',
                'allow_comments': True,
                'allow_duet': True,
                'allow_stitch': True
            }
            
            return post_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la préparation des données: {str(e)}")
            raise
            
    def _mock_tiktok_api(self, post_data: Dict) -> Dict:
        """
        Simule l'API TikTok (à remplacer par l'API réelle)
        """
        try:
            # Simulation d'une réponse de l'API
            response = {
                'status': 'success',
                'message': 'Vidéo prête pour publication',
                'post_data': post_data,
                'timestamp': datetime.now().isoformat(),
                'mock_video_url': f"https://tiktok.com/@user/video/{hash(post_data['video_file'])}"
            }
            
            self.logger.info("Vidéo préparée avec succès pour publication")
            return response
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la simulation de l'API: {str(e)}")
            raise
            
    def _save_publish_report(self, response: Dict, video_path: str):
        """
        Sauvegarde le rapport de publication
        """
        try:
            output_dir = Path(video_path).parent / 'publish_reports'
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f'publish_report_{timestamp}.json'
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Rapport de publication sauvegardé dans {output_file}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du rapport: {str(e)}")
            raise 