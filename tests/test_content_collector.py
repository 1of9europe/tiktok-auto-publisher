import pytest
from unittest.mock import patch, MagicMock, Mock
from ContentCollector.content_collector import ContentCollector
from pathlib import Path
import json

class TestContentCollector:
    @pytest.fixture
    def content_collector(self, test_config):
        return ContentCollector(test_config)
    
    @pytest.fixture
    def mock_youtube_video(self):
        video = MagicMock()
        video.video_id = "test_id"
        video.title = "Test Video"
        video.author = "Test Author"
        video.length = 60
        video.views = 10000
        video.keywords = ["test", "video"]
        video.description = "Test description"
        video.thumbnail_url = "http://test.com/thumb.jpg"
        return video
    
    def test_init(self, content_collector, test_config):
        """Test l'initialisation de ContentCollector"""
        assert content_collector.config == test_config
        assert content_collector.logger is not None
        assert Path(content_collector.downloads_dir).exists()
        
    @patch('pytube.Search')
    def test_collect_content(self, mock_search, content_collector, mock_youtube_video):
        """Test la collecte de contenu YouTube"""
        # Configuration du mock
        mock_search.return_value.results = [mock_youtube_video]
        
        # Test de la collecte
        videos = content_collector.collect_content("test query")
        
        assert len(videos) == 1
        assert videos[0]['id'] == "test_id"
        assert videos[0]['title'] == "Test Video"
        
    def test_process_video(self, content_collector, mock_youtube_video):
        """Test le traitement d'une vidéo"""
        # Configuration du mock pour le stream
        stream = MagicMock()
        mock_youtube_video.streams.filter.return_value.order_by.return_value.desc.return_value.first.return_value = stream
        
        # Test du traitement
        video_data = content_collector._process_video(mock_youtube_video)
        
        assert video_data is not None
        assert video_data['id'] == "test_id"
        assert video_data['title'] == "Test Video"
        assert video_data['author'] == "Test Author"
        
    def test_process_video_too_long(self, content_collector, mock_youtube_video):
        """Test le rejet des vidéos trop longues"""
        # Configuration d'une vidéo trop longue
        mock_youtube_video.length = 1000
        
        # Test du traitement
        video_data = content_collector._process_video(mock_youtube_video)
        
        assert video_data is None
        
    def test_save_metadata(self, content_collector, tmp_path):
        """Test la sauvegarde des métadonnées"""
        # Configuration du répertoire temporaire
        content_collector.downloads_dir = tmp_path
        
        # Données de test
        test_videos = [
            {
                'id': 'test_id',
                'title': 'Test Video',
                'author': 'Test Author'
            }
        ]
        
        # Sauvegarde des métadonnées
        content_collector._save_metadata(test_videos)
        
        # Vérification
        metadata_dir = tmp_path / 'metadata'
        assert metadata_dir.exists()
        
        metadata_files = list(metadata_dir.glob('videos_*.json'))
        assert len(metadata_files) == 1
        
    def test_error_handling(self, content_collector, mock_youtube_video):
        """Test la gestion des erreurs"""
        # Test d'erreur lors du téléchargement
        mock_youtube_video.streams.filter.side_effect = Exception("Download error")
        
        video_data = content_collector._process_video(mock_youtube_video)
        assert video_data is None
        
    @patch('pytube.Search')
    def test_collect_content_with_invalid_videos(self, mock_search, content_collector):
        """Test la collecte avec des vidéos invalides"""
        # Configuration de vidéos invalides
        invalid_video = MagicMock()
        invalid_video.video_id = "invalid_id"
        invalid_video.views = 0  # Trop peu de vues
        
        mock_search.return_value.results = [invalid_video]
        
        # Test de la collecte
        videos = content_collector.collect_content("test query")
        
        assert len(videos) == 0

def test_init(test_config, setup_test_environment):
    collector = ContentCollector(test_config)
    assert collector.config is not None
    assert collector.logger is not None
    assert collector.downloads_dir.exists()

@patch('pytube.Search')
def test_collect_content(mock_search, test_config, setup_test_environment):
    # Simuler un résultat de recherche YouTube
    mock_video = Mock()
    mock_video.title = "Test Video"
    mock_video.video_id = "test123"
    mock_video.watch_url = "https://youtube.com/watch?v=test"
    mock_video.length = 30  # 30 secondes
    mock_video.views = 10000
    mock_video.author = "Test Author"
    mock_video.keywords = ["test", "video"]
    mock_video.description = "Test description"
    mock_video.thumbnail_url = "https://example.com/thumb.jpg"
    
    mock_search.return_value.results = [mock_video]
    
    collector = ContentCollector(test_config)
    videos = collector.collect_content("test query")
    
    assert len(videos) == 1
    assert videos[0]["title"] == "Test Video"
    assert videos[0]["id"] == "test123"
    assert videos[0]["length"] == 30

@patch('pytube.YouTube')
def test_process_video(mock_youtube, test_config, setup_test_environment, sample_video_path):
    # Simuler un stream vidéo
    mock_stream = Mock()
    mock_stream.filesize = 1024 * 1024  # 1MB
    mock_stream.resolution = "1080p"
    mock_stream.fps = 30
    mock_stream.download.return_value = sample_video_path
    
    mock_youtube.return_value.streams.filter.return_value = [mock_stream]
    mock_youtube.return_value.title = "Test Video"
    mock_youtube.return_value.length = 30
    mock_youtube.return_value.video_id = "test123"
    mock_youtube.return_value.author = "Test Author"
    mock_youtube.return_value.views = 10000
    mock_youtube.return_value.keywords = ["test"]
    mock_youtube.return_value.description = "Test description"
    mock_youtube.return_value.thumbnail_url = "https://example.com/thumb.jpg"
    
    collector = ContentCollector(test_config)
    video_data = collector._process_video(mock_youtube.return_value)
    
    assert video_data is not None
    assert video_data["title"] == "Test Video"
    assert video_data["length"] == 30
    assert video_data["local_path"] == str(sample_video_path)

def test_process_video_too_long(test_config):
    collector = ContentCollector(test_config)
    
    with patch('pytube.YouTube') as mock_youtube:
        mock_youtube.return_value.length = 3600  # 1 heure
        
        video_data = collector._process_video(mock_youtube.return_value)
        assert video_data is None

def test_save_metadata(test_config, setup_test_environment):
    collector = ContentCollector(test_config)
    videos = [{
        "id": "test123",
        "title": "Test Video",
        "length": 30,
        "local_path": "test.mp4"
    }]
    
    metadata_path = Path(setup_test_environment["metadata"]) / "video_metadata.json"
    collector._save_metadata(videos)
    
    assert metadata_path.exists()
    with open(metadata_path) as f:
        saved_data = json.load(f)
    assert saved_data == videos

def test_error_handling(test_config):
    collector = ContentCollector(test_config)
    
    with patch('pytube.YouTube') as mock_youtube:
        mock_youtube.side_effect = Exception("Download Error")
        video_data = collector._process_video(mock_youtube.return_value)
        assert video_data is None

def test_collect_content_with_invalid_videos(test_config):
    collector = ContentCollector(test_config)
    
    with patch('pytube.Search') as mock_search:
        # Simuler des vidéos invalides (trop longues)
        mock_video = Mock()
        mock_video.length = 3600  # 1 heure
        mock_search.return_value.results = [mock_video, mock_video]
        
        videos = collector.collect_content("test query")
        assert len(videos) == 0 