from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper
import openai
import logging
from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime
import os

class ClipMaster:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        self.outputs_dir = Path(self.config['paths']['outputs'])
        self.outputs_dir.mkdir(exist_ok=True)
        self.model = whisper.load_model("base")
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('ClipMaster')
        
    def process_video(self, video_path: str) -> Dict:
        """
        Traite une vidéo en ajoutant des sous-titres et en la préparant pour TikTok
        Args:
            video_path (str): Chemin vers la vidéo à traiter
        Returns:
            Dict: Métadonnées de la vidéo traitée
        """
        try:
            self.logger.info(f"Traitement de la vidéo: {video_path}")
            
            # Chargement de la vidéo
            video = VideoFileClip(video_path)
            
            # Génération des sous-titres
            subtitles = self._generate_subtitles(video_path)
            
            # Ajout des sous-titres à la vidéo
            final_video = self._add_subtitles(video, subtitles)
            
            # Génération du titre et des hashtags
            metadata = self._generate_metadata(video_path, subtitles['text'])
            
            # Sauvegarde de la vidéo
            output_path = self._save_video(final_video, video_path, metadata)
            
            # Nettoyage
            video.close()
            final_video.close()
            
            return {
                'input_path': video_path,
                'output_path': str(output_path),
                'metadata': metadata,
                'subtitles': subtitles
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de la vidéo: {str(e)}")
            raise
            
    def _generate_subtitles(self, video_path: str) -> Dict:
        """
        Génère les sous-titres pour une vidéo
        """
        try:
            self.logger.info("Génération des sous-titres...")
            
            # Transcription avec Whisper
            result = self.model.transcribe(video_path)
            
            return {
                'text': result['text'],
                'segments': result['segments']
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération des sous-titres: {str(e)}")
            raise
            
    def _add_subtitles(self, video: VideoFileClip, subtitles: Dict) -> CompositeVideoClip:
        """
        Ajoute les sous-titres à la vidéo
        """
        try:
            self.logger.info("Ajout des sous-titres à la vidéo...")
            
            # Configuration des sous-titres
            txt_clips = []
            
            for segment in subtitles['segments']:
                start = segment['start']
                end = segment['end']
                text = segment['text']
                
                txt_clip = TextClip(
                    text,
                    font='Arial',
                    fontsize=24,
                    color='white',
                    stroke_color='black',
                    stroke_width=2
                )
                
                txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(end - start).set_start(start)
                txt_clips.append(txt_clip)
                
            # Composition finale
            final = CompositeVideoClip([video] + txt_clips)
            
            return final
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout des sous-titres: {str(e)}")
            raise
            
    def _generate_metadata(self, video_path: str, transcript: str) -> Dict:
        """
        Génère le titre et les hashtags pour la vidéo
        """
        try:
            self.logger.info("Génération des métadonnées...")
            
            # Utilisation de GPT pour générer le titre et les hashtags
            prompt = f"""
            Basé sur cette transcription de vidéo, génère :
            1. Un titre accrocheur pour TikTok (max 100 caractères)
            2. Une description engageante (max 150 caractères)
            3. 5 hashtags pertinents
            
            Transcription :
            {transcript[:1000]}...
            
            Format de réponse souhaité :
            {{"title": "...", "description": "...", "hashtags": ["...", "..."]}}
            """
            
            response = openai.ChatCompletion.create(
                model=self.config['api']['openai']['model'],
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config['api']['openai']['temperature']
            )
            
            metadata = json.loads(response.choices[0].message.content)
            metadata['generated_date'] = datetime.now().isoformat()
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération des métadonnées: {str(e)}")
            raise
            
    def _save_video(self, video: CompositeVideoClip, input_path: str, metadata: Dict) -> Path:
        """
        Sauvegarde la vidéo éditée
        """
        try:
            # Création du nom de fichier
            input_filename = Path(input_path).stem
            output_filename = f"{input_filename}_edited.mp4"
            output_path = self.outputs_dir / output_filename
            
            # Sauvegarde de la vidéo
            video.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=self.config['video_settings']['fps'],
                bitrate=self.config['video_settings']['bitrate']
            )
            
            # Sauvegarde des métadonnées
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            return output_path
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de la vidéo: {str(e)}")
            raise 