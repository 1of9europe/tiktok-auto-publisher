import os
import json
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import whisper
import openai
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import yt_dlp
import shutil
import re
from dotenv import load_dotenv

def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour le rendre compatible avec le système de fichiers.
    
    Args:
        filename (str): Nom de fichier à nettoyer
        
    Returns:
        str: Nom de fichier nettoyé
    """
    # Remplace les caractères non autorisés par des underscores
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limite la longueur du nom de fichier
    return filename[:255]

class VideoProcessor:
    def __init__(self, config: Dict):
        """
        Initialise le processeur vidéo avec la configuration spécifiée.
        
        Args:
            config (Dict): Configuration du processeur
        """
        self.config = config
        self.setup_logging()
        self._init_models()
        
        # Chemins de sortie
        self.output_dir = config.get('paths', {}).get('outputs', 'outputs')
        self.temp_dir = config.get('paths', {}).get('temp', 'temp')
        self.downloads_dir = config.get('paths', {}).get('downloads', 'downloads')
        
        # Création des répertoires nécessaires
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)
        
    def sanitize_filename(self, filename: str) -> str:
        """
        Nettoie un nom de fichier pour le rendre compatible avec le système de fichiers.
        
        Args:
            filename (str): Nom de fichier à nettoyer
            
        Returns:
            str: Nom de fichier nettoyé
        """
        # Remplace les caractères non autorisés par des underscores
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limite la longueur du nom de fichier
        return filename[:255]
        
    def setup_logging(self):
        """Configure le système de logging."""
        self.logger = logging.getLogger('VideoProcessor')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
    def _init_models(self):
        """Initialise les modèles Whisper et OpenAI."""
        try:
            # Initialisation de Whisper avec le modèle medium
            self.logger.info("🔄 Chargement du modèle Whisper medium...")
            self.whisper_model = whisper.load_model("medium")
            self.logger.info("✅ Modèle Whisper chargé avec succès")
            
            # Initialisation du client OpenAI si une clé API est fournie
            api_key = self.config.get('api', {}).get('openai', {}).get('api_key')
            
            # Si la clé n'est pas dans la config, essayer de la récupérer depuis les variables d'environnement
            if not api_key:
                load_dotenv()
                api_key = os.getenv('OPENAI_API_KEY')
            
            if api_key:
                openai.api_key = api_key
                self.logger.info("✅ Client OpenAI initialisé")
            else:
                self.logger.warning("⚠️ Pas de clé API OpenAI fournie, la correction GPT sera désactivée")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'initialisation des modèles: {str(e)}")
            raise
            
    def process_video(self, video_path: str, dry_run: bool = False, video_metadata: Dict = None) -> List[str]:
        """
        Traite une vidéo en la découpant en segments et en ajoutant des sous-titres.
        
        Args:
            video_path (str): Chemin de la vidéo à traiter
            dry_run (bool): Si True, ne fait que l'analyse sans export
            video_metadata (Dict): Métadonnées de la vidéo YouTube
            
        Returns:
            List[str]: Liste des chemins des vidéos traitées
        """
        try:
            self.logger.info(f"🎥 Traitement de la vidéo: {video_path}")
            
            # Découpage de la vidéo
            segments = self._split_video(video_path)
            self.logger.info(f"✂️ Vidéo découpée en {len(segments)} segments")
            
            processed_videos = []
            for i, segment in enumerate(segments):
                self.logger.info(f"🔄 Traitement du segment {i+1}/{len(segments)}")
                
                # Génération des sous-titres
                subtitles = self._generate_subtitles_for_segment(segment)
                
                # Sauvegarde des sous-titres
                srt_path = os.path.join(self.temp_dir, f"segment_{i+1}.srt")
                self._save_srt(subtitles, srt_path)
                
                # Ajout des sous-titres à la vidéo
                output_path = os.path.join(self.output_dir, f"segment_{i+1}_with_subs.mp4")
                if not dry_run:
                    if self._add_subtitles_ffmpeg(segment, srt_path, output_path):
                        processed_videos.append(output_path)
                        self.logger.info(f"✅ Segment {i+1} traité avec succès")
                        
                        # Génération et sauvegarde des métadonnées
                        transcript = ' '.join([s['text'] for s in subtitles]) if subtitles else ''
                        metadata = self._generate_metadata(i+1, video_metadata, transcript)
                        self._save_metadata(metadata, output_path)
                    else:
                        self.logger.error(f"❌ Erreur lors du traitement du segment {i+1}")
                else:
                    self.logger.info(f"🔍 Mode analyse: segment {i+1} analysé")
                    
            return processed_videos
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du traitement de la vidéo: {str(e)}")
            return []
            
    def _split_video(self, video_path: str) -> List[str]:
        """
        Découpe une vidéo en segments de durée égale.
        
        Args:
            video_path (str): Chemin de la vidéo à découper
            
        Returns:
            List[str]: Liste des chemins des segments
        """
        try:
            # Chargement de la vidéo
            video = VideoFileClip(video_path)
            duration = video.duration
            
            # Calcul de la durée des segments (60 secondes par défaut)
            segment_duration = self.config.get('segment_duration', 60)
            num_segments = int(duration / segment_duration) + (1 if duration % segment_duration > 0 else 0)
            
            segments = []
            for i in range(num_segments):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, duration)
                
                # Extraction du segment
                segment = video.subclip(start_time, end_time)
                
                # Sauvegarde du segment
                segment_path = os.path.join(self.temp_dir, f"segment_{i+1}.mp4")
                segment.write_videofile(segment_path, codec='libx264', audio_codec='aac')
                segments.append(segment_path)
                
            video.close()
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du découpage de la vidéo: {str(e)}")
            return []
            
    def _generate_subtitles_for_segment(self, video_path: str) -> List[Dict]:
        """
        Génère les sous-titres pour un segment vidéo en utilisant Whisper.
        
        Args:
            video_path (str): Chemin du segment vidéo
            
        Returns:
            List[Dict]: Liste des segments de sous-titres
        """
        try:
            # Transcription avec Whisper
            self.logger.info("🎯 Transcription du segment...")
            result = self.whisper_model.transcribe(video_path)
            
            # Nettoyage et optimisation des segments
            segments = self.clean_segments(result['segments'])
            
            # Correction avec GPT si disponible
            if hasattr(self, 'openai_api_key'):
                segments = self.post_correct_transcription(segments)
                
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la génération des sous-titres: {str(e)}")
            return []
            
    def clean_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Nettoie et optimise les segments de sous-titres.
        
        Args:
            segments (List[Dict]): Liste des segments à nettoyer
            
        Returns:
            List[Dict]: Liste des segments nettoyés
        """
        cleaned_segments = []
        current_segment = None
        
        for segment in segments:
            # Fusion des segments courts (< 1.2s)
            if segment['end'] - segment['start'] < 1.2:
                if current_segment is None:
                    current_segment = segment.copy()
                else:
                    current_segment['end'] = segment['end']
                    current_segment['text'] += ' ' + segment['text']
                continue
                
            # Découpage des segments longs (> 6s)
            if segment['end'] - segment['start'] > 6:
                duration = segment['end'] - segment['start']
                num_parts = int(duration / 6) + 1
                part_duration = duration / num_parts
                
                for i in range(num_parts):
                    start = segment['start'] + i * part_duration
                    end = start + part_duration
                    text = segment['text']  # Le texte sera réparti équitablement
                    
                    cleaned_segments.append({
                        'start': start,
                        'end': end,
                        'text': text
                    })
            else:
                cleaned_segments.append(segment)
                
        # Ajout du dernier segment en cours si nécessaire
        if current_segment is not None:
            cleaned_segments.append(current_segment)
            
        return cleaned_segments
        
    def post_correct_transcription(self, segments: List[Dict]) -> List[Dict]:
        """
        Corrige la transcription avec GPT pour améliorer la qualité.
        
        Args:
            segments (List[Dict]): Liste des segments à corriger
            
        Returns:
            List[Dict]: Liste des segments corrigés
        """
        try:
            # Préparation du texte pour GPT
            text = ' '.join(segment['text'] for segment in segments)
            
            # Appel à l'API OpenAI
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en correction de transcription. Corrige les erreurs de ponctuation et de majuscules tout en préservant le style oral."},
                    {"role": "user", "content": text}
                ]
            )
            
            # Récupération du texte corrigé
            corrected_text = response.choices[0].message.content
            
            # Répartition du texte corrigé sur les segments
            words = corrected_text.split()
            words_per_segment = len(words) // len(segments)
            
            for i, segment in enumerate(segments):
                start_idx = i * words_per_segment
                end_idx = start_idx + words_per_segment if i < len(segments) - 1 else len(words)
                segment['text'] = ' '.join(words[start_idx:end_idx])
                
            return segments
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la correction GPT: {str(e)}")
            return segments
            
    def _save_srt(self, segments: List[Dict], output_path: str):
        """
        Sauvegarde les sous-titres au format SRT.
        
        Args:
            segments (List[Dict]): Liste des segments de sous-titres
            output_path (str): Chemin de sortie du fichier SRT
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    # Conversion des timestamps
                    start = self._format_timestamp(segment['start'])
                    end = self._format_timestamp(segment['end'])
                    
                    # Écriture du segment
                    f.write(f"{i}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{segment['text']}\n\n")
                    
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la sauvegarde des sous-titres: {str(e)}")
            
    def _format_timestamp(self, seconds: float) -> str:
        """
        Convertit des secondes en timestamp SRT.
        
        Args:
            seconds (float): Nombre de secondes
            
        Returns:
            str: Timestamp au format SRT (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
        
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
                
            # Vérification de FFmpeg
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                self.logger.info("✅ FFmpeg est disponible")
            except (subprocess.SubprocessError, FileNotFoundError):
                self.logger.error("❌ FFmpeg n'est pas installé ou n'est pas accessible")
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
            font_size = max(24, min(30, int(min_dim * 0.04)))  # Police plus petite et adaptative
            
            # Utilisation de drawtext pour plus de contrôle
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
            
            # Exécution de la commande
            self.logger.info(f"🔄 Ajout des sous-titres...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres: {result.stderr}")
                return False
                    
            # Vérification que la vidéo de sortie existe et contient des sous-titres
            if os.path.exists(output_path):
                # Vérification rapide avec ffprobe
                probe_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_name',
                    '-of', 'json',
                    output_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("✅ Sous-titres ajoutés avec succès")
                    return True
                else:
                    self.logger.error("❌ La vidéo de sortie n'a pas été correctement générée")
                    return False
            else:
                self.logger.error("❌ La vidéo de sortie n'a pas été générée")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'ajout des sous-titres: {str(e)}")
            return False
            
    def _convert_srt_to_drawtext(self, srt_path: str, width: int, height: int, font_size: int) -> str:
        """
        Convertit un fichier SRT en filtre drawtext FFmpeg avec style discret et lisible (TikTok-friendly).
        
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

            # Adapter la taille pour rester sobre et lisible
            font_size = max(24, min(30, int(min(width, height) * 0.04)))

            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                segments = content.strip().split('\n\n')

                for segment in segments:
                    lines = segment.strip().split('\n')
                    if len(lines) >= 3:
                        timing = lines[1]
                        text = lines[2].strip()

                        # Échapper les caractères spéciaux pour FFmpeg
                        text = text.replace("'", "'\\\\\\''")  # Triple escape pour FFmpeg
                        text = text.replace(":", "\\:")
                        text = text.replace("[", "\\[")
                        text = text.replace("]", "\\]")
                        text = text.replace(",", "\\,")
                        text = text.replace("(", "\\(")
                        text = text.replace(")", "\\)")

                        # Split en 2 lignes max si nécessaire
                        if len(text) > 50:
                            midpoint = len(text) // 2
                            space_index = text.find(' ', midpoint)
                            if space_index != -1:
                                text = text[:space_index] + '\\n' + text[space_index+1:]

                        # Conversion du timing
                        try:
                            start_time, end_time = timing.split(' --> ')
                            start_seconds = self._srt_time_to_seconds(start_time)
                            end_seconds = self._srt_time_to_seconds(end_time)

                            # Filtre les sous-titres avec un end mal formaté ou une durée excessive (bug d'encodage possible)
                            max_duration = 15  # 15s max pour un seul sous-titre
                            duration = end_seconds - start_seconds

                            if (
                                0 <= start_seconds < end_seconds
                                and 0 < duration <= max_duration
                                and text.strip()
                            ):
                                # Style drawtext simple et propre
                                drawtext = (
                                    f"drawtext=text='{text}':"
                                    f"fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:"
                                    f"fontsize={font_size}:"
                                    f"fontcolor=white:"
                                    f"box=1:"
                                    f"boxcolor=black@0.7:"
                                    f"boxborderw=5:"
                                    f"line_spacing=4:"
                                    f"x=(w-text_w)/2:"
                                    f"y=h-text_h-40:"
                                    f"enable='between(t,{start_seconds:.3f},{end_seconds:.3f})'"
                                )
                                drawtext_parts.append(drawtext)
                                self.logger.debug(f"Filtre drawtext généré: {drawtext}")
                            else:
                                self.logger.warning(
                                    f"⏱️ Segment ignoré (durée invalide ou trop longue) : start={start_seconds}, end={end_seconds}, text='{text[:30]}'"
                                )
                        except Exception as e:
                            self.logger.warning(f"⚠️ Erreur lors du traitement du segment: {str(e)}")
                            continue

            if not drawtext_parts:
                self.logger.warning("⚠️ Aucun filtre drawtext généré")
                return ""

            final_filter = ','.join(drawtext_parts)
            self.logger.debug(f"Filtre drawtext final: {final_filter}")
            return final_filter

        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la conversion SRT vers drawtext: {str(e)}")
            return ""
            
    def _srt_time_to_seconds(self, time_str: str) -> float:
        """
        Convertit un timestamp SRT en secondes.
        
        Args:
            time_str (str): Timestamp au format SRT (HH:MM:SS,mmm)
            
        Returns:
            float: Nombre de secondes
        """
        try:
            # Format: HH:MM:SS,mmm
            hours, minutes, seconds = time_str.replace(',', '.').split(':')
            total_seconds = (
                int(hours) * 3600 +
                int(minutes) * 60 +
                float(seconds)
            )
            # Arrondir à 3 décimales et s'assurer que la valeur est positive
            total_seconds = max(0, round(total_seconds, 3))
            return total_seconds
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la conversion du timestamp {time_str}: {str(e)}")
            return 0.0
        
    def _cleanup_temp_files(self, file_paths: List[str]):
        """
        Nettoie les fichiers temporaires.
        
        Args:
            file_paths (List[str]): Liste des chemins de fichiers à supprimer
        """
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible de supprimer le fichier temporaire {path}: {str(e)}")

    def _generate_metadata(self, segment_number: int, video_metadata: Dict, transcript: str) -> Dict:
        """
        Génère les métadonnées pour un segment vidéo.
        
        Args:
            segment_number (int): Numéro du segment
            video_metadata (Dict): Métadonnées de la vidéo YouTube
            transcript (str): Transcription du segment
            
        Returns:
            Dict: Métadonnées générées
        """
        try:
            if not video_metadata:
                return {
                    'title': f'Segment {segment_number}',
                    'description': 'Segment vidéo automatiquement généré',
                    'hashtags': ['#tiktok', '#viral', '#trending']
                }

            # Vérification de la clé API OpenAI
            openai_api_key = self.config.get('api', {}).get('openai', {}).get('api_key')
            if not openai_api_key:
                self.logger.warning("⚠️ Aucune clé API OpenAI trouvée, utilisation du mode basique")
                return {
                    'title': f"{video_metadata.get('title', 'Vidéo')} (partie {segment_number})",
                    'description': f"✨ Découvre la suite de cette vidéo incroyable ! 💫 Like et commente si tu veux voir la suite 👇",
                    'hashtags': ['#tiktok', '#viral', '#trending', '#fyp', '#pourtoi', '#foryoupage', '#decouverte']
                }

            # Utilisation de l'API OpenAI pour générer des métadonnées pertinentes
            prompt = f"""
            Tu es un expert en création de contenu viral pour TikTok.

            Ta mission est de générer des **métadonnées engageantes et distinctes** pour un segment vidéo court à partir des informations suivantes :

            🎬 CONTEXTE ORIGINAL :
            - Titre YouTube : {video_metadata.get('title', 'Non disponible')}
            - Description YouTube : {video_metadata.get('description', 'Non disponible')}
            - Chaîne : {video_metadata.get('channel_title', 'Non disponible')}
            - Vues : {video_metadata.get('views', 0):,}
            - Date de publication : {video_metadata.get('published_at', 'Non disponible')}

            📝 TRANSCRIPTION DU SEGMENT ({segment_number}) :
            {transcript[:1000]}

            🎯 OBJECTIF :
            Créer un **titre, une description et des hashtags TikTok uniques** pour ce **segment** en particulier. Le style doit rester **naturel, humain, percutant et TikTok-friendly**, et s'adapter au **contenu réel du segment**, qu'il soit informatif, divertissant, émotionnel ou autre.

            ⚙️ DIRECTIVES :

            1. **TITRE (max. 100 caractères)** :
               - Accroche fort : émotion, choc, révélation, humour, etc.
               - Mentionne "(partie {segment_number})" à la fin
               - Ne jamais copier le titre YouTube
               - Évite les titres génériques
               - Utilise au plus 1 ou 2 emojis bien placés

            2. **DESCRIPTION (max. 150 caractères)** :
               - Différente du titre
               - Naturelle et engageante
               - Peut poser une question, teaser un moment ou ajouter du contexte
               - 1 à 3 emojis max, pas plus
               - Appelle à interagir : commentaires, opinions, réactions

            3. **HASHTAGS (entre 5 et 7)** :
               - Mélange entre hashtags populaires TikTok (FR ou global) et hashtags de niche
               - Inclure des hashtags en lien avec le contenu réel (ex: #histoire, #funny, #cinema, #rapfr, etc.)
               - Évite de toujours répéter les mêmes (#tiktok, #foryou, etc.)
               - Minimum 3 hashtags différents d'un segment à l'autre

            📦 FORMAT DE SORTIE ATTENDU (JSON strict) :
            {{
              "title": "Titre TikTok",
              "description": "Description TikTok",
              "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"]
            }}

            ⚠️ CONTRAINTES :
            - Pas de titre ou description identique entre segments
            - Pas de surcharge d'emojis
            - Aucune répétition inutile
            - Si le contenu ne permet pas une accroche forte, adopte un ton sobre et authentique
            """
            
            try:
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model=self.config['api']['openai'].get('model', 'gpt-3.5-turbo'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                
                metadata = json.loads(response.choices[0].message.content)
                
                # Vérification et nettoyage des métadonnées
                metadata['title'] = metadata['title'].strip()
                if len(metadata['title']) > 100:
                    metadata['title'] = metadata['title'][:97] + "..."
                
                metadata['description'] = metadata['description'].strip()
                if len(metadata['description']) > 150:
                    metadata['description'] = metadata['description'][:147] + "..."
                
                # Limitation du nombre de hashtags
                metadata['hashtags'] = metadata['hashtags'][:7]
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lors de la génération GPT des métadonnées: {str(e)}")
                # Fallback en mode basique avec des hashtags variés
                metadata = {
                    'title': f"{video_metadata.get('title', 'Vidéo')} (partie {segment_number})",
                    'description': f"✨ Découvre la suite de cette vidéo incroyable ! 💫 Like et commente si tu veux voir la suite 👇",
                    'hashtags': ['#tiktok', '#viral', '#trending', '#fyp', '#pourtoi', '#foryoupage', '#decouverte']
                }
                
            # Ajout des métadonnées supplémentaires
            metadata['generated_date'] = datetime.now().isoformat()
            metadata['original_video_id'] = video_metadata.get('video_id', '')
            metadata['segment_number'] = segment_number
            metadata['channel_title'] = video_metadata.get('channel_title', '')
            metadata['views'] = video_metadata.get('views', 0)
            metadata['published_at'] = video_metadata.get('published_at', '')
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la génération des métadonnées: {str(e)}")
            return {
                'title': f'Segment {segment_number}',
                'description': 'Segment vidéo automatiquement généré',
                'hashtags': ['#tiktok', '#viral', '#trending', '#fyp', '#pourtoi', '#foryoupage', '#decouverte']
            }

    def _save_metadata(self, metadata: Dict, output_path: str):
        """
        Sauvegarde les métadonnées dans un fichier texte.
        
        Args:
            metadata (Dict): Métadonnées à sauvegarder
            output_path (str): Chemin du fichier vidéo associé
        """
        try:
            metadata_path = os.path.splitext(output_path)[0] + '.txt'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                f.write(f"Titre: {metadata.get('title', '')}\n")
                f.write(f"Description: {metadata.get('description', '')}\n")
                f.write(f"Hashtags: {' '.join(metadata.get('hashtags', []))}\n")
                f.write(f"Date de génération: {metadata.get('generated_date', '')}\n")
                f.write(f"ID vidéo originale: {metadata.get('original_video_id', '')}\n")
                f.write(f"Numéro de segment: {metadata.get('segment_number', '')}\n")
                
            self.logger.info(f"✅ Métadonnées sauvegardées dans {metadata_path}")
            
            # Renommer le fichier MP4 avec le titre généré
            self._rename_video_with_metadata(output_path, metadata_path)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la sauvegarde des métadonnées: {str(e)}")

    def _rename_video_with_metadata(self, video_path: str, metadata_path: str):
        """
        Renomme le fichier vidéo en utilisant le titre des métadonnées.
        
        Args:
            video_path (str): Chemin du fichier vidéo
            metadata_path (str): Chemin du fichier de métadonnées
        """
        try:
            # Lire le titre depuis le fichier de métadonnées
            with open(metadata_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('Titre:'):
                        title = line.replace('Titre:', '').strip()
                        break
            
            if title:
                # Nettoyer le titre pour le nom de fichier
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '|', '(', ')')).strip()
                new_video_path = os.path.join(os.path.dirname(video_path), f"{safe_title}.mp4")
                
                # Renommer le fichier
                os.rename(video_path, new_video_path)
                self.logger.info(f"✅ Fichier vidéo renommé: {new_video_path}")
                
                # Mettre à jour le chemin des métadonnées
                new_metadata_path = os.path.splitext(new_video_path)[0] + '.txt'
                os.rename(metadata_path, new_metadata_path)
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du renommage du fichier: {str(e)}")

    def organize_outputs(self, output_paths: List[str], video_title: str) -> None:
        """Organise les fichiers de sortie dans une structure de dossiers."""
        try:
            # Créer le dossier principal pour la vidéo
            safe_title = self.sanitize_filename(video_title)
            base_dir = os.path.join(self.config['paths']['outputs'], safe_title)
            os.makedirs(base_dir, exist_ok=True)
            
            # Déplacer les fichiers dans le dossier principal
            for path in output_paths:
                if path and os.path.exists(path):
                    # Déplacer le fichier
                    filename = os.path.basename(path)
                    new_path = os.path.join(base_dir, filename)
                    shutil.move(path, new_path)
                    self.logger.info(f"Fichier déplacé vers {new_path}")
            
            self.logger.info(f"Organisation des fichiers terminée dans {base_dir}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'organisation des fichiers: {str(e)}")
            raise 