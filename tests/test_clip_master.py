import pytest
from unittest.mock import patch, MagicMock, Mock
from ClipMaster.clip_master import ClipMaster
from pathlib import Path
import json
import numpy as np

class TestClipMaster:
    @pytest.fixture
    def clip_master(self, test_config):
        with patch('whisper.load_model'):
            return ClipMaster(test_config)
    
    @pytest.fixture
    def mock_video_clip(self):
        clip = MagicMock()
        clip.duration = 60
        clip.fps = 30
        clip.size = (1920, 1080)
        return clip
    
    @pytest.fixture
    def mock_whisper_result(self):
        return {
            'text': 'Test transcription',
            'segments': [
                {'start': 0, 'end': 5, 'text': 'First segment'},
                {'start': 5, 'end': 10, 'text': 'Second segment'}
            ]
        }
    
    def test_init(self, clip_master, test_config):
        """Test l'initialisation de ClipMaster"""
        assert clip_master.config == test_config
        assert clip_master.logger is not None
        assert Path(clip_master.outputs_dir).exists()
        
    @patch('moviepy.editor.VideoFileClip')
    def test_process_video(self, mock_video_clip_class, clip_master, mock_video_clip, mock_whisper_result):
        """Test le traitement complet d'une vidéo"""
        # Configuration des mocks
        mock_video_clip_class.return_value = mock_video_clip
        
        with patch.object(clip_master, '_generate_subtitles', return_value=mock_whisper_result):
            with patch.object(clip_master, '_add_subtitles', return_value=mock_video_clip):
                with patch.object(clip_master, '_generate_metadata', return_value={'title': 'Test'}):
                    with patch.object(clip_master, '_save_video', return_value=Path('test_output.mp4')):
                        result = clip_master.process_video('test_video.mp4')
                        
                        assert result['input_path'] == 'test_video.mp4'
                        assert result['metadata']['title'] == 'Test'
                        assert result['subtitles'] == mock_whisper_result
                        
    def test_generate_subtitles(self, clip_master, mock_whisper_result):
        """Test la génération des sous-titres"""
        with patch.object(clip_master.model, 'transcribe', return_value=mock_whisper_result):
            subtitles = clip_master._generate_subtitles('test_video.mp4')
            
            assert subtitles['text'] == 'Test transcription'
            assert len(subtitles['segments']) == 2
            
    @patch('moviepy.editor.TextClip')
    def test_add_subtitles(self, mock_text_clip, clip_master, mock_video_clip, mock_whisper_result):
        """Test l'ajout des sous-titres"""
        # Configuration du mock TextClip
        mock_text_clip.return_value.set_position.return_value.set_duration.return_value.set_start.return_value = MagicMock()
        
        result = clip_master._add_subtitles(mock_video_clip, mock_whisper_result)
        
        assert result is not None
        assert mock_text_clip.call_count == len(mock_whisper_result['segments'])
        
    @patch('openai.ChatCompletion.create')
    def test_generate_metadata(self, mock_openai, clip_master):
        """Test la génération des métadonnées"""
        # Configuration de la réponse OpenAI
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'title': 'Test Title',
            'description': 'Test Description',
            'hashtags': ['#test1', '#test2']
        })
        mock_openai.return_value = mock_response
        
        metadata = clip_master._generate_metadata('test_video.mp4', 'Test transcript')
        
        assert metadata['title'] == 'Test Title'
        assert metadata['description'] == 'Test Description'
        assert len(metadata['hashtags']) == 2
        
    def test_save_video(self, clip_master, mock_video_clip, tmp_path):
        """Test la sauvegarde de la vidéo"""
        # Configuration du répertoire de sortie
        clip_master.outputs_dir = tmp_path
        
        # Métadonnées de test
        metadata = {
            'title': 'Test Title',
            'description': 'Test Description',
            'hashtags': ['#test1', '#test2']
        }
        
        # Test de la sauvegarde
        output_path = clip_master._save_video(mock_video_clip, 'test_input.mp4', metadata)
        
        assert output_path.exists()
        assert output_path.with_suffix('.json').exists()
        
    def test_error_handling(self, clip_master):
        """Test la gestion des erreurs"""
        # Test d'erreur lors de la transcription
        with patch.object(clip_master.model, 'transcribe', side_effect=Exception("Transcription error")):
            with pytest.raises(Exception):
                clip_master._generate_subtitles('test_video.mp4')
                
        # Test d'erreur lors de la génération des métadonnées
        with patch('openai.ChatCompletion.create', side_effect=Exception("OpenAI error")):
            with pytest.raises(Exception):
                clip_master._generate_metadata('test_video.mp4', 'Test transcript')

def test_init(test_config):
    master = ClipMaster(test_config)
    assert master.config is not None
    assert master.logger is not None
    assert master.outputs_dir.exists()

@patch('moviepy.editor.VideoFileClip')
@patch('whisper.load_model')
def test_process_video(mock_whisper, mock_video_clip, test_config, setup_test_environment, sample_video_path):
    # Simuler une vidéo de test
    mock_clip = Mock()
    mock_clip.duration = 30
    mock_clip.size = (1920, 1080)
    mock_clip.fps = 30
    mock_clip.audio = Mock()
    mock_clip.audio.to_soundarray.return_value = np.zeros(44100)  # 1 seconde d'audio
    
    mock_video_clip.return_value = mock_clip
    
    # Simuler la transcription Whisper
    mock_whisper.return_value.transcribe.return_value = {
        "text": "Test transcription",
        "segments": [
            {"start": 0, "end": 5, "text": "Test"}
        ]
    }
    
    master = ClipMaster(test_config)
    output_path = Path(setup_test_environment["processed"]) / "processed.mp4"
    
    result = master.process_video(sample_video_path)
    
    assert result["input_path"] == sample_video_path
    assert "output_path" in result
    assert "metadata" in result
    assert "subtitles" in result

@patch('whisper.load_model')
def test_generate_subtitles(mock_whisper, test_config):
    # Simuler la transcription Whisper
    mock_whisper.return_value.transcribe.return_value = {
        "text": "Test transcription",
        "segments": [
            {"start": 0, "end": 5, "text": "Test"}
        ]
    }
    
    master = ClipMaster(test_config)
    subtitles = master._generate_subtitles("test.mp4")
    
    assert "text" in subtitles
    assert "segments" in subtitles
    assert len(subtitles["segments"]) > 0

@patch('moviepy.editor.VideoFileClip')
def test_add_subtitles(mock_video_clip, test_config):
    # Simuler une vidéo
    mock_clip = Mock()
    mock_clip.duration = 30
    mock_clip.size = (1920, 1080)
    mock_video_clip.return_value = mock_clip
    
    subtitles = {
        "text": "Test transcription",
        "segments": [
            {"start": 0, "end": 5, "text": "Test"}
        ]
    }
    
    master = ClipMaster(test_config)
    final_video = master._add_subtitles(mock_clip, subtitles)
    
    assert final_video is not None
    assert hasattr(final_video, "duration")

def test_generate_metadata(test_config):
    master = ClipMaster(test_config)
    
    metadata = master._generate_metadata("test.mp4", "Test transcription")
    
    assert "title" in metadata
    assert "description" in metadata
    assert "hashtags" in metadata
    assert len(metadata["hashtags"]) > 0

def test_save_metadata(test_config, setup_test_environment):
    master = ClipMaster(test_config)
    
    metadata = {
        "input_path": "input.mp4",
        "output_path": "output.mp4",
        "duration": 30,
        "resolution": "1080x1920",
        "fps": 30
    }
    
    metadata_path = Path(setup_test_environment["metadata"]) / "clip_metadata.json"
    master._save_metadata(metadata, metadata_path)
    
    assert metadata_path.exists()
    with open(metadata_path) as f:
        saved_data = json.load(f)
    assert saved_data == metadata

def test_error_handling(test_config):
    master = ClipMaster(test_config)
    
    # Test avec un fichier inexistant
    with pytest.raises(FileNotFoundError):
        master.process_video("nonexistent.mp4")
    
    # Test avec une erreur de transcription
    with patch('whisper.load_model') as mock_whisper:
        mock_whisper.return_value.transcribe.side_effect = Exception("Transcription error")
        with pytest.raises(Exception, match="Transcription error"):
            master.process_video("test.mp4")

def test_process_video_too_long(test_config, setup_test_environment):
    master = ClipMaster(test_config)
    
    with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
        mock_clip = Mock()
        mock_clip.duration = 3600  # 1 heure
        mock_video_clip.return_value = mock_clip
        
        result = master.process_video("test.mp4", "output.mp4")
        assert result["success"] is False
        assert "duration exceeds maximum" in result["error"]

def test_resize_video(test_config):
    master = ClipMaster(test_config)
    
    with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
        mock_clip = Mock()
        mock_clip.size = (1920, 1080)
        mock_video_clip.return_value = mock_clip
        
        resized_clip = master.resize_video(mock_clip)
        assert resized_clip.size == (1080, 1920)  # Format portrait pour TikTok

def test_adjust_audio(test_config):
    master = ClipMaster(test_config)
    
    with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
        mock_clip = Mock()
        mock_clip.audio = Mock()
        mock_clip.audio.to_soundarray.return_value = np.zeros(44100)
        mock_video_clip.return_value = mock_clip
        
        adjusted_clip = master.adjust_audio(mock_clip)
        assert adjusted_clip.audio is not None

def test_process_video_with_effects(test_config, setup_test_environment):
    master = ClipMaster(test_config)
    
    with patch('moviepy.editor.VideoFileClip') as mock_video_clip:
        mock_clip = Mock()
        mock_clip.duration = 30
        mock_clip.size = (1920, 1080)
        mock_clip.fps = 30
        mock_video_clip.return_value = mock_clip
        
        output_path = Path(setup_test_environment["processed"]) / "effects.mp4"
        result = master.process_video(
            "test.mp4",
            output_path,
            add_transitions=True,
            add_filters=True
        )
        
        assert result["success"] is True
        assert "effects" in result
        assert result["effects"]["transitions"] is True
        assert result["effects"]["filters"] is True 