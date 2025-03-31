import cv2
import numpy as np
import librosa
import logging
from pathlib import Path
from typing import Dict, Tuple
import json
from datetime import datetime
from moviepy.editor import VideoFileClip

class QualityChecker:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        self.thresholds = config['quality_thresholds']
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('QualityChecker')
        
    def check_video(self, video_path: str) -> Dict:
        """
        Vérifie la qualité d'une vidéo
        Args:
            video_path (str): Chemin vers la vidéo à vérifier
        Returns:
            Dict: Résultats de l'analyse de qualité
        """
        try:
            self.logger.info(f"Vérification de la qualité de la vidéo: {video_path}")
            
            # Analyse vidéo
            visual_metrics = self._analyze_visual_quality(video_path)
            
            # Analyse audio
            audio_metrics = self._analyze_audio_quality(video_path)
            
            # Compilation des résultats
            results = {
                'video_path': video_path,
                'timestamp': datetime.now().isoformat(),
                'visual_quality': visual_metrics,
                'audio_quality': audio_metrics,
                'overall_quality': self._calculate_overall_quality(visual_metrics, audio_metrics)
            }
            
            # Sauvegarde des résultats
            self._save_results(results, video_path)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de la vidéo: {str(e)}")
            raise
            
    def _analyze_visual_quality(self, video_path: str) -> Dict:
        """
        Analyse la qualité visuelle de la vidéo
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError("Impossible d'ouvrir la vidéo")
                
            frame_count = 0
            brightness_values = []
            contrast_values = []
            blur_values = []
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Analyse tous les 30 frames pour optimiser les performances
                if frame_count % 30 == 0:
                    # Mesure de la luminosité
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    brightness = np.mean(hsv[:, :, 2]) / 255.0
                    brightness_values.append(brightness)
                    
                    # Mesure du contraste
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    contrast = np.std(gray) / 255.0
                    contrast_values.append(contrast)
                    
                    # Mesure du flou
                    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                    blur = np.var(laplacian)
                    blur_values.append(blur)
                    
                frame_count += 1
                
            cap.release()
            
            # Calcul des moyennes
            avg_brightness = np.mean(brightness_values)
            avg_contrast = np.mean(contrast_values)
            avg_blur = np.mean(blur_values)
            
            # Évaluation de la qualité
            quality_scores = {
                'brightness': {
                    'value': float(avg_brightness),
                    'status': 'good' if self.thresholds['min_brightness'] <= avg_brightness <= self.thresholds['max_brightness'] else 'poor'
                },
                'contrast': {
                    'value': float(avg_contrast),
                    'status': 'good' if avg_contrast >= self.thresholds['min_contrast'] else 'poor'
                },
                'sharpness': {
                    'value': float(avg_blur),
                    'status': 'good' if avg_blur >= 100 else 'poor'
                }
            }
            
            return quality_scores
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse visuelle: {str(e)}")
            raise
            
    def _analyze_audio_quality(self, video_path: str) -> Dict:
        """
        Analyse la qualité audio de la vidéo
        """
        try:
            # Extraction de l'audio avec moviepy
            video = VideoFileClip(video_path)
            
            if video.audio is None:
                return {
                    'status': 'no_audio',
                    'message': 'Pas de piste audio détectée'
                }
                
            # Sauvegarde temporaire de l'audio
            temp_audio = Path(video_path).with_suffix('.wav')
            video.audio.write_audiofile(str(temp_audio))
            
            # Chargement avec librosa
            y, sr = librosa.load(str(temp_audio))
            
            # Suppression du fichier temporaire
            temp_audio.unlink()
            
            # Calcul des métriques audio
            rms = librosa.feature.rms(y=y)[0]
            db = 20 * np.log10(np.mean(rms))
            
            # Détection du bruit
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            noise_level = np.mean(spectral_rolloff)
            
            quality_scores = {
                'volume': {
                    'value': float(db),
                    'status': 'good' if self.thresholds['min_audio_db'] <= db <= self.thresholds['max_audio_db'] else 'poor'
                },
                'noise': {
                    'value': float(noise_level),
                    'status': 'good' if noise_level < 0.85 else 'poor'
                }
            }
            
            return quality_scores
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse audio: {str(e)}")
            raise
            
    def _calculate_overall_quality(self, visual_metrics: Dict, audio_metrics: Dict) -> Dict:
        """
        Calcule la qualité globale de la vidéo
        """
        try:
            # Compte des métriques "good"
            total_metrics = 0
            good_metrics = 0
            
            for metric in visual_metrics.values():
                if isinstance(metric, dict) and 'status' in metric:
                    total_metrics += 1
                    if metric['status'] == 'good':
                        good_metrics += 1
                        
            for metric in audio_metrics.values():
                if isinstance(metric, dict) and 'status' in metric:
                    total_metrics += 1
                    if metric['status'] == 'good':
                        good_metrics += 1
                        
            quality_score = good_metrics / total_metrics if total_metrics > 0 else 0
            
            return {
                'score': quality_score,
                'status': 'good' if quality_score >= 0.7 else 'poor',
                'message': f"Score de qualité: {quality_score:.2f}"
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors du calcul de la qualité globale: {str(e)}")
            raise
            
    def _save_results(self, results: Dict, video_path: str):
        """
        Sauvegarde les résultats de l'analyse
        """
        try:
            output_path = Path(video_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Rapport de qualité sauvegardé dans {output_path}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des résultats: {str(e)}")
            raise 