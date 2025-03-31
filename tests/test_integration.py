import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import shutil
import os
from datetime import datetime
import subprocess
from moviepy.config import change_settings

from TrendHunter.trend_hunter import TrendHunter
from ContentCollector.content_collector import ContentCollector
from ClipMaster.clip_master import ClipMaster
from QualityChecker.quality_checker import QualityChecker
from AutoPublisher.auto_publisher import AutoPublisher
from TrendHunter.models import Trend, TrendMetadata

# Configuration de MoviePy pour utiliser ImageMagick
change_settings({"IMAGEMAGICK_BINARY": "convert"})

@pytest.fixture(scope="class")
def test_config():
    """Configuration de test"""
    return {
        'api': {
            'youtube': {
                'api_key': 'test_youtube_key',
                'max_results': 5,
                'max_duration': 60,
                'min_views': 1000
            },
            'tiktok': {
                'api_key': 'test_tiktok_key',
                'max_description_length': 150,
                'max_results': 5,
                'max_hashtags': 10
            },
            'openai': {
                'api_key': 'test_openai_key',
                'model': 'gpt-3.5-turbo',
                'temperature': 0.7,
                'max_tokens': 150
            }
        },
        'paths': {
            'downloads': '',  # Sera configuré dans setup_workflow
            'clips': '',      # Sera configuré dans setup_workflow
            'output': '',     # Sera configuré dans setup_workflow
            'outputs': ''     # Pour la compatibilité avec ClipMaster
        },
        'video_settings': {
            'fps': 30,
            'min_duration': 15,
            'max_duration': 60,
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'quality_threshold': 0.3,
            'bitrate': '2000k'  # Ajout du bitrate
        },
        'quality_thresholds': {
            'min_resolution': [1280, 720],  # 720p minimum
            'min_fps': 24,
            'min_bitrate': 1000000,  # 1 Mbps
            'max_noise_level': 0.3,
            'min_brightness': 0.2,
            'max_brightness': 0.8
        }
    }

@pytest.fixture(scope="function")
def setup_workflow(test_config, tmp_path):
    """Configure les chemins pour les tests"""
    config = test_config.copy()
    config['paths'] = {
        'downloads': str(tmp_path / 'downloads'),
        'clips': str(tmp_path / 'clips'),
        'output': str(tmp_path / 'output'),
        'outputs': str(tmp_path / 'outputs')
    }
    
    # Créer les répertoires
    for path in config['paths'].values():
        os.makedirs(path, exist_ok=True)
    
    return config

@pytest.fixture(scope="function")
def mock_video_file(tmp_path):
    """Crée un fichier vidéo mock valide"""
    video_file = tmp_path / "test_video.mp4"
    
    # Créer un fichier vidéo valide avec ffmpeg
    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "color=c=white:s=1280x720:d=5",
        "-c:v", "libx264", "-preset", "ultrafast",
        str(video_file)
    ], check=True)
    
    return str(video_file)

class TestIntegration:
    def test_trend_to_content_workflow(self, setup_workflow):
        """Test l'intégration entre TrendHunter et ContentCollector"""
        trend_hunter = TrendHunter(setup_workflow)
        content_collector = ContentCollector(setup_workflow)
        
        # Mock des tendances
        with patch.object(trend_hunter, '_get_tiktok_trends') as mock_trends:
            mock_trends.return_value = [
                Trend(
                    platform='tiktok',
                    type='hashtag',
                    name='#TestTrend',
                    timestamp=datetime.now(),
                    metadata=TrendMetadata(
                        views=1000000,
                        videos=1000,
                        description='Test Description',
                        category='test'
                    )
                )
            ]
            trends = trend_hunter.find_trends()
            
            # Utilisation des tendances pour la recherche de contenu
            with patch.object(content_collector.session, 'get') as mock_get:
                # Mock de la recherche
                mock_get.return_value.status_code = 200
                mock_get.return_value.raise_for_status.return_value = None
                mock_get.return_value.json.return_value = {
                    'items': [{
                        'id': {'videoId': 'test_id'},
                        'snippet': {
                            'title': 'Test Video',
                            'description': 'Test Description',
                            'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                            'publishedAt': '2024-01-01T00:00:00Z',
                            'channelTitle': 'Test Channel'
                        }
                    }]
                }

                # Mock des détails de la vidéo
                mock_get.return_value.json.side_effect = [
                    # Première réponse pour la recherche
                    {
                        'items': [{
                            'id': {'videoId': 'test_id'},
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                                'publishedAt': '2024-01-01T00:00:00Z',
                                'channelTitle': 'Test Channel'
                            }
                        }]
                    },
                    # Deuxième réponse pour les détails
                    {
                        'items': [{
                            'id': 'test_id',
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                                'publishedAt': '2024-01-01T00:00:00Z',
                                'channelTitle': 'Test Channel'
                            },
                            'contentDetails': {
                                'duration': 'PT1M'
                            },
                            'statistics': {
                                'viewCount': '10000'
                            }
                        }]
                    },
                    # Troisième réponse pour le téléchargement
                    {
                        'items': [{
                            'contentDetails': {
                                'duration': 'PT1M'
                            }
                        }]
                    }
                ]

                videos = content_collector.collect_content([trends[0].name])
                
                assert len(videos) > 0
                assert videos[0]['title'] == "Test Video"
                
    def test_content_to_clip_workflow(self, setup_workflow, mock_video_file):
        """Test l'intégration entre ContentCollector et ClipMaster"""
        content_collector = ContentCollector(setup_workflow)
        clip_master = ClipMaster(setup_workflow)
        
        # Mock de la collecte de contenu
        with patch.object(content_collector.session, 'get') as mock_get:
            # Mock de la recherche
            mock_get.return_value.status_code = 200
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.side_effect = [
                # Première réponse pour la recherche
                {
                    'items': [{
                        'id': {'videoId': 'test_id'},
                        'snippet': {
                            'title': 'Test Video',
                            'description': 'Test Description',
                            'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                            'publishedAt': '2024-01-01T00:00:00Z',
                            'channelTitle': 'Test Channel'
                        }
                    }]
                },
                # Deuxième réponse pour les détails
                {
                    'items': [{
                        'id': 'test_id',
                        'snippet': {
                            'title': 'Test Video',
                            'description': 'Test Description',
                            'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                            'publishedAt': '2024-01-01T00:00:00Z',
                            'channelTitle': 'Test Channel'
                        },
                        'contentDetails': {
                            'duration': 'PT1M'
                        },
                        'statistics': {
                            'viewCount': '10000'
                        }
                    }]
                },
                # Troisième réponse pour le téléchargement
                {
                    'items': [{
                        'contentDetails': {
                            'duration': 'PT1M'
                        }
                    }]
                }
            ]

            with patch.object(content_collector, '_download_video', return_value=True):
                videos = content_collector.collect_content(["test query"])

                # Mock de l'API OpenAI
                with patch('openai.ChatCompletion.create') as mock_openai:
                    mock_openai.return_value.choices = [
                        MagicMock(
                            message=MagicMock(
                                content='{"title": "Test Title", "description": "Test Description", "hashtags": ["#test"]}'
                            )
                        )
                    ]

                    # Traitement de la vidéo avec ClipMaster
                    with patch.object(clip_master, '_generate_subtitles') as mock_subtitles:
                        mock_subtitles.return_value = {
                            'text': 'Test transcription',
                            'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
                        }

                        result = clip_master.process_video(mock_video_file)
                        
                        assert result['input_path'] == mock_video_file
                        assert 'subtitles' in result
                        assert 'metadata' in result
                        assert result['metadata']['title'] == "Test Title"
                        assert result['metadata']['description'] == "Test Description"
                        assert result['metadata']['hashtags'] == ["#test"]

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
            mock_trends.return_value = [
                Trend(
                    platform='tiktok',
                    type='hashtag',
                    name='#TestTrend',
                    timestamp=datetime.now(),
                    metadata=TrendMetadata(
                        views=1000000,
                        videos=1000,
                        description='Test Description',
                        category='test'
                    )
                )
            ]
            trends = trend_hunter.find_trends()
            
            # 2. Collecte de contenu
            with patch.object(content_collector.session, 'get') as mock_get:
                # Mock de la recherche
                mock_get.return_value.status_code = 200
                mock_get.return_value.raise_for_status.return_value = None
                mock_get.return_value.json.return_value = {
                    'items': [{
                        'id': {'videoId': 'test_id'},
                        'snippet': {
                            'title': 'Test Video',
                            'description': 'Test Description',
                            'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                            'publishedAt': '2024-01-01T00:00:00Z',
                            'channelTitle': 'Test Channel'
                        }
                    }]
                }

                # Mock des détails de la vidéo
                mock_get.return_value.json.side_effect = [
                    # Première réponse pour la recherche
                    {
                        'items': [{
                            'id': {'videoId': 'test_id'},
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                                'publishedAt': '2024-01-01T00:00:00Z',
                                'channelTitle': 'Test Channel'
                            }
                        }]
                    },
                    # Deuxième réponse pour les détails
                    {
                        'items': [{
                            'id': 'test_id',
                            'snippet': {
                                'title': 'Test Video',
                                'description': 'Test Description',
                                'thumbnails': {'high': {'url': 'https://example.com/thumbnail.jpg'}},
                                'publishedAt': '2024-01-01T00:00:00Z',
                                'channelTitle': 'Test Channel'
                            },
                            'contentDetails': {
                                'duration': 'PT1M'
                            },
                            'statistics': {
                                'viewCount': '10000'
                            }
                        }]
                    },
                    # Troisième réponse pour le téléchargement
                    {
                        'items': [{
                            'contentDetails': {
                                'duration': 'PT1M'
                            }
                        }]
                    }
                ]

                with patch.object(content_collector, '_download_video', return_value=True):
                    videos = content_collector.collect_content([trends[0].name])
                
                # 3. Traitement de la vidéo
                with patch.object(clip_master, '_generate_subtitles') as mock_subtitles:
                    mock_subtitles.return_value = {
                        'text': 'Test transcription',
                        'segments': [{'start': 0, 'end': 5, 'text': 'Test'}]
                    }
                    
                    # Mock de l'API OpenAI
                    with patch('openai.ChatCompletion.create') as mock_openai:
                        mock_openai.return_value.choices = [
                            MagicMock(
                                message=MagicMock(
                                    content='{"title": "Test Title", "description": "Test Description", "hashtags": ["#test"]}'
                                )
                            )
                        ]
                        
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

@pytest.fixture
def trend_hunter(setup_workflow):
    """Fixture pour TrendHunter"""
    return TrendHunter(setup_workflow)

@pytest.fixture
def content_collector(setup_workflow):
    """Fixture pour ContentCollector"""
    return ContentCollector(setup_workflow)

def test_trend_hunter_content_collector_integration(trend_hunter, content_collector, setup_workflow):
    """Test l'intégration entre TrendHunter et ContentCollector"""
    # Mock des réponses de l'API TikTok
    mock_tiktok_response = MagicMock()
    mock_tiktok_response.status_code = 200
    mock_tiktok_response.raise_for_status.return_value = None
    mock_tiktok_response.json.return_value = {
        'body': {
            'challenge_list': [
                {
                    'title': 'Test Trend 1',
                    'stats': {
                        'view_count': '1M',
                        'video_count': 1000
                    },
                    'description': 'Test Description 1'
                },
                {
                    'title': 'Test Trend 2',
                    'stats': {
                        'view_count': '500K',
                        'video_count': 500
                    },
                    'description': 'Test Description 2'
                }
            ]
        }
    }

    # Mock des réponses de l'API YouTube
    mock_youtube_search = MagicMock()
    mock_youtube_search.status_code = 200
    mock_youtube_search.raise_for_status.return_value = None
    mock_youtube_search.json.return_value = {
        'items': [
            {
                'id': {'videoId': 'test1'},
                'snippet': {
                    'title': 'Test Video 1',
                    'description': 'Test Description',
                    'thumbnails': {'high': {'url': 'http://example.com/thumb.jpg'}},
                    'publishedAt': '2024-01-01T00:00:00Z',
                    'channelTitle': 'Test Channel'
                }
            }
        ]
    }

    mock_youtube_details = MagicMock()
    mock_youtube_details.status_code = 200
    mock_youtube_details.raise_for_status.return_value = None
    mock_youtube_details.json.return_value = {
        'items': [
            {
                'id': 'test1',
                'snippet': {
                    'title': 'Test Video 1',
                    'description': 'Test Description',
                    'thumbnails': {'high': {'url': 'http://example.com/thumb.jpg'}},
                    'publishedAt': '2024-01-01T00:00:00Z',
                    'channelTitle': 'Test Channel'
                },
                'contentDetails': {'duration': 'PT30S'},
                'statistics': {'viewCount': '5000'}
            }
        ]
    }

    # Configuration des mocks pour les requêtes YouTube
    def mock_get(url, **kwargs):
        if 'search' in url:
            return mock_youtube_search
        elif 'videos' in url:
            return mock_youtube_details
        return mock_tiktok_response

    # Patch des requêtes HTTP
    with patch('requests.Session.get', side_effect=mock_get), \
         patch('ContentCollector.content_collector.ContentCollector._download_video') as mock_download:
        # Configuration du mock de téléchargement pour créer un fichier vide
        def mock_download_video(video_id):
            output_path = os.path.join(setup_workflow['paths']['downloads'], f"{video_id}.mp4")
            with open(output_path, 'wb') as f:
                f.write(b'video content')
            return True
        mock_download.side_effect = mock_download_video

        # 1. Détection des tendances
        trends = trend_hunter.find_trends()
        assert len(trends) == 10  # 10 tendances de secours
        assert trends[0].name == '#fyp'  # Première tendance de secours
        assert trends[1].name == '#foryou'  # Deuxième tendance de secours

        # 2. Collecte de contenu basée sur les tendances
        keywords = [trend.name for trend in trends]
        collected_videos = content_collector.collect_content(keywords)

        # 3. Vérifications
        assert len(collected_videos) > 0
        assert all(video['duration'] <= 60 for video in collected_videos)
        assert all(video['views'] >= 1000 for video in collected_videos)
        downloads_dir = setup_workflow['paths']['downloads']
        assert all(os.path.exists(os.path.join(downloads_dir, f"{video['id']}.mp4")) for video in collected_videos)

def test_error_handling_integration(trend_hunter, content_collector):
    """Test la gestion des erreurs dans l'intégration"""
    # Mock pour simuler une erreur de l'API TikTok
    with patch('requests.get', side_effect=Exception("API Error")):
        # La détection des tendances devrait utiliser les tendances de secours
        trends = trend_hunter.find_trends()
        assert len(trends) > 0  # Devrait avoir des tendances de secours

        # La collecte de contenu devrait continuer même avec des erreurs
        keywords = [trend.name for trend in trends]
        collected_videos = content_collector.collect_content(keywords)
        assert isinstance(collected_videos, list)  # Devrait retourner une liste vide en cas d'erreur 