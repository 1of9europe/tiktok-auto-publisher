import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path
from TrendHunter.trend_hunter import TrendHunter

def test_init(test_config):
    trend_hunter = TrendHunter(test_config)
    assert trend_hunter.config is not None
    assert trend_hunter.logger is not None

@patch('requests.get')
def test_get_tiktok_trends(mock_get, test_config):
    # Simuler une réponse HTML avec des hashtags tendance
    mock_html = """
    <div class="trending-tag">
        <a href="/tag/trending">#trending</a>
        <span class="view-count">1M views</span>
    </div>
    <div class="trending-tag">
        <a href="/tag/viral">#viral</a>
        <span class="view-count">2M views</span>
    </div>
    """
    mock_get.return_value.text = mock_html
    mock_get.return_value.status_code = 200
    
    trend_hunter = TrendHunter(test_config)
    trends = trend_hunter.get_tiktok_trends()
    
    assert len(trends) == 2
    assert trends[0]["tag"] == "#trending"
    assert mock_get.call_count == 1

@patch('requests.get')
def test_get_reddit_trends(mock_get, test_config):
    # Simuler une réponse JSON de Reddit
    mock_response = {
        "data": {
            "children": [
                {"data": {"title": "Topic 1", "score": 1000, "num_comments": 100}},
                {"data": {"title": "Topic 2", "score": 2000, "num_comments": 200}}
            ]
        }
    }
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.status_code = 200
    
    trend_hunter = TrendHunter(test_config)
    topics = trend_hunter.get_reddit_trends()
    
    assert len(topics) == 2
    assert topics[0]["topic"] == "Topic 1"
    assert mock_get.call_count == 1

def test_save_trends(test_config, setup_test_environment, mock_trend_data):
    trend_hunter = TrendHunter(test_config)
    temp_path = setup_test_environment["metadata"] / "trends.json"
    
    trend_hunter.save_trends(mock_trend_data, temp_path)
    
    assert temp_path.exists()
    with open(temp_path) as f:
        saved_data = json.load(f)
    assert saved_data == mock_trend_data

@patch.object(TrendHunter, 'get_tiktok_trends')
@patch.object(TrendHunter, 'get_reddit_trends')
def test_find_trends(mock_reddit, mock_tiktok, test_config, mock_trend_data):
    mock_tiktok.return_value = mock_trend_data["tiktok"]
    mock_reddit.return_value = mock_trend_data["reddit"]
    
    trend_hunter = TrendHunter(test_config)
    trends = trend_hunter.find_trends()
    
    assert trends["tiktok"] == mock_trend_data["tiktok"]
    assert trends["reddit"] == mock_trend_data["reddit"]
    assert mock_tiktok.call_count == 1
    assert mock_reddit.call_count == 1

def test_error_handling(test_config):
    trend_hunter = TrendHunter(test_config)
    
    # Simuler une erreur dans la récupération des tendances
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("API Error")
        
        # Vérifier que les méthodes retournent une liste vide en cas d'erreur
        assert trend_hunter.get_tiktok_trends() == []
        assert trend_hunter.get_reddit_trends() == [] 