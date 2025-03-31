import pytest
from unittest.mock import patch, MagicMock
from ContentCollector.content_collector import ContentCollector
import json
import os
import requests
import shutil

@pytest.fixture
def config():
    """Fixture pour la configuration"""
    return {
        'api': {
            'youtube': {
                'api_key': 'test_api_key',
                'max_results': 10,
                'min_views': 1000,
                'max_duration': 60
            }
        },
        'paths': {
            'downloads': 'test_downloads'
        }
    }

@pytest.fixture
def content_collector():
    """Fixture pour créer une instance de ContentCollector"""
    config = {
        'api': {
            'youtube': {
                'api_key': 'test_api_key',
                'max_results': 10,
                'max_duration': 60,
                'min_views': 1000
            }
        },
        'paths': {
            'downloads': 'test_downloads'
        }
    }
    collector = ContentCollector(config)
    yield collector
    # Nettoyage
    if os.path.exists('test_downloads'):
        shutil.rmtree('test_downloads')

def test_init(content_collector, config):
    """Test l'initialisation du ContentCollector"""
    assert content_collector.config == config
    assert content_collector.api_key == config['api']['youtube']['api_key']
    assert content_collector.output_dir == config['paths']['downloads']
    assert os.path.exists(config['paths']['downloads'])

def test_meets_criteria(content_collector):
    """Test la vérification des critères"""
    # Vidéo valide
    valid_video = {
        'id': 'test1',
        'duration': 30,
        'views': 5000
    }
    assert content_collector._meets_criteria(valid_video) is True
    
    # Vidéo trop longue
    long_video = {
        'id': 'test2',
        'duration': 120,
        'views': 5000
    }
    assert content_collector._meets_criteria(long_video) is False
    
    # Vidéo pas assez de vues
    low_views_video = {
        'id': 'test3',
        'duration': 30,
        'views': 500
    }
    assert content_collector._meets_criteria(low_views_video) is False

def test_parse_duration(content_collector):
    """Test la conversion de la durée ISO 8601"""
    assert content_collector._parse_duration('PT1H2M10S') == 3730
    assert content_collector._parse_duration('PT5M') == 300
    assert content_collector._parse_duration('PT30S') == 30
    assert content_collector._parse_duration('P1DT2H') == 0  # Format invalide
    assert content_collector._parse_duration('invalid') == 0

def test_search_videos(content_collector):
    """Test la recherche de vidéos"""
    # Configuration du mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        'items': [
            {
                'id': {'videoId': 'test1'},
                'snippet': {'title': 'Test Video 1'}
            }
        ]
    }
    
    with patch.object(content_collector.session, 'get', return_value=mock_response):
        # Test de la recherche
        results = content_collector._search_videos('test query')

        # Vérifications
        assert len(results) == 1
        assert results[0]['id']['videoId'] == 'test1'
        content_collector.session.get.assert_called_once()

def test_get_video_details(content_collector):
    """Test la récupération des détails des vidéos"""
    # Configuration du mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
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
    
    with patch.object(content_collector.session, 'get', return_value=mock_response):
        # Test de la récupération
        results = content_collector._get_video_details(['test1'])

        # Vérifications
        assert len(results) == 1
        assert results[0]['id'] == 'test1'
        content_collector.session.get.assert_called_once()

def test_collect_content(content_collector):
    """Test la collecte complète de contenu"""
    # Configuration des mocks pour la recherche
    search_response = MagicMock()
    search_response.status_code = 200
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        'items': [
            {
                'id': {'videoId': 'test1'},
                'snippet': {'title': 'Test Video 1'}
            }
        ]
    }

    # Configuration des mocks pour les détails
    details_response = MagicMock()
    details_response.status_code = 200
    details_response.raise_for_status.return_value = None
    details_response.json.return_value = {
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

    # Configuration des mocks pour le téléchargement
    download_response = MagicMock()
    download_response.status_code = 200
    download_response.raise_for_status.return_value = None
    download_response.json.return_value = {
        'items': [
            {
                'id': 'test1',
                'contentDetails': {'duration': 'PT30S'}
            }
        ]
    }

    with patch.object(content_collector.session, 'get', side_effect=[search_response, details_response, download_response]):
        # Test de la collecte
        results = content_collector.collect_content(['test'])

        # Vérifications
        assert len(results) == 1
        assert results[0]['id'] == 'test1'
        assert content_collector.session.get.call_count == 3

def test_error_handling(content_collector):
    """Test la gestion des erreurs"""
    # Configuration du mock pour simuler une erreur
    mock_error = requests.exceptions.RequestException("API Error")
    
    with patch.object(content_collector.session, 'get', side_effect=mock_error):
        # Test avec gestion d'erreur
        results = content_collector.collect_content(['test'])

        # Vérifications
        assert len(results) == 0
        assert content_collector.session.get.call_count == 1 