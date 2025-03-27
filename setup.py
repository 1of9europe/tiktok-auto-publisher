from setuptools import setup, find_namespace_packages

setup(
    name="tiktok_auto",
    version="0.1.0",
    packages=find_namespace_packages(include=[
        "TrendHunter*",
        "ContentCollector*",
        "ClipMaster*",
        "QualityChecker*",
        "AutoPublisher*",
        "Orchestrator*"
    ]),
    install_requires=[
        "beautifulsoup4>=4.12.2",
        "requests>=2.31.0",
        "pytube>=15.0.0",
        "moviepy>=1.0.3",
        "openai-whisper>=20231117",
        "openai>=1.3.5",
        "opencv-python-headless>=4.8.1.78",
        "librosa>=0.10.1",
        "streamlit>=1.29.0",
        "python-dotenv>=1.0.0",
        "google-api-python-client>=2.108.0",
        "pydub>=0.25.1",
        "numpy>=1.24.3",
        "pandas>=2.1.3",
        "scipy>=1.11.0",
        "pooch>=1.7.0",
        "soundfile>=0.12.1",
        "ffmpeg-python>=0.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-mock>=3.12.0",
        ],
    },
) 