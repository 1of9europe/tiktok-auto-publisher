import pytest
import json
import os
from pathlib import Path
import shutil

@pytest.fixture
def test_config():
    return {
        "video_settings": {
            "max_duration": 60,
            "min_duration": 15,
            "output_resolution": "1080p",
            "fps": 30,
            "max_file_size": 50 * 1024 * 1024  # 50MB en bytes
        },
        "api": {
            "tiktok": {
                "api_key": "test_tiktok_key",
                "max_hashtags": 10,
                "max_description_length": 2200,
                "max_title_length": 150
            },
            "openai": {
                "api_key": "test_openai_key"
            }
        },
        "quality_thresholds": {
            "brightness": 0.5,
            "contrast": 0.4,
            "sharpness": 0.6,
            "audio_volume": 0.7,
            "noise_level": 0.3
        }
    }

@pytest.fixture
def setup_test_environment(tmp_path):
    # Créer les répertoires temporaires pour les tests
    test_dirs = {
        "downloads": tmp_path / "downloads",
        "processed": tmp_path / "processed",
        "metadata": tmp_path / "metadata",
        "reports": tmp_path / "reports"
    }
    
    for dir_path in test_dirs.values():
        dir_path.mkdir(exist_ok=True)
    
    # Configuration des variables d'environnement pour les tests
    os.environ["OPENAI_API_KEY"] = "test_openai_key"
    os.environ["TIKTOK_API_KEY"] = "test_tiktok_key"
    
    yield test_dirs
    
    # Nettoyage après les tests
    for dir_path in test_dirs.values():
        if dir_path.exists():
            shutil.rmtree(dir_path)

@pytest.fixture
def sample_video_path(tmp_path):
    video_path = tmp_path / "test_video.mp4"
    # Créer un fichier vidéo factice pour les tests
    video_path.write_bytes(b"fake video content")
    return str(video_path)

@pytest.fixture
def mock_trend_data():
    return {
        "tiktok": [
            {"tag": "#trending", "views": 1000000, "posts": 5000},
            {"tag": "#viral", "views": 2000000, "posts": 8000}
        ],
        "reddit": [
            {"topic": "interesting_topic", "upvotes": 50000, "comments": 1000},
            {"topic": "viral_content", "upvotes": 75000, "comments": 1500}
        ]
    } 