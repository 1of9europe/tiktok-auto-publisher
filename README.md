# TikTok Auto Publisher

Un outil automatisé pour la collecte, l'édition et la publication de vidéos sur TikTok.

## 🚀 Fonctionnalités

- 🔍 Détection automatique des tendances TikTok
- 📥 Téléchargement intelligent de contenu
- ✂️ Édition automatique des vidéos
- 🎯 Optimisation des hashtags
- 📊 Analyse des performances
- 🔄 Publication automatisée

## 📋 Prérequis

- Python 3.10 ou supérieur
- FFmpeg installé sur votre système
- Compte TikTok avec accès API

### Installation de FFmpeg

#### macOS
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

#### Windows
Téléchargez FFmpeg depuis [le site officiel](https://ffmpeg.org/download.html)

## 🛠️ Installation

1. Clonez le dépôt :
```bash
git clone https://github.com/1of9europe/tiktok-auto-publisher.git
cd tiktok-auto-publisher
```

2. Créez un environnement virtuel et activez-le :
```bash
python3 -m venv .venv
source .venv/bin/activate  # Sur Unix/macOS
# ou
.venv\Scripts\activate  # Sur Windows
```

3. Installez les dépendances :
```bash
pip install -r requirements.txt
```

## 📁 Structure du Projet

```
tiktok-auto-publisher/
├── src/
│   ├── trend_hunter/
│   │   └── trend_hunter.py
│   ├── content_collector/
│   │   └── content_collector.py
│   ├── clip_master/
│   │   └── clip_master.py
│   ├── quality_checker/
│   │   └── quality_checker.py
│   └── auto_publisher/
│       └── auto_publisher.py
├── tests/
│   ├── test_trend_hunter.py
│   ├── test_content_collector.py
│   ├── test_clip_master.py
│   ├── test_quality_checker.py
│   └── test_auto_publisher.py
├── config/
│   └── config.yaml
├── requirements.txt
└── README.md
```

## 🔧 Configuration

1. Créez un fichier `.env` à la racine du projet :
```env
TIKTOK_API_KEY=votre_clé_api
TIKTOK_API_SECRET=votre_secret_api
```

2. Configurez les paramètres dans `config/config.yaml` :
```yaml
trend_hunter:
  update_interval: 3600  # secondes
  max_trends: 10

content_collector:
  max_videos: 5
  min_duration: 15
  max_duration: 60

clip_master:
  output_dir: "output"
  max_clips: 3

quality_checker:
  min_brightness: 0.5
  min_contrast: 0.5
  min_sharpness: 0.5
  min_volume: 0.5
  max_noise: 0.3

auto_publisher:
  max_file_size: 512000  # 512MB
  max_title_length: 150
  max_description_length: 2200
  max_hashtags: 30
```

## 🧪 Tests

Pour exécuter les tests :
```bash
pytest tests/
```

## 📝 Utilisation

1. Lancez le programme :
```bash
python src/main.py
```

2. Le programme va :
   - Analyser les tendances TikTok
   - Télécharger le contenu pertinent
   - Éditer les vidéos
   - Vérifier la qualité
   - Publier automatiquement

## 📦 Dépendances Principales

- beautifulsoup4==4.12.2
- requests==2.31.0
- pytube==15.0.0
- moviepy==1.0.3
- openai-whisper==20231117
- openai==1.3.5
- opencv-python-headless==4.8.1.78
- librosa==0.10.1
- streamlit==1.29.0

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
1. Fork le projet
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 👥 Auteurs

- 1of9europe

## 🙏 Remerciements

- OpenAI pour Whisper
- La communauté open-source pour les bibliothèques utilisées 