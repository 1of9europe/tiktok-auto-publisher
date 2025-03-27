import pytest
from unittest.mock import patch, MagicMock
from QualityChecker.quality_checker import QualityChecker
import numpy as np
from pathlib import Path
import cv2
import json

class TestQualityChecker:
    @pytest.fixture
    def quality_checker(self, test_config):
        return QualityChecker(test_config)
    
    @pytest.fixture
    def mock_video_frame(self):
        # Création d'une frame de test
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[:] = 128  # Luminosité moyenne
        return frame
    
    @pytest.fixture
    def mock_audio_data(self):
        # Création de données audio de test
        return np.random.rand(44100 * 2)  # 2 secondes d'audio
    
    def test_init(self, quality_checker, test_config):
        """Test l'initialisation de QualityChecker"""
        assert quality_checker.config == test_config
        assert quality_checker.logger is not None
        assert quality_checker.thresholds == test_config['quality_thresholds']
        
    @patch('cv2.VideoCapture')
    @patch('moviepy.editor.VideoFileClip')
    def test_check_video(self, mock_video_clip, mock_video_capture, quality_checker):
        """Test la vérification complète d'une vidéo"""
        # Configuration des mocks
        mock_video_capture.return_value.isOpened.return_value = True
        mock_video_capture.return_value.read.side_effect = [(True, np.zeros((1080, 1920, 3))), (False, None)]
        
        mock_video_clip.return_value.audio = MagicMock()
        
        with patch.object(quality_checker, '_analyze_audio_quality', return_value={'status': 'good'}):
            results = quality_checker.check_video('test_video.mp4')
            
            assert results['video_path'] == 'test_video.mp4'
            assert 'visual_quality' in results
            assert 'audio_quality' in results
            assert 'overall_quality' in results
            
    def test_analyze_visual_quality(self, quality_checker, mock_video_frame):
        """Test l'analyse de la qualité visuelle"""
        with patch('cv2.VideoCapture') as mock_capture:
            # Configuration du mock pour retourner notre frame de test
            mock_capture.return_value.isOpened.return_value = True
            mock_capture.return_value.read.side_effect = [(True, mock_video_frame), (False, None)]
            
            metrics = quality_checker._analyze_visual_quality('test_video.mp4')
            
            assert 'brightness' in metrics
            assert 'contrast' in metrics
            assert 'sharpness' in metrics
            assert all(m['status'] in ['good', 'poor'] for m in metrics.values())
            
    @patch('moviepy.editor.VideoFileClip')
    def test_analyze_audio_quality(self, mock_video_clip, quality_checker, mock_audio_data):
        """Test l'analyse de la qualité audio"""
        # Configuration du mock
        mock_video_clip.return_value.audio = MagicMock()
        
        with patch('librosa.load', return_value=(mock_audio_data, 44100)):
            with patch('librosa.feature.rms', return_value=np.array([[0.1]])):
                with patch('librosa.feature.spectral_rolloff', return_value=np.array([[0.5]])):
                    metrics = quality_checker._analyze_audio_quality('test_video.mp4')
                    
                    assert 'volume' in metrics
                    assert 'noise' in metrics
                    assert all(m['status'] in ['good', 'poor'] for m in metrics.values())
                    
    def test_calculate_overall_quality(self, quality_checker):
        """Test le calcul de la qualité globale"""
        visual_metrics = {
            'brightness': {'status': 'good'},
            'contrast': {'status': 'poor'},
            'sharpness': {'status': 'good'}
        }
        
        audio_metrics = {
            'volume': {'status': 'good'},
            'noise': {'status': 'good'}
        }
        
        result = quality_checker._calculate_overall_quality(visual_metrics, audio_metrics)
        
        assert 'score' in result
        assert 'status' in result
        assert 'message' in result
        assert 0 <= result['score'] <= 1
        
    def test_save_results(self, quality_checker, tmp_path):
        """Test la sauvegarde des résultats"""
        # Configuration du chemin temporaire
        test_results = {
            'video_path': 'test_video.mp4',
            'visual_quality': {'brightness': {'status': 'good'}},
            'audio_quality': {'volume': {'status': 'good'}},
            'overall_quality': {'score': 0.8, 'status': 'good'}
        }
        
        # Test de la sauvegarde
        quality_checker._save_results(test_results, str(tmp_path / 'test_video.mp4'))
        
        # Vérification
        quality_reports_dir = tmp_path / 'quality_reports'
        assert quality_reports_dir.exists()
        assert len(list(quality_reports_dir.glob('*.json'))) == 1
        
    def test_error_handling(self, quality_checker):
        """Test la gestion des erreurs"""
        # Test d'erreur lors de l'ouverture de la vidéo
        with patch('cv2.VideoCapture') as mock_capture:
            mock_capture.return_value.isOpened.return_value = False
            
            with pytest.raises(ValueError):
                quality_checker._analyze_visual_quality('nonexistent.mp4')
                
        # Test d'erreur lors de l'analyse audio
        with patch('moviepy.editor.VideoFileClip') as mock_clip:
            mock_clip.return_value.audio = None
            
            result = quality_checker._analyze_audio_quality('test_video.mp4')
            assert result['status'] == 'no_audio'

def test_init(test_config):
    checker = QualityChecker(test_config)
    assert checker.config is not None
    assert checker.logger is not None
    assert checker.thresholds is not None

@patch('cv2.VideoCapture')
@patch('moviepy.editor.VideoFileClip')
def test_check_video(mock_video_clip, mock_video_capture, test_config, sample_video_path):
    # Simuler une vidéo valide
    mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    mock_video_capture.return_value.read.return_value = (True, mock_frame)
    mock_video_capture.return_value.get.return_value = 30  # fps
    
    mock_audio = np.zeros(44100)  # 1 seconde d'audio
    mock_video_clip.return_value.audio.to_soundarray.return_value = mock_audio
    
    checker = QualityChecker(test_config)
    results = checker.check_video(sample_video_path)
    
    assert results["video_path"] == sample_video_path
    assert "visual_quality" in results
    assert "audio_quality" in results
    assert "overall_quality" in results

@patch('cv2.VideoCapture')
def test_analyze_visual_quality(mock_video_capture, test_config):
    # Simuler une frame de test
    mock_frame = np.ones((1080, 1920, 3), dtype=np.uint8) * 128
    mock_video_capture.return_value.read.return_value = (True, mock_frame)
    
    checker = QualityChecker(test_config)
    metrics = checker._analyze_visual_quality("test.mp4")
    
    assert "brightness" in metrics
    assert "contrast" in metrics
    assert "blur" in metrics
    assert all(metric["status"] == "good" for metric in metrics.values())

@patch('moviepy.editor.VideoFileClip')
def test_analyze_audio_quality(mock_video_clip, test_config):
    # Simuler des données audio
    mock_audio = np.ones(44100) * 0.5  # 1 seconde d'audio
    mock_video_clip.return_value.audio.to_soundarray.return_value = mock_audio
    
    checker = QualityChecker(test_config)
    metrics = checker._analyze_audio_quality("test.mp4")
    
    assert "volume" in metrics
    assert "noise" in metrics
    assert all(metric["status"] == "good" for metric in metrics.values())

def test_calculate_overall_quality(test_config):
    checker = QualityChecker(test_config)
    
    visual_metrics = {
        "brightness": {"score": 0.8, "status": "good"},
        "contrast": {"score": 0.7, "status": "good"},
        "blur": {"score": 0.9, "status": "good"}
    }
    
    audio_metrics = {
        "volume": {"score": 0.8, "status": "good"},
        "noise": {"score": 0.9, "status": "good"}
    }
    
    result = checker._calculate_overall_quality(visual_metrics, audio_metrics)
    
    assert "score" in result
    assert "status" in result
    assert "message" in result
    assert 0 <= result["score"] <= 1

def test_save_results(test_config, setup_test_environment):
    checker = QualityChecker(test_config)
    results = {
        "video_path": "test.mp4",
        "visual_quality": {"brightness": {"score": 0.8}},
        "audio_quality": {"volume": {"score": 0.7}},
        "overall_quality": {"score": 0.75}
    }
    
    report_path = Path(setup_test_environment["reports"]) / "quality_report.json"
    checker._save_results(results, report_path)
    
    assert report_path.exists()
    with open(report_path) as f:
        saved_data = json.load(f)
    assert saved_data == results

def test_error_handling(test_config):
    checker = QualityChecker(test_config)
    
    # Test avec une vidéo qui ne peut pas être ouverte
    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_video_capture.return_value.isOpened.return_value = False
        with pytest.raises(ValueError, match="Impossible d'ouvrir la vidéo"):
            checker.check_video("nonexistent.mp4")
    
    # Test avec une vidéo sans audio
    with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
        mock_video_clip.return_value.audio = None
        with pytest.raises(ValueError, match="La vidéo ne contient pas d'audio"):
            checker.check_video("no_audio.mp4") 