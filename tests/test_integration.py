import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import shutil

from TrendHunter.trend_hunter import TrendHunter
from ContentCollector.content_collector import ContentCollector
from ClipMaster.clip_master import ClipMaster
from QualityChecker.quality_checker import QualityChecker
from AutoPublisher.auto_publisher import AutoPublisher

class TestIntegration:
    @pytest.fixture
    def setup_workflow(self, test_config, tmp_path):
        """Configure l'environnement de test pour le workflow complet"""
        # Configuration des chemins temporaires
        test_config['paths']['downloads'] = str(tmp_path / 'downloads')
        test_config['paths']['outputs'] = str(tmp_path / 'outputs')
        test_config['paths']['temp'] = str(tmp_path / 'temp')
        
        # Création des répertoires
        for path in test_config['paths'].values():
            Path(path).mkdir(parents=True, exist_ok=True)
            
        return test_config
        
    @pytest.fixture
    def mock_video_file(self, tmp_path):
        """Crée un fichier vidéo factice pour les tests"""
        video_path = tmp_path / 'test_video.mp4'
        video_path.write_bytes(b"0" * 1024)  # Fichier factice de 1KB
        return str(video_path)
        
    def test_trend_to_content_workflow(self, setup_workflow):
        """Test l'intégration entre TrendHunter et ContentCollector"""
        trend_hunter = TrendHunter(setup_workflow)
        content_collector = ContentCollector(setup_workflow)
        
        # Mock des tendances
        with patch.object(trend_hunter, '_get_tiktok_trends') as mock_trends:
            mock_trends.return_value = [{'name': '#TestTrend', 'type': 'hashtag'}]
            trends = trend_hunter.find_trends()
            
            # Utilisation des tendances pour la recherche de contenu
            with patch('pytube.Search') as mock_search:
                mock_video = MagicMock()
                mock_video.video_id = "test_id"
                mock_video.title = "Test Video"
                mock_video.length = 60
                mock_video.views = 10000
                mock_search.return_value.results = [mock_video]
                
                videos = content_collector.collect_content(trends[0]['name'])
                
                assert len(videos) > 0
                assert videos[0]['title'] == "Test Video"
                
    def test_content_to_clip_workflow(self, setup_workflow, mock_video_file):
        """Test l'intégration entre ContentCollector et ClipMaster"""
        content_collector = ContentCollector(setup_workflow)
        clip_master = ClipMaster(setup_workflow)
        
        # Mock de la collecte de contenu
        with patch('pytube.Search'):
            with patch.object(content_collector, '_process_video') as mock_process:
                mock_process.return_value = {
                    'id': 'test_id',
                    'local_path': mock_video_file
                }
                
                videos = content_collector.collect_content("test query")
                
                # Traitement de la vidéo avec ClipMaster
                with patch.object(clip_master, '_generate_subtitles') as mock_subtitles:
                    mock_subtitles.return_value = {
                        'text': 'Test transcription',
                        'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
                    }
                    
                    result = clip_master.process_video(videos[0]['local_path'])
                    
                    assert result['input_path'] == videos[0]['local_path']
                    assert 'subtitles' in result
                    
    def test_clip_to_quality_workflow(self, setup_workflow, mock_video_file):
        """Test l'intégration entre ClipMaster et QualityChecker"""
        clip_master = ClipMaster(setup_workflow)
        quality_checker = QualityChecker(setup_workflow)
        
        # Mock du traitement de la vidéo
        with patch.object(clip_master, 'process_video') as mock_process:
            mock_process.return_value = {
                'output_path': mock_video_file,
                'metadata': {'title': 'Test'}
            }
            
            processed_video = clip_master.process_video(mock_video_file)
            
            # Vérification de la qualité
            with patch.object(quality_checker, '_analyze_visual_quality') as mock_visual:
                with patch.object(quality_checker, '_analyze_audio_quality') as mock_audio:
                    mock_visual.return_value = {'brightness': {'status': 'good'}}
                    mock_audio.return_value = {'volume': {'status': 'good'}}
                    
                    quality_results = quality_checker.check_video(processed_video['output_path'])
                    
                    assert quality_results['overall_quality']['status'] == 'good'
                    
    def test_quality_to_publish_workflow(self, setup_workflow, mock_video_file):
        """Test l'intégration entre QualityChecker et AutoPublisher"""
        quality_checker = QualityChecker(setup_workflow)
        auto_publisher = AutoPublisher(setup_workflow)
        
        # Mock de la vérification de qualité
        with patch.object(quality_checker, 'check_video') as mock_check:
            mock_check.return_value = {
                'overall_quality': {'status': 'good', 'score': 0.9}
            }
            
            quality_results = quality_checker.check_video(mock_video_file)
            
            # Si la qualité est bonne, publication
            if quality_results['overall_quality']['status'] == 'good':
                metadata = {
                    'title': 'Test Video',
                    'description': 'Test Description',
                    'hashtags': ['#test']
                }
                
                result = auto_publisher.publish_video(mock_video_file, metadata)
                
                assert result['status'] == 'success'
                
    def test_complete_workflow(self, setup_workflow, mock_video_file):
        """Test du workflow complet de bout en bout"""
        # Initialisation des composants
        trend_hunter = TrendHunter(setup_workflow)
        content_collector = ContentCollector(setup_workflow)
        clip_master = ClipMaster(setup_workflow)
        quality_checker = QualityChecker(setup_workflow)
        auto_publisher = AutoPublisher(setup_workflow)
        
        # 1. Recherche des tendances
        with patch.object(trend_hunter, '_get_tiktok_trends') as mock_trends:
            mock_trends.return_value = [{'name': '#TestTrend', 'type': 'hashtag'}]
            trends = trend_hunter.find_trends()
            
            # 2. Collecte de contenu
            with patch('pytube.Search') as mock_search:
                mock_video = MagicMock()
                mock_video.video_id = "test_id"
                mock_video.title = "Test Video"
                mock_video.length = 60
                mock_video.views = 10000
                mock_search.return_value.results = [mock_video]
                
                videos = content_collector.collect_content(trends[0]['name'])
                
                # 3. Traitement de la vidéo
                with patch.object(clip_master, '_generate_subtitles') as mock_subtitles:
                    mock_subtitles.return_value = {
                        'text': 'Test transcription',
                        'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
                    }
                    
                    processed_video = clip_master.process_video(mock_video_file)
                    
                    # 4. Vérification de la qualité
                    with patch.object(quality_checker, '_analyze_visual_quality') as mock_visual:
                        with patch.object(quality_checker, '_analyze_audio_quality') as mock_audio:
                            mock_visual.return_value = {'brightness': {'status': 'good'}}
                            mock_audio.return_value = {'volume': {'status': 'good'}}
                            
                            quality_results = quality_checker.check_video(processed_video['output_path'])
                            
                            # 5. Publication si la qualité est bonne
                            if quality_results['overall_quality']['status'] == 'good':
                                result = auto_publisher.publish_video(
                                    processed_video['output_path'],
                                    processed_video['metadata']
                                )
                                
                                assert result['status'] == 'success'
                                assert Path(result['post_data']['video_file']).exists() 