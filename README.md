# TikTok Auto Publisher

Un outil automatisé pour la création et la publication de contenu sur TikTok.

## 🚀 Fonctionnalités

### 1. Chasseur de Tendances (TrendHunter)
- Surveillance automatique des tendances TikTok
- Analyse des hashtags populaires
- Suivi des tendances Reddit pour inspiration
- Stockage et analyse des données de tendances
- Génération de rapports de tendances

### 2. Collecteur de Contenu (ContentCollector)
- Recherche automatique de contenu sur YouTube
- Filtrage par pertinence et popularité
- Téléchargement intelligent des vidéos
- Extraction des métadonnées
- Gestion des droits d'auteur

### 3. Maître des Clips (ClipMaster)
- Découpage intelligent des vidéos
- Ajout automatique de sous-titres
- Génération de transitions fluides
- Optimisation du format pour TikTok
- Ajout d'effets visuels et sonores

### 4. Vérificateur de Qualité (QualityChecker)
- Analyse de la qualité visuelle
- Vérification de la qualité audio
- Détection des problèmes techniques
- Génération de rapports de qualité
- Recommandations d'amélioration

### 5. Publication Automatique (AutoPublisher)
- Publication automatique sur TikTok
- Gestion des métadonnées
- Optimisation des hashtags
- Suivi des performances
- Génération de rapports de publication

## 🛠️ Installation

1. Cloner le dépôt :
```bash
git clone https://github.com/1of9europe/tiktok-auto-publisher.git
cd tiktok-auto-publisher
```

2. Créer un environnement virtuel :
```bash
python -m venv .venv
source .venv/bin/activate  # Sur Unix/macOS
# ou
.venv\Scripts\activate  # Sur Windows
```

3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement :
```bash
cp .env.example .env
# Éditer .env avec vos clés API
```

## 📝 Configuration

Le fichier de configuration principal (`config.json`) permet de personnaliser :
- Les paramètres de traitement vidéo
- Les seuils de qualité
- Les limites d'API
- Les préférences de publication

## 🧪 Tests

Les tests sont organisés par module :
- `tests/test_trend_hunter.py`
- `tests/test_content_collector.py`
- `tests/test_clip_master.py`
- `tests/test_quality_checker.py`
- `tests/test_auto_publisher.py`

Pour exécuter les tests :
```bash
pytest tests/
```

## 📚 Documentation

La documentation complète est disponible dans le dossier `docs/` :
- [Spécifications Techniques](docs/technical_specs.md)
- [Spécifications Fonctionnelles](docs/functional_specs.md)
- [Guide d'Utilisation](docs/user_guide.md)
- [Tests Gherkin](docs/gherkin_tests.md)

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 👥 Auteurs

- 1of9europe - [@1of9europe](https://github.com/1of9europe)

## 🙏 Remerciements

- OpenAI pour l'API Whisper
- TikTok pour l'API de publication
- La communauté open-source pour les bibliothèques utilisées 