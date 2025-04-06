#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path
from typing import Dict
import yaml
from dotenv import load_dotenv
import shutil
import re

from ClipMaster.video_processor import VideoProcessor
from ClipMaster.youtube_downloader import YouTubeDownloader
from ContentCollector.content_collector import ContentCollector

def setup_logging():
    """Configure le système de logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def load_config() -> Dict:
    """Charge la configuration depuis le fichier YAML."""
    # Charge les variables d'environnement depuis .env
    load_dotenv()
    
    config_path = Path('config.yaml')
    if not config_path.exists():
        raise FileNotFoundError("Le fichier config.yaml est manquant")
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Remplace les clés API par celles des variables d'environnement
    if 'api' in config:
        if 'openai' in config['api']:
            config['api']['openai']['api_key'] = os.getenv('OPENAI_API_KEY')
        if 'youtube' in config['api']:
            config['api']['youtube']['api_key'] = os.getenv('YOUTUBE_API_KEY')
    
    return config

def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier pour le rendre compatible avec le système de fichiers."""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip()

def organize_outputs(output_paths: list, video_title: str, config: Dict):
    """
    Organise les fichiers de sortie dans une structure de dossiers.
    
    Args:
        output_paths (list): Liste des chemins des fichiers de sortie
        video_title (str): Titre de la vidéo
        config (Dict): Configuration du système
    """
    base_dir = Path(config['paths']['outputs']) / sanitize_filename(video_title)
    base_dir.mkdir(parents=True, exist_ok=True)
    
    for i, output_path in enumerate(output_paths, 1):
        segment_dir = base_dir / f'segment_{i:02d}'
        segment_dir.mkdir(exist_ok=True)
        
        # Déplacer la vidéo
        output_file = Path(output_path)
        if output_file.exists():
            shutil.move(str(output_file), segment_dir / f'segment_{i:02d}.mp4')

def main():
    """Point d'entrée principal du programme."""
    # Configuration du logging
    logger = setup_logging()
    
    # Parsing des arguments
    parser = argparse.ArgumentParser(description='Traitement de vidéos YouTube pour TikTok')
    parser.add_argument('youtube_url', help='URL de la vidéo YouTube')
    parser.add_argument('--dry-run', action='store_true', help='Mode analyse sans export')
    args = parser.parse_args()
    
    try:
        # Chargement de la configuration
        config = load_config()
        
        # Extraction de l'ID de la vidéo YouTube
        video_id = args.youtube_url.split('v=')[-1].split('&')[0]
        logger.info(f"ID de la vidéo YouTube : {video_id}")
        
        # Récupération des métadonnées via l'API YouTube
        logger.info("Récupération des métadonnées via l'API YouTube")
        collector = ContentCollector(config)
        video_details = collector._get_video_details([video_id])
        
        if not video_details:
            logger.error("Impossible de récupérer les métadonnées de la vidéo")
            raise ValueError("Métadonnées non disponibles")
            
        video_metadata = collector._format_video_data(video_details[0])
        logger.info(f"Métadonnées récupérées : {video_metadata['title']}")
        
        # Téléchargement de la vidéo
        logger.info("Téléchargement de la vidéo")
        downloader = YouTubeDownloader()
        video_path = downloader.download(args.youtube_url)
        
        # Traitement de la vidéo avec les métadonnées
        logger.info("Traitement de la vidéo")
        processor = VideoProcessor(config)
        output_paths = processor.process_video(
            str(video_path), 
            dry_run=args.dry_run,
            video_metadata=video_metadata  # Passage des métadonnées YouTube
        )
        
        if not args.dry_run:
            # Organisation des résultats
            logger.info("Organisation des résultats")
            processor.organize_outputs(output_paths, video_metadata['title'])
        
        logger.info("Traitement terminé avec succès")
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement: {str(e)}")
        raise

if __name__ == '__main__':
    main() 