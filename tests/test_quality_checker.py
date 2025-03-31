import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from QualityChecker.quality_checker import QualityChecker
import numpy as np
from pathlib import Path
import cv2
import json
import os
import librosa

@pytest.fixture
def test_config():
    """Fixture pour la configuration de test"""
    return {
        'quality_thresholds': {
            'min_duration': 15,
            'max_duration': 60,
            'min_fps': 24,
            'min_resolution': (720, 1280),
            'min_brightness': 0.3,
            'max_brightness': 0.8,
            'min_contrast': 0.4,
            'min_audio_db': -20,
            'max_audio_db': 0
        }
    }

@pytest.fixture
def test_video_path():
    """Fixture pour le chemin de la vidéo de test"""
    return str(Path(__file__).parent / "video" / "test.mp4")

@pytest.fixture
def quality_checker(test_config):
    """Fixture pour l'instance de QualityChecker"""
    return QualityChecker(test_config)

class TestQualityChecker:
    """Tests pour la classe QualityChecker"""

    def test_init(self, quality_checker, test_config):
        """Test l'initialisation"""
        assert quality_checker.config == test_config
        assert quality_checker.thresholds == test_config['quality_thresholds']

    def test_check_video(self, quality_checker, test_video_path):
        """Test la vérification complète d'une vidéo"""
        with patch.object(quality_checker, '_analyze_visual_quality') as mock_visual:
            with patch.object(quality_checker, '_analyze_audio_quality') as mock_audio:
                mock_visual.return_value = {
                    'brightness': {'value': 0.5, 'status': 'good'},
                    'contrast': {'value': 0.6, 'status': 'good'},
                    'sharpness': {'value': 150, 'status': 'good'}
                }
                mock_audio.return_value = {
                    'volume': {'value': -10, 'status': 'good'},
                    'noise': {'value': 0.5, 'status': 'good'}
                }
                
                results = quality_checker.check_video(test_video_path)

                assert isinstance(results, dict)
                assert 'visual_quality' in results
                assert 'audio_quality' in results
                assert 'overall_quality' in results

    def test_analyze_audio_quality(self, quality_checker, test_video_path):
        """Test l'analyse de la qualité audio"""
        with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
            # Mock pour VideoFileClip
            mock_instance = MagicMock()
            mock_instance.audio = MagicMock()
            mock_instance.audio.write_audiofile.return_value = None
            mock_video_clip.return_value = mock_instance

            # Mock pour librosa
            with patch('librosa.load') as mock_load:
                mock_load.return_value = (np.zeros(1000), 44100)
                with patch('librosa.feature.rms') as mock_rms:
                    mock_rms.return_value = [np.array([0.1])]
                    with patch('librosa.feature.spectral_rolloff') as mock_rolloff:
                        mock_rolloff.return_value = np.array([0.5])
                        
                        # Mock pour Path
                        with patch('pathlib.Path') as mock_path:
                            mock_path_instance = MagicMock()
                            mock_path_instance.with_suffix.return_value = mock_path_instance
                            mock_path_instance.unlink.return_value = None
                            mock_path.return_value = mock_path_instance
                            
                            metrics = quality_checker._analyze_audio_quality(test_video_path)

                            assert isinstance(metrics, dict)
                            assert 'volume' in metrics
                            assert 'noise' in metrics
                            assert all('value' in m and 'status' in m for m in metrics.values())

    def test_analyze_visual_quality(self, quality_checker, test_video_path):
        """Test l'analyse de la qualité visuelle"""
        with patch('cv2.VideoCapture') as mock_capture:
            # Mock pour VideoCapture
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (True, np.uint8(np.zeros((100, 100, 3))))
            mock_capture.return_value = mock_instance
            
            metrics = quality_checker._analyze_visual_quality(test_video_path)
            
            assert isinstance(metrics, dict)
            assert 'brightness' in metrics
            assert 'contrast' in metrics
            assert 'sharpness' in metrics
            assert all('value' in m and 'status' in m for m in metrics.values())

    def test_calculate_overall_quality(self, quality_checker):
        """Test le calcul de la qualité globale"""
        visual_metrics = {
            'brightness': {'value': 0.5, 'status': 'good'},
            'contrast': {'value': 0.6, 'status': 'good'},
            'sharpness': {'value': 150, 'status': 'good'}
        }
        audio_metrics = {
            'volume': {'value': -10, 'status': 'good'},
            'noise': {'value': 0.5, 'status': 'good'}
        }

        result = quality_checker._calculate_overall_quality(visual_metrics, audio_metrics)
        assert isinstance(result, dict)
        assert 'score' in result
        assert 0 <= result['score'] <= 1

    def test_save_results(self, quality_checker, tmp_path):
        """Test la sauvegarde des résultats"""
        results = {
            'visual_quality': {
                'brightness': {'value': 0.5, 'status': 'good'},
                'contrast': {'value': 0.6, 'status': 'good'},
                'sharpness': {'value': 150, 'status': 'good'}
            },
            'audio_quality': {
                'volume': {'value': -10, 'status': 'good'},
                'noise': {'value': 0.5, 'status': 'good'}
            },
            'overall_quality': {'score': 0.8, 'status': 'good'}
        }

        output_path = tmp_path / "results.json"
        quality_checker._save_results(results, str(output_path))
        assert output_path.exists()
        
        # Vérifier le contenu du fichier
        with open(output_path, 'r') as f:
            saved_results = json.load(f)
            assert saved_results == results

    def test_error_handling(self, quality_checker):
        """Test la gestion des erreurs"""
        # Test d'erreur lors de l'ouverture de la vidéo
        with patch('cv2.VideoCapture') as mock_capture:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_capture.return_value = mock_instance
            
            with pytest.raises(ValueError, match="Impossible d'ouvrir la vidéo"):
                quality_checker._analyze_visual_quality('nonexistent.mp4')

        # Test d'erreur avec une vidéo sans audio
        with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
            mock_instance = MagicMock()
            mock_instance.audio = None
            mock_video_clip.return_value = mock_instance
            
            result = quality_checker._analyze_audio_quality('nonexistent.mp4')
            assert result['status'] == 'no_audio' 