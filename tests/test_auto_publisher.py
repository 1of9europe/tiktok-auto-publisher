import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path
from AutoPublisher.auto_publisher import AutoPublisher

def test_init(test_config):
    publisher = AutoPublisher(test_config)
    assert publisher.config is not None
    assert publisher.logger is not None

def test_check_file_size(test_config, setup_test_environment):
    publisher = AutoPublisher(test_config)
    
    # Créer un fichier de test de 1KB
    test_file = Path(setup_test_environment["processed"]) / "test.mp4"
    test_file.write_bytes(b"0" * 1024)  # 1KB
    
    # Vérifier avec une limite de 512 bytes (devrait échouer)
    publisher.config['video_settings']['max_file_size'] = 512
    assert not publisher._check_file_size(str(test_file))
    
    # Vérifier avec une limite de 2KB (devrait réussir)
    publisher.config['video_settings']['max_file_size'] = 2048
    assert publisher._check_file_size(str(test_file))

def test_prepare_post_data(test_config):
    publisher = AutoPublisher(test_config)
    
    metadata = {
        "title": "Test Video",
        "description": "This is a test video with a very long description that should be truncated because it exceeds the maximum length allowed by TikTok's API. This is just some additional text to make sure it's long enough to be truncated.",
        "hashtags": ["#test", "#video", "#tiktok", "#viral", "#trending", "#fyp", "#foryou", "#foryoupage"]
    }
    
    post_data = publisher._prepare_post_data("test.mp4", metadata)
    
    assert "video_file" in post_data
    assert "title" in post_data
    assert "hashtags" in post_data
    assert len(post_data["hashtags"]) <= test_config["api"]["tiktok"]["max_hashtags"]
    assert len(post_data["description"]) <= test_config["api"]["tiktok"]["max_description_length"]

def test_mock_tiktok_api(test_config):
    publisher = AutoPublisher(test_config)
    
    post_data = {
        "video_file": "test.mp4",
        "title": "Test Video",
        "description": "Test description",
        "hashtags": ["#test"]
    }
    
    response = publisher._mock_tiktok_api(post_data)
    
    assert response["status"] == "success"
    assert "message" in response
    assert "post_data" in response
    assert "timestamp" in response
    assert "mock_video_url" in response

def test_save_publish_report(test_config, setup_test_environment):
    publisher = AutoPublisher(test_config)
    
    response = {
        "status": "success",
        "message": "Video published successfully",
        "post_data": {
            "title": "Test Video",
            "hashtags": ["#test"]
        },
        "timestamp": "2024-01-01T00:00:00",
        "mock_video_url": "https://www.tiktok.com/@test"
    }
    
    # Utiliser un chemin complet pour la vidéo
    video_path = str(Path(setup_test_environment["processed"]) / "test.mp4")
    publisher._save_publish_report(response, video_path)
    
    # Vérification du rapport
    publish_reports_dir = Path(setup_test_environment["processed"]) / "publish_reports"
    assert publish_reports_dir.exists()
    assert len(list(publish_reports_dir.glob("*.json"))) == 1

def test_publish_video_with_valid_file(test_config, setup_test_environment, sample_video_path):
    publisher = AutoPublisher(test_config)
    
    metadata = {
        "title": "Test Video",
        "description": "This is a test video",
        "hashtags": ["#test", "#video"]
    }
    
    result = publisher.publish_video(sample_video_path, metadata)
    
    assert result["status"] == "success"
    assert "mock_video_url" in result

def test_publish_video_with_invalid_file_size(test_config, setup_test_environment):
    publisher = AutoPublisher(test_config)
    
    # Créer un fichier trop grand
    large_file = Path(setup_test_environment["processed"]) / "large.mp4"
    large_file.write_bytes(b"0" * (100 * 1024 * 1024))  # 100MB
    
    metadata = {
        "title": "Test Video",
        "description": "This is a test video",
        "hashtags": ["#test"]
    }
    
    with pytest.raises(ValueError, match="La taille de la vidéo dépasse la limite autorisée"):
        publisher.publish_video(str(large_file), metadata)

def test_error_handling(test_config, setup_test_environment):
    publisher = AutoPublisher(test_config)
    
    # Test avec un fichier inexistant
    with pytest.raises(FileNotFoundError):
        publisher.publish_video("nonexistent.mp4", {})
    
    # Test avec des métadonnées invalides
    with pytest.raises(ValueError, match="Les métadonnées ne peuvent pas être None"):
        publisher._prepare_post_data("test.mp4", None) 