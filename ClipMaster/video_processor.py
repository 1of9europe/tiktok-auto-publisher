import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import json
from datetime import datetime
import numpy as np
import subprocess
import shutil
import re
import openai
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip
from moviepy.video.fx.all import resize

from .video_encoder import VideoEncoder

class VideoProcessor:
    """
    Classe principale pour le traitement de vidéos destinées aux réseaux sociaux.
    Gère le découpage, l'ajout de sous-titres, la génération de métadonnées et l'encodage.
    """
    
    def __init__(self, config: Dict):
        """
        Initialise le processeur vidéo avec la configuration.
        
        Args:
            config (Dict): Configuration du système
        """
        self.config = config
        self.setup_logging()
        self.encoder = VideoEncoder(config)
        
        # Chemins de base
        self.outputs_dir = Path(config['paths']['outputs'])
        self.downloads_dir = Path(config['paths']['downloads'])
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration des polices
        self.font_config = {
            'default': 'Arial',
            'bold': 'Arial-Bold',
            'fallback': 'Helvetica'
        }
        
        # Options de configuration avec valeurs par défaut
        self.use_subtitles = config.get('use_subtitles', True)
        self.subtitle_style = config.get('subtitle_style', 'auto')
        self.force_vertical = config.get('video_settings', {}).get('force_vertical', False)
        self.add_watermark = config.get('video_settings', {}).get('add_watermark', False)
        self.watermark_path = config.get('video_settings', {}).get('watermark_path', '')
        self.watermark_position = config.get('video_settings', {}).get('watermark_position', 'bottom-right')
        self.watermark_opacity = config.get('video_settings', {}).get('watermark_opacity', 0.7)
        
        # Initialisation des modèles si nécessaire
        self._init_models()
        
    def setup_logging(self):
        """Configure le système de logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('VideoProcessor')
        
    def _init_models(self):
        """Initialise les modèles nécessaires (Whisper, etc.)."""
        if self.use_subtitles:
            try:
                import whisper
                self.logger.info("🔄 Chargement du modèle Whisper...")
                self.whisper_model = whisper.load_model("base")
                self.logger.info("✅ Modèle Whisper chargé")
            except ImportError:
                self.logger.warning("⚠️ Whisper non installé, les sous-titres seront désactivés")
                self.use_subtitles = False
                
    def process_video(self, video_path: str, dry_run: bool = False, video_metadata: Optional[Dict] = None) -> List[str]:
        """
        Traite une vidéo en la découpant en segments et en ajoutant des sous-titres si activé.
        
        Args:
            video_path (str): Chemin de la vidéo à traiter
            dry_run (bool): Si True, ne fait que l'analyse sans exporter
            video_metadata (Optional[Dict]): Métadonnées de la vidéo YouTube
            
        Returns:
            List[str]: Liste des chemins des segments traités
        """
        try:
            self.logger.info(f"🎬 Traitement de la vidéo: {video_path}")
            
            # Vérification du fichier
            if not os.path.exists(video_path):
                self.logger.error(f"❌ Fichier introuvable: {video_path}")
                return []
                
            # Chargement de la vidéo
            video = VideoFileClip(video_path)
            self.logger.info(f"📊 Informations vidéo: {video.w}x{video.h}, {video.duration:.2f}s, {video.fps}fps")
            
            # Découpage en segments
            segments = self._split_video(video)
            self.logger.info(f"✂️ Vidéo découpée en {len(segments)} segments")
            
            if dry_run:
                self.logger.info("🔍 Mode dry_run: analyse terminée sans export")
                video.close()
                return []
                
            # Traitement des segments
            output_paths = []
            fps = self.config.get('video_settings', {}).get('fps', 30)
            
            for i, segment in enumerate(segments):
                try:
                    self.logger.info(f"🔄 Segment {i+1}/{len(segments)}")
                    
                    # Export temporaire simple avec MoviePy
                    temp_path = f"temp_segment_{i+1}.mp4"
                    segment.write_videofile(
                        temp_path,
                        codec='libx264',
                        audio_codec='aac',
                        fps=fps
                    )
                    
                    # Génération des sous-titres si activé
                    subtitles = None
                    if self.use_subtitles:
                        subtitles = self._generate_subtitles_for_segment(VideoFileClip(temp_path))
                    
                    # Simplification de la gestion des sous-titres
                    segment_clip = VideoFileClip(temp_path)
                    
                    # Application du format vertical si demandé
                    if self.force_vertical and segment_clip.w / segment_clip.h < 9/16:
                        segment_clip = self._force_vertical_format(segment_clip)
                    
                    # Ajout des sous-titres si disponibles
                    if subtitles:
                        segment_with_subs = self._add_subtitles(
                            segment_clip, 
                            subtitles,
                            style=self.subtitle_style
                        )
                    else:
                        segment_with_subs = segment_clip
                    
                    # Ajout du watermark si activé
                    if self.add_watermark and self.watermark_path:
                        segment_with_subs = self._add_watermark(segment_with_subs)
                    
                    # Génération des métadonnées avec numéro de partie
                    metadata = self._generate_metadata(
                        video_path,
                        subtitles.get("text") if subtitles else None,
                        video_metadata
                    )
                    
                    # Ajout du numéro de partie au titre
                    if metadata and 'title' in metadata:
                        metadata['title'] = f"{metadata['title']} (partie {i + 1})"
                        self.logger.info(f"📝 Titre du segment {i+1}: {metadata['title']}")
                        self.logger.debug(f"📦 Métadonnées générées: {metadata}")
                    
                    # Sauvegarde temporaire avec sous-titres
                    temp_with_subs = f"temp_with_subs_{i+1}.mp4"
                    segment_with_subs.write_videofile(
                        temp_with_subs,
                        codec='libx264',
                        audio_codec='aac',
                        fps=fps
                    )
                    
                    # Réencodage avec FFmpeg si activé
                    if self.config.get('video_settings', {}).get('reencode_with_ffmpeg', True):
                        output_path = self._save_video(segment_with_subs, video_path, metadata)
                        if not self.encoder.reencode_video(temp_with_subs, output_path):
                            self.logger.error(f"❌ Échec de l'encodage FFmpeg pour le segment {i+1}")
                            continue
                    else:
                        output_path = self._save_video(segment_with_subs, video_path, metadata)
                    
                    output_paths.append(str(output_path))
                    
                    # Nettoyage sécurisé des fichiers temporaires
                    for temp_file in [temp_path, temp_with_subs]:
                        try:
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                        except Exception as cleanup_err:
                            self.logger.warning(f"⚠️ Échec du nettoyage de {temp_file}: {cleanup_err}")
                    
                    # Fermeture des clips
                    segment_with_subs.close()
                    segment_clip.close()
                    
                except Exception as e:
                    self.logger.error(f"❌ Erreur segment {i+1}: {str(e)}")
                    continue
            
            video.close()
            return output_paths
            
        except Exception as e:
            self.logger.error(f"❌ Erreur globale: {str(e)}")
            raise
            
    def _split_video(self, video: VideoFileClip) -> List[VideoFileClip]:
        """
        Découpe une vidéo en segments de durée fixe.
        
        Args:
            video (VideoFileClip): Vidéo à découper
            
        Returns:
            List[VideoFileClip]: Liste des segments
        """
        try:
            segments = []
            duration = video.duration
            segment_duration = self.config.get('video_settings', {}).get('segment_duration', 60)
            
            for start_time in range(0, int(duration), segment_duration):
                end_time = min(start_time + segment_duration, duration)
                segment = video.subclip(start_time, end_time)
                segments.append(segment)
                
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du découpage: {str(e)}")
            raise
            
    def _generate_subtitles_for_segment(self, segment: VideoFileClip) -> Optional[Dict]:
        """
        Génère les sous-titres pour un segment avec Whisper.
        
        Args:
            segment (VideoFileClip): Segment vidéo
            
        Returns:
            Optional[Dict]: Données des sous-titres ou None en cas d'erreur
        """
        if not self.use_subtitles:
            return None
            
        try:
            self.logger.info("🎤 Génération des sous-titres...")
            
            # Sauvegarde temporaire du segment
            temp_path = "temp_for_whisper.mp4"
            segment.write_videofile(
                temp_path,
                codec='libx264',
                audio_codec='aac',
                fps=24
            )
            
            # Transcription avec Whisper
            result = self.whisper_model.transcribe(temp_path)
            
            # Nettoyage
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            # Sauvegarde des sous-titres en SRT
            srt_path = f"temp_segment.srt"
            self._save_srt(result['segments'], srt_path)
            
            return {
                'text': result['text'],
                'segments': result['segments']
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la génération des sous-titres: {str(e)}")
            return None
            
    def _save_srt(self, segments: List[Dict], output_path: str) -> bool:
        """
        Sauvegarde les segments en format SRT.
        
        Args:
            segments (List[Dict]): Segments de sous-titres
            output_path (str): Chemin de sortie
            
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    start = self._format_timestamp(segment['start'])
                    end = self._format_timestamp(segment['end'])
                    text = segment['text'].strip()
                    
                    f.write(f"{i}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
                    
            self.logger.info(f"💬 Sous-titres sauvegardés: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la sauvegarde des sous-titres: {str(e)}")
            return False
            
    def _format_timestamp(self, seconds: float) -> str:
        """
        Convertit un timestamp en secondes en format SRT.
        
        Args:
            seconds (float): Timestamp en secondes
            
        Returns:
            str: Timestamp au format SRT
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
            
    def _add_subtitles(self, video: VideoFileClip, subtitles: Dict, style: str = "auto") -> CompositeVideoClip:
        """
        Ajoute des sous-titres stylisés à une vidéo avec un style fixe TikTok-friendly.
        
        Args:
            video (VideoFileClip): Clip vidéo
            subtitles (Dict): Données des sous-titres
            style (str): Style des sous-titres (ignoré, style fixe)
            
        Returns:
            CompositeVideoClip: Vidéo avec sous-titres
        """
        try:
            txt_clips = []
            font = self.font_config['bold']  # Utilisation de Arial-Bold
            
            # Taille de police adaptative entre 24 et 48px
            min_fontsize = 24
            max_fontsize = 48
            base_fontsize = int(video.h * 0.08)  # 8% de la hauteur
            fontsize = max(min_fontsize, min(base_fontsize, max_fontsize))
            
            for segment in subtitles['segments']:
                start = segment['start']
                end = segment['end']
                text = segment['text']
                
                # Style fixe TikTok-friendly
                text_color = '#ffc800'  # Jaune foncé
                stroke_color = 'black'
                stroke_width = 1.5  # Contour fin
                bg_color = (0, 0, 0)  # Fond noir semi-transparent
                
                # Création du clip de texte avec style amélioré
                txt_clip = TextClip(
                    text,
                    font=font,
                    fontsize=fontsize,
                    color=text_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    method='caption',
                    size=(video.w * 0.9, None),  # Largeur max 90% de la vidéo
                    align='center'
                )
                
                # Création du fond semi-transparent
                bg_width = txt_clip.w + 40  # Marge de 20px de chaque côté
                bg_height = txt_clip.h + 20  # Marge de 10px en haut et en bas
                bg_clip = ColorClip(
                    size=(bg_width, bg_height),
                    color=bg_color
                ).set_opacity(0.3)  # 30% d'opacité
                
                # Positionnement en bas de l'écran avec marge
                txt_pos = ('center', video.h - txt_clip.h - 30)  # 30px du bas
                bg_pos = ('center', video.h - bg_clip.h - 25)  # 25px du bas
                
                # Application du timing
                txt_clip = txt_clip.set_position(txt_pos).set_start(start).set_end(end)
                bg_clip = bg_clip.set_position(bg_pos).set_start(start).set_end(end)
                
                # Ajout à la liste des clips
                txt_clips.extend([bg_clip, txt_clip])
            
            # Composition finale
            final = CompositeVideoClip([video] + txt_clips)
            return final
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres: {str(e)}")
            return video  # Retourne la vidéo sans sous-titres en cas d'erreur
            
    def _force_vertical_format(self, clip: VideoFileClip) -> VideoFileClip:
        """
        Force un format vertical 9:16 avec padding si nécessaire.
        
        Args:
            clip (VideoFileClip): Clip vidéo
            
        Returns:
            VideoFileClip: Clip au format vertical
        """
        try:
            # Calcul des dimensions cibles (9:16)
            target_ratio = 9/16
            current_ratio = clip.w / clip.h
            
            if current_ratio > target_ratio:
                # Vidéo trop large, on ajoute des bandes noires en haut et en bas
                new_height = int(clip.w / target_ratio)
                padding = (new_height - clip.h) // 2
                
                # Création d'un fond noir
                bg = ColorClip(size=(clip.w, new_height), color=(0, 0, 0))
                
                # Positionnement de la vidéo au centre
                video_pos = ('center', padding)
                
                # Composition
                final = CompositeVideoClip([bg, clip.set_position(video_pos)])
                return final
            else:
                # Vidéo déjà assez haute, on la centre horizontalement
                new_width = int(clip.h * target_ratio)
                padding = (new_width - clip.w) // 2
                
                # Création d'un fond noir
                bg = ColorClip(size=(new_width, clip.h), color=(0, 0, 0))
                
                # Positionnement de la vidéo au centre
                video_pos = (padding, 'center')
                
                # Composition
                final = CompositeVideoClip([bg, clip.set_position(video_pos)])
                return final
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du formatage vertical: {str(e)}")
            return clip  # Retourne le clip original en cas d'erreur
            
    def _add_watermark(self, clip: VideoFileClip) -> CompositeVideoClip:
        """
        Ajoute un watermark à la vidéo.
        
        Args:
            clip (VideoFileClip): Clip vidéo
            
        Returns:
            CompositeVideoClip: Vidéo avec watermark
        """
        try:
            if not os.path.exists(self.watermark_path):
                self.logger.warning(f"⚠️ Fichier watermark introuvable: {self.watermark_path}")
                return clip
                
            # Chargement du watermark
            watermark = ImageClip(self.watermark_path)
            
            # Redimensionnement (10% de la hauteur de la vidéo)
            watermark_height = int(clip.h * 0.1)
            watermark = watermark.resize(height=watermark_height)
            
            # Positionnement selon la configuration
            if self.watermark_position == 'top-left':
                pos = (10, 10)
            elif self.watermark_position == 'top-right':
                pos = (clip.w - watermark.w - 10, 10)
            elif self.watermark_position == 'bottom-left':
                pos = (10, clip.h - watermark.h - 10)
            elif self.watermark_position == 'bottom-right':
                pos = (clip.w - watermark.w - 10, clip.h - watermark.h - 10)
            else:  # center par défaut
                pos = ('center', 'center')
                
            # Application de l'opacité
            watermark = watermark.set_opacity(self.watermark_opacity)
            
            # Application du timing
            watermark = watermark.set_duration(clip.duration)
            
            # Composition
            final = CompositeVideoClip([clip, watermark.set_position(pos)])
            return final
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'ajout du watermark: {str(e)}")
            return clip  # Retourne le clip original en cas d'erreur
            
    def _basic_metadata(self, video_path: str) -> Dict:
        """
        Génère des métadonnées basiques en cas d'échec de GPT.
        
        Args:
            video_path (str): Chemin de la vidéo
            
        Returns:
            Dict: Métadonnées basiques
        """
        title = Path(video_path).stem
        return {
            'title': title[:100],  # Limite TikTok
            'description': f"Découvrez : {title} ✨",
            'hashtags': ['#tiktok', '#viral', '#trending', '#fyp', '#foryou', '#shorts'],
            'generated_date': datetime.now().isoformat(),
            'generation_mode': 'fallback'
        }
            
    def _get_youtube_metadata(self, video_path: str) -> Optional[Dict]:
        """
        Récupère les métadonnées YouTube de la vidéo.
        
        Args:
            video_path (str): Chemin de la vidéo
            
        Returns:
            Optional[Dict]: Métadonnées YouTube de la vidéo ou None si inexistantes
        """
        try:
            # Utilisation d'une commande FFprobe pour récupérer les métadonnées YouTube
            command = ['ffprobe', '-v', 'error', '-show_entries', 'format=title,description,channel_title,views,published_at', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.warning("⚠️ Aucune métadonnée YouTube trouvée")
                return None
                
            # Extraction des métadonnées
            metadata = {}
            for line in result.stdout.splitlines():
                key, value = line.split('=')
                metadata[key] = value
            
            # Vérification des métadonnées
            if not metadata.get('title') or not metadata.get('description'):
                self.logger.warning("⚠️ Métadonnées YouTube incomplètes")
                return None
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la récupération des métadonnées YouTube: {str(e)}")
            return None
            
    def _generate_metadata(self, video_path: str, transcript: Optional[str] = None, video_metadata: Optional[Dict] = None) -> Dict:
        """
        Génère les métadonnées pour la vidéo (titre, description, hashtags).
        
        Args:
            video_path (str): Chemin de la vidéo
            transcript (Optional[str]): Transcription du texte
            video_metadata (Optional[Dict]): Métadonnées YouTube de la vidéo
            
        Returns:
            Dict: Métadonnées générées
        """
        try:
            # Mode basic : génération simple
            if not transcript or self.config['metadata']['generation_mode'] == 'basic':
                return self._basic_metadata(video_path)
                
            # Mode GPT : génération avec OpenAI
            prompt = f"""
            Basé sur cette vidéo YouTube et sa transcription, génère un contenu viral pour TikTok :
            
            Métadonnées YouTube :
            - Titre original : {video_metadata.get('title', 'Non disponible')}
            - Description : {video_metadata.get('description', 'Non disponible')}
            - Chaîne : {video_metadata.get('channel_title', 'Non disponible')}
            - Vues : {video_metadata.get('views', 0):,}
            - Date de publication : {video_metadata.get('published_at', 'Non disponible')}
            
            Transcription :
            {transcript[:1000]}...
            
            Format de réponse strict (JSON) :
            {{
                "title": "Titre accrocheur et unique (max 100 caractères)",
                "description": "Description engageante et différente du titre (max 150 caractères)",
                "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
            }}
            
            IMPORTANT :
            - Le titre et la description DOIVENT être différents
            - Utilise des emojis pertinents
            - Les hashtags doivent être populaires sur TikTok
            - Adapte le contenu pour le format court TikTok
            - Garde l'essence de la vidéo originale
            """
            
            client = openai.OpenAI(api_key=self.config['api']['openai']['api_key'])
            response = client.chat.completions.create(
                model=self.config['api']['openai']['model'],
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config['api']['openai']['temperature']
            )
            
            # Lecture sécurisée du JSON GPT
            try:
                raw = response.choices[0].message.content.strip()
                metadata = json.loads(raw)
                
                # Validation du contenu
                if not metadata.get("title") or not metadata.get("description"):
                    raise ValueError("Titre ou description manquant")
                    
                if metadata.get("title", "") == metadata.get("description", ""):
                    metadata["description"] = f"Regardez cette vidéo : {metadata['title']} ✨"
                    
                if not metadata.get("hashtags") or len(metadata["hashtags"]) < 3:
                    metadata["hashtags"] = ['#tiktok', '#viral', '#trending', '#fyp', '#foryou']
                    
                metadata['generated_date'] = datetime.now().isoformat()
                metadata['generation_mode'] = 'gpt'
                metadata['original_metadata'] = video_metadata  # Stockage des métadonnées originales
                
                return metadata
                
            except Exception as json_err:
                self.logger.warning(f"⚠️ Parsing GPT échoué, fallback: {json_err}")
                return self._basic_metadata(video_path)
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la génération des métadonnées: {str(e)}")
            return self._basic_metadata(video_path)
            
    def _save_video(self, video: VideoFileClip, original_path: str, metadata: Dict) -> Path:
        """
        Sauvegarde une vidéo avec ses métadonnées.
        
        Args:
            video (VideoFileClip): Clip vidéo à sauvegarder
            original_path (str): Chemin de la vidéo originale
            metadata (Dict): Métadonnées de la vidéo
            
        Returns:
            Path: Chemin de la vidéo sauvegardée
        """
        try:
            # Création du dossier de sortie avec la date
            date_str = datetime.now().strftime("%Y-%m-%d")
            output_dir = Path(self.config['paths']['outputs']) / date_str
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Utilisation du titre modifié pour le nom du fichier
            title = metadata.get('title', Path(original_path).stem)
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            output_path = output_dir / f"{safe_title}.mp4"
            
            # Sauvegarde des métadonnées
            metadata_path = output_path.with_suffix('.txt')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(f"Titre: {metadata.get('title', '')}\n")
                f.write(f"Description: {metadata.get('description', '')}\n")
                f.write(f"Hashtags: {' '.join(metadata.get('hashtags', []))}\n")
            
            self.logger.info(f"📝 Métadonnées sauvegardées: {metadata_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
            raise
            
    def organize_outputs(self, output_paths: List[str], video_title: str) -> None:
        """
        Organise les fichiers de sortie dans une structure de dossiers.
        
        Args:
            output_paths (List[str]): Liste des chemins des fichiers de sortie
            video_title (str): Titre de la vidéo
        """
        try:
            # Création du dossier principal
            base_dir = Path(self.config['paths']['outputs']) / self._sanitize_filename(video_title)
            base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"\n📁 Création du dossier principal : {base_dir}")

            # Organisation des segments
            for i, output_path in enumerate(output_paths, 1):
                try:
                    segment_dir = base_dir / f'segment_{i:02d}'
                    segment_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"\n🔄 Traitement du segment {i:02d}")

                    output_file = Path(output_path)
                    if output_file.exists():
                        # Déplacer la vidéo
                        video_path = segment_dir / f'segment_{i:02d}.mp4'
                        shutil.move(str(output_file), video_path)
                        self.logger.info(f"✅ Vidéo déplacée : {video_path}")

                        # Vérifier et déplacer les métadonnées associées
                        metadata_path = output_file.with_suffix('.txt')
                        if metadata_path.exists():
                            shutil.move(str(metadata_path), segment_dir / 'metadata.txt')
                            self.logger.info(f"📝 Métadonnées déplacées : {segment_dir}/metadata.txt")
                        else:
                            self.logger.warning(f"⚠️ Aucune métadonnée trouvée pour le segment {i:02d}")

                        # Vérifier et déplacer les sous-titres SRT si présents
                        srt_path = output_file.with_suffix('.srt')
                        if srt_path.exists():
                            shutil.move(str(srt_path), segment_dir / f'segment_{i:02d}.srt')
                            self.logger.info(f"💬 Sous-titres déplacés : {segment_dir}/segment_{i:02d}.srt")

                    else:
                        self.logger.error(f"❌ Fichier introuvable : {output_path}")

                except Exception as e:
                    self.logger.error(f"⚠️ Erreur lors du traitement du segment {i:02d}: {str(e)}")
                    continue

            self.logger.info(f"\n✨ Organisation terminée !")
            self.logger.info(f"📂 Dossier de sortie : {base_dir}")
            self.logger.info(f"📊 Nombre de segments : {len(output_paths)}")

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'organisation des fichiers : {str(e)}")
            raise
            
    def _sanitize_filename(self, name: str) -> str:
        """
        Nettoie un nom de fichier pour qu'il soit valide sur tous les OS.
        
        Args:
            name (str): Nom de fichier à nettoyer
            
        Returns:
            str: Nom de fichier nettoyé
        """
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
        
    def upload_to_tiktok(self, video_path: str, metadata: Dict) -> bool:
        """
        Upload une vidéo sur TikTok (placeholder pour future implémentation).
        
        Args:
            video_path (str): Chemin de la vidéo
            metadata (Dict): Métadonnées de la vidéo
            
        Returns:
            bool: True si l'upload a réussi, False sinon
        """
        self.logger.info("⚠️ Fonctionnalité d'upload TikTok non implémentée")
        self.logger.info(f"📤 Vidéo prête pour upload: {video_path}")
        self.logger.info(f"📝 Titre: {metadata.get('title', '')}")
        self.logger.info(f"📝 Description: {metadata.get('description', '')}")
        self.logger.info(f"🏷️ Hashtags: {' '.join(metadata.get('hashtags', []))}")
        return False

    def _cleanup_temp_files(self, file_paths: List[str]) -> None:
        """
        Nettoie les fichiers temporaires.
        
        Args:
            file_paths (List[str]): Liste des chemins des fichiers à supprimer
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.debug(f"🧹 Fichier temporaire supprimé: {file_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Échec de la suppression de {file_path}: {str(e)}")

    def _add_subtitles_ffmpeg(self, video_path: str, srt_path: str, output_path: str) -> bool:
        """
        Ajoute des sous-titres à une vidéo avec FFmpeg en utilisant un style fixe TikTok-friendly.
        
        Args:
            video_path (str): Chemin de la vidéo d'entrée
            srt_path (str): Chemin du fichier SRT
            output_path (str): Chemin de la vidéo de sortie
            
        Returns:
            bool: True si l'ajout des sous-titres a réussi, False sinon
        """
        try:
            # Vérification des fichiers
            if not os.path.exists(video_path):
                self.logger.error(f"❌ Vidéo introuvable: {video_path}")
                return False
            if not os.path.exists(srt_path):
                self.logger.error(f"❌ Fichier SRT introuvable: {srt_path}")
                return False
                
            # Récupération des dimensions de la vidéo
            probe_cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error("❌ Erreur lors de l'analyse de la vidéo")
                return False
                
            # Calcul de la taille de police adaptative
            video_info = json.loads(result.stdout)
            width = video_info['streams'][0]['width']
            height = video_info['streams'][0]['height']
            min_dim = min(width, height)
            font_size = max(24, min(48, int(min_dim * 0.05)))  # Entre 24 et 48px
            
            # Style ASS pour libass
            ass_style = f"""
[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial-Bold,{font_size},&H00FFC800,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,1.5,0,2,20,20,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            
            # Sauvegarde du style ASS
            ass_path = srt_path.replace('.srt', '.ass')
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_style)
                
            # Conversion SRT vers ASS
            with open(srt_path, 'r', encoding='utf-8') as srt_file:
                srt_content = srt_file.read()
                # Conversion des timestamps et ajout des lignes
                for line in srt_content.split('\n\n'):
                    if line.strip():
                        parts = line.split('\n')
                        if len(parts) >= 3:
                            timing = parts[1]
                            text = parts[2]
                            ass_line = f"Dialogue: 0,{timing},Default,,0,0,0,,{text}\n"
                            with open(ass_path, 'a', encoding='utf-8') as f:
                                f.write(ass_line)
                                
            # Commande FFmpeg avec libass
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-vf', f"ass={ass_path}",
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',
                output_path
            ]
            
            # Exécution de la commande
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Nettoyage des fichiers temporaires
            self._cleanup_temp_files([ass_path])
            
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres avec libass: {result.stderr}")
                
                # Fallback avec drawtext
                self.logger.info("🔄 Tentative avec drawtext...")
                
                # Conversion des timestamps SRT en format drawtext
                drawtext_filter = self._convert_srt_to_drawtext(srt_path, width, height, font_size)
                
                # Commande FFmpeg avec drawtext
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', video_path,
                    '-vf', drawtext_filter,
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-c:a', 'copy',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres avec drawtext: {result.stderr}")
                    return False
                    
            self.logger.info("✅ Sous-titres ajoutés avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres: {str(e)}")
            return False
            
    def _convert_srt_to_drawtext(self, srt_path: str, width: int, height: int, font_size: int) -> str:
        """
        Convertit un fichier SRT en filtre drawtext FFmpeg.
        
        Args:
            srt_path (str): Chemin du fichier SRT
            width (int): Largeur de la vidéo
            height (int): Hauteur de la vidéo
            font_size (int): Taille de la police
            
        Returns:
            str: Filtre drawtext FFmpeg
        """
        try:
            drawtext_parts = []
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                segments = content.split('\n\n')
                
                for segment in segments:
                    if not segment.strip():
                        continue
                        
                    lines = segment.split('\n')
                    if len(lines) >= 3:
                        timing = lines[1]
                        text = lines[2].strip()
                        
                        # Conversion du timing
                        start_time, end_time = timing.split(' --> ')
                        start_seconds = self._srt_time_to_seconds(start_time)
                        end_seconds = self._srt_time_to_seconds(end_time)
                        
                        # Création du filtre drawtext
                        drawtext = (
                            f"drawtext=text='{text}':"
                            f"fontfile=/System/Library/Fonts/Arial.ttf:"  # Chemin de la police
                            f"fontsize={font_size}:"
                            f"fontcolor=#ffc800:"  # Jaune foncé
                            f"bordercolor=black:"
                            f"borderw=1.5:"
                            f"x=(w-text_w)/2:"  # Centrage horizontal
                            f"y=h-th-30:"  # 30px du bas
                            f"enable='between(t,{start_seconds},{end_seconds})'"
                        )
                        drawtext_parts.append(drawtext)
                        
            # Combinaison des filtres
            return ','.join(drawtext_parts)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la conversion SRT vers drawtext: {str(e)}")
            return ""
            
    def _srt_time_to_seconds(self, srt_time: str) -> float:
        """
        Convertit un timestamp SRT en secondes.
        
        Args:
            srt_time (str): Timestamp au format SRT (HH:MM:SS,mmm)
            
        Returns:
            float: Nombre de secondes
        """
        hours, minutes, seconds = srt_time.replace(',', '.').split(':')
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds) 