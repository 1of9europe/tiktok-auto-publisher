import pytest
from pathlib import Path
import streamlit as st
from unittest.mock import patch, MagicMock
import json
import os

from Orchestrator.main import Orchestrator

class TestSystem:
    @pytest.fixture
    def setup_environment(self, test_config, tmp_path):
        """Configure l'environnement complet pour les tests système"""
        # Configuration des chemins
        test_config['paths']['downloads'] = str(tmp_path / 'downloads')
        test_config['paths']['outputs'] = str(tmp_path / 'outputs')
        test_config['paths']['temp'] = str(tmp_path / 'temp')
        
        # Création des répertoires
        for path in test_config['paths'].values():
            Path(path).mkdir(parents=True, exist_ok=True)
            
        # Configuration des variables d'environnement
        os.environ['OPENAI_API_KEY'] = 'test_key'
        os.environ['TIKTOK_API_KEY'] = 'test_key'
        
        return test_config
        
    @pytest.fixture
    def orchestrator(self, setup_environment):
        """Crée une instance de l'orchestrateur"""
        return Orchestrator()
        
    def test_system_initialization(self, orchestrator):
        """Test l'initialisation complète du système"""
        assert orchestrator.trend_hunter is not None
        assert orchestrator.content_collector is not None
        assert orchestrator.clip_master is not None
        assert orchestrator.quality_checker is not None
        assert orchestrator.auto_publisher is not None
        
    def test_trend_detection_system(self, orchestrator):
        """Test le système de détection des tendances"""
        with patch.object(orchestrator.trend_hunter, '_get_tiktok_trends') as mock_tiktok:
            with patch.object(orchestrator.trend_hunter, '_get_reddit_trends') as mock_reddit:
                # Configuration des mocks
                mock_tiktok.return_value = [{'name': '#TikTokTrend', 'type': 'hashtag'}]
                mock_reddit.return_value = [{'name': 'RedditTrend', 'type': 'topic'}]
                
                # Test de la détection
                trends = orchestrator.trend_hunter.find_trends()
                
                assert len(trends) == 2
                assert any(t['name'] == '#TikTokTrend' for t in trends)
                assert any(t['name'] == 'RedditTrend' for t in trends)
                
    def test_content_collection_system(self, orchestrator):
        """Test le système de collecte de contenu"""
        with patch('pytube.Search') as mock_search:
            # Configuration du mock
            mock_video = MagicMock()
            mock_video.video_id = "test_id"
            mock_video.title = "Test Video"
            mock_video.length = 60
            mock_video.views = 10000
            mock_search.return_value.results = [mock_video]
            
            # Test de la collecte
            videos = orchestrator.content_collector.collect_content("#TestTrend")
            
            assert len(videos) > 0
            assert all(key in videos[0] for key in ['id', 'title', 'author', 'length'])
            
    def test_video_processing_system(self, orchestrator, tmp_path):
        """Test le système de traitement des vidéos"""
        # Création d'une vidéo de test
        test_video = tmp_path / "test_video.mp4"
        test_video.write_bytes(b"0" * 1024)
        
        with patch.object(orchestrator.clip_master, '_generate_subtitles') as mock_subtitles:
            mock_subtitles.return_value = {
                'text': 'Test transcription',
                'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
            }
            
            # Test du traitement
            result = orchestrator.clip_master.process_video(str(test_video))
            
            assert result['input_path'] == str(test_video)
            assert 'metadata' in result
            assert 'subtitles' in result
            
    def test_quality_check_system(self, orchestrator, tmp_path):
        """Test le système de vérification de la qualité"""
        # Création d'une vidéo de test
        test_video = tmp_path / "test_video.mp4"
        test_video.write_bytes(b"0" * 1024)
        
        with patch.object(orchestrator.quality_checker, '_analyze_visual_quality') as mock_visual:
            with patch.object(orchestrator.quality_checker, '_analyze_audio_quality') as mock_audio:
                mock_visual.return_value = {'brightness': {'status': 'good'}}
                mock_audio.return_value = {'volume': {'status': 'good'}}
                
                # Test de la vérification
                results = orchestrator.quality_checker.check_video(str(test_video))
                
                assert results['overall_quality']['status'] == 'good'
                assert 'visual_quality' in results
                assert 'audio_quality' in results
                
    def test_publication_system(self, orchestrator, tmp_path):
        """Test le système de publication"""
        # Création d'une vidéo de test
        test_video = tmp_path / "test_video.mp4"
        test_video.write_bytes(b"0" * 1024)
        
        # Métadonnées de test
        metadata = {
            'title': 'Test Video',
            'description': 'Test Description',
            'hashtags': ['#test']
        }
        
        # Test de la publication
        result = orchestrator.auto_publisher.publish_video(str(test_video), metadata)
        
        assert result['status'] == 'success'
        assert 'post_data' in result
        assert result['post_data']['title'] == metadata['title']
        
    def test_complete_system_workflow(self, orchestrator, tmp_path):
        """Test le workflow complet du système"""
        # 1. Détection des tendances
        with patch.object(orchestrator.trend_hunter, '_get_tiktok_trends') as mock_trends:
            mock_trends.return_value = [{'name': '#TestTrend', 'type': 'hashtag'}]
            trends = orchestrator.trend_hunter.find_trends()
            
            # 2. Collecte de contenu
            with patch('pytube.Search') as mock_search:
                mock_video = MagicMock()
                mock_video.video_id = "test_id"
                mock_video.title = "Test Video"
                mock_video.length = 60
                mock_video.views = 10000
                mock_search.return_value.results = [mock_video]
                
                videos = orchestrator.content_collector.collect_content(trends[0]['name'])
                
                # Création d'une vidéo de test pour la suite du workflow
                test_video = tmp_path / "test_video.mp4"
                test_video.write_bytes(b"0" * 1024)
                
                # 3. Traitement de la vidéo
                with patch.object(orchestrator.clip_master, '_generate_subtitles') as mock_subtitles:
                    mock_subtitles.return_value = {
                        'text': 'Test transcription',
                        'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
                    }
                    
                    processed_video = orchestrator.clip_master.process_video(str(test_video))
                    
                    # 4. Vérification de la qualité
                    with patch.object(orchestrator.quality_checker, '_analyze_visual_quality') as mock_visual:
                        with patch.object(orchestrator.quality_checker, '_analyze_audio_quality') as mock_audio:
                            mock_visual.return_value = {'brightness': {'status': 'good'}}
                            mock_audio.return_value = {'volume': {'status': 'good'}}
                            
                            quality_results = orchestrator.quality_checker.check_video(processed_video['output_path'])
                            
                            # 5. Publication
                            if quality_results['overall_quality']['status'] == 'good':
                                result = orchestrator.auto_publisher.publish_video(
                                    processed_video['output_path'],
                                    processed_video['metadata']
                                )
                                
                                # Vérifications finales
                                assert result['status'] == 'success'
                                assert Path(result['post_data']['video_file']).exists()
                                assert len(trends) > 0
                                assert len(videos) > 0
                                assert processed_video is not None
                                assert quality_results['overall_quality']['status'] == 'good' 