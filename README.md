# 🎥 TikTok Auto Project

Un système automatisé pour la création et la publication de contenu TikTok basé sur les tendances actuelles.

## 🌟 Fonctionnalités

- 🔍 Détection des tendances TikTok en temps réel
- 📥 Récupération automatique de vidéos YouTube pertinentes
- ✂️ Édition automatique des vidéos (sous-titres, titres, descriptions)
- 🎯 Vérification de la qualité audio et visuelle
- 📤 Publication semi-automatique sur TikTok
- 🎛️ Interface utilisateur Streamlit centralisée

## 🚀 Installation

1. Clonez le repository :
```bash
git clone [votre-repo]
cd TikTokAutoProject
```

2. Créez un environnement virtuel :
```bash
python -m venv venv
source venv/bin/activate  # Sur Unix/MacOS
# ou
.\venv\Scripts\activate  # Sur Windows
```

3. Installez les dépendances :
```bash
pip install -r requirements.txt
```

## 🛠️ Configuration

1. Créez un fichier `.env` à la racine du projet
2. Ajoutez vos clés API :
```env
OPENAI_API_KEY=votre_clé_openai
TIKTOK_API_KEY=votre_clé_tiktok
```

## 🎮 Utilisation

Lancez l'interface Streamlit :
```bash
streamlit run Orchestrator/main.py
```

## 📁 Structure du Projet

```
/TikTokAutoProject/
|-- /TrendHunter/         # Détection des tendances
|-- /ContentCollector/    # Récupération de contenu
|-- /ClipMaster/         # Édition de vidéos
|-- /QualityChecker/     # Vérification qualité
|-- /AutoPublisher/      # Publication
|-- /Orchestrator/       # Interface principale
|-- /downloads/          # Stockage temporaire
|-- /outputs/           # Vidéos finales
|-- /config/            # Configuration
```

## 📝 License

MIT License

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou un pull request. 