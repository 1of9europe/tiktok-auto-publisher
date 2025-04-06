import os
import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

class VideoEncoder:
    """
    Classe dédiée à l'encodage vidéo optimisé pour TikTok avec FFmpeg.
    Gère l'analyse vidéo, le redimensionnement et l'encodage avec des paramètres optimisés.
    """
    
    def __init__(self, config: Dict):
        """
        Initialise l'encodeur vidéo avec la configuration.
        
        Args:
            config (Dict): Configuration du système
        """
        self.config = config
        self.setup_logging()
        
        # Paramètres d'encodage par défaut
        self.preset = config.get('video_settings', {}).get('ffmpeg_preset', 'medium')
        self.crf = config.get('video_settings', {}).get('ffmpeg_crf', 23)
        self.bitrate = config.get('video_settings', {}).get('ffmpeg_bitrate', '2M')
        self.audio_bitrate = config.get('video_settings', {}).get('ffmpeg_audio_bitrate', '128k')
        self.max_size = config.get('video_settings', {}).get('max_file_size_mb', 287)  # Limite TikTok
        
    def setup_logging(self):
        """Configure le système de logging."""
        self.logger = logging.getLogger('VideoEncoder')
        
    def analyze_video(self, video_path: str) -> Dict:
        """
        Analyse une vidéo avec FFprobe pour obtenir ses métadonnées.
        
        Args:
            video_path (str): Chemin de la vidéo
            
        Returns:
            Dict: Métadonnées de la vidéo
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors de l'analyse de la vidéo: {result.stderr}")
                return {}
                
            data = json.loads(result.stdout)
            
            # Extraction des informations pertinentes
            video_stream = next((s for s in data.get('streams', []) if s['codec_type'] == 'video'), {})
            audio_stream = next((s for s in data.get('streams', []) if s['codec_type'] == 'audio'), {})
            
            info = {
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'duration': float(data.get('format', {}).get('duration', 0)),
                'bitrate': int(data.get('format', {}).get('bit_rate', 0)),
                'size': int(data.get('format', {}).get('size', 0)),
                'video_codec': video_stream.get('codec_name', ''),
                'audio_codec': audio_stream.get('codec_name', ''),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'has_audio': bool(audio_stream)
            }
            
            self.logger.info(f"📊 Analyse vidéo: {info['width']}x{info['height']}, {info['duration']:.2f}s, {info['fps']:.2f}fps")
            return info
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'analyse: {str(e)}")
            return {}
            
    def reencode_video(self, input_path: str, output_path: str) -> bool:
        """
        Réencode une vidéo avec FFmpeg en utilisant des paramètres optimisés pour TikTok.
        
        Args:
            input_path (str): Chemin de la vidéo d'entrée
            output_path (str): Chemin de la vidéo de sortie
            
        Returns:
            bool: True si l'encodage a réussi, False sinon
        """
        try:
            # Analyse de la vidéo source
            info = self.analyze_video(input_path)
            if not info:
                return False
                
            # Construction de la commande FFmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Écraser le fichier de sortie
                '-i', input_path,
                '-c:v', 'libx264',  # Codec vidéo
                '-preset', self.preset,  # Vitesse d'encodage
                '-crf', str(self.crf),  # Qualité
                '-b:v', self.bitrate,  # Bitrate vidéo
                '-maxrate', f"{int(self.bitrate[:-1]) * 1.5}M",  # Bitrate maximum
                '-bufsize', f"{int(self.bitrate[:-1]) * 2}M",  # Taille du buffer
                '-movflags', '+faststart',  # Optimisation pour le streaming
                '-pix_fmt', 'yuv420p',  # Format de pixel compatible
                '-profile:v', 'high',  # Profil H.264
                '-level', '4.1',  # Niveau H.264
                '-g', '30',  # GOP size
                '-keyint_min', '30',  # Intervalle minimum des images clés
                '-sc_threshold', '0',  # Désactive la détection de changement de scène
                '-threads', '0',  # Utilise tous les threads disponibles
                '-c:a', 'aac',  # Codec audio
                '-b:a', self.audio_bitrate,  # Bitrate audio
                '-ar', '48000',  # Taux d'échantillonnage audio
                '-ac', '2',  # Nombre de canaux audio
                output_path
            ]
            
            # Exécution de l'encodage
            self.logger.info("🔄 Début de l'encodage FFmpeg...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors de l'encodage: {result.stderr}")
                return False
                
            # Vérification de la taille du fichier
            output_size = os.path.getsize(output_path) / (1024 * 1024)  # Taille en MB
            if output_size > self.max_size:
                self.logger.warning(f"⚠️ Fichier trop volumineux ({output_size:.1f}MB > {self.max_size}MB)")
                # Tentative de réduction de la taille
                return self._reduce_file_size(output_path)
                
            self.logger.info(f"✅ Encodage terminé: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'encodage: {str(e)}")
            return False
            
    def _reduce_file_size(self, video_path: str) -> bool:
        """
        Réduit la taille d'un fichier vidéo en ajustant le bitrate.
        
        Args:
            video_path (str): Chemin de la vidéo
            
        Returns:
            bool: True si la réduction a réussi, False sinon
        """
        try:
            # Analyse de la vidéo
            info = self.analyze_video(video_path)
            if not info:
                return False
                
            # Calcul du nouveau bitrate
            current_size = info['size'] / (1024 * 1024)  # Taille en MB
            target_size = self.max_size * 0.95  # 95% de la limite
            duration = info['duration']
            
            # Nouveau bitrate en kbps
            new_bitrate = int((target_size * 8192) / duration)  # 8192 = 8 * 1024 (conversion MB -> kbps)
            
            # Fichier temporaire
            temp_path = f"{video_path}.temp.mp4"
            
            # Commande FFmpeg avec nouveau bitrate
            cmd = [
                'ffmpeg',
                '-y',
                '-i', video_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-b:v', f"{new_bitrate}k",
                '-maxrate', f"{int(new_bitrate * 1.5)}k",
                '-bufsize', f"{new_bitrate * 2}k",
                '-c:a', 'aac',
                '-b:a', '96k',
                temp_path
            ]
            
            # Exécution
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors de la réduction: {result.stderr}")
                return False
                
            # Remplacement du fichier original
            os.replace(temp_path, video_path)
            
            # Vérification finale
            final_size = os.path.getsize(video_path) / (1024 * 1024)
            self.logger.info(f"✅ Taille réduite: {current_size:.1f}MB -> {final_size:.1f}MB")
            
            return final_size <= self.max_size
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la réduction: {str(e)}")
            return False
            
    def resize_video(self, input_path: str, output_path: str, target_width: int, target_height: int) -> bool:
        """
        Redimensionne une vidéo aux dimensions cibles.
        
        Args:
            input_path (str): Chemin de la vidéo d'entrée
            output_path (str): Chemin de la vidéo de sortie
            target_width (int): Largeur cible
            target_height (int): Hauteur cible
            
        Returns:
            bool: True si le redimensionnement a réussi, False sinon
        """
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-preset', self.preset,
                '-crf', str(self.crf),
                '-c:a', 'aac',
                '-b:a', self.audio_bitrate,
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"❌ Erreur lors du redimensionnement: {result.stderr}")
                return False
                
            self.logger.info(f"✅ Redimensionnement terminé: {target_width}x{target_height}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du redimensionnement: {str(e)}")
            return False 