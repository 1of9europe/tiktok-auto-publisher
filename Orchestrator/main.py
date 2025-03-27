import streamlit as st
import sys
import os
import json
from pathlib import Path

# Ajout du répertoire parent au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

# Import des modules
from TrendHunter.trend_hunter import TrendHunter
from ContentCollector.content_collector import ContentCollector
from ClipMaster.clip_master import ClipMaster
from QualityChecker.quality_checker import QualityChecker
from AutoPublisher.auto_publisher import AutoPublisher

class Orchestrator:
    def __init__(self):
        self.load_config()
        self.setup_modules()
        
    def load_config(self):
        config_path = Path(__file__).parent.parent / "config" / "settings.json"
        with open(config_path) as f:
            self.config = json.load(f)
            
    def setup_modules(self):
        self.trend_hunter = TrendHunter(self.config)
        self.content_collector = ContentCollector(self.config)
        self.clip_master = ClipMaster(self.config)
        self.quality_checker = QualityChecker(self.config)
        self.auto_publisher = AutoPublisher(self.config)

def main():
    st.set_page_config(
        page_title="TikTok Auto Manager",
        page_icon="🎥",
        layout="wide"
    )
    
    st.title("🎥 TikTok Auto Manager")
    
    try:
        orchestrator = Orchestrator()
    except Exception as e:
        st.error(f"Erreur d'initialisation: {str(e)}")
        return
    
    # Sidebar pour la navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choisissez une section:",
        ["Tendances", "Collecte", "Édition", "Qualité", "Publication"]
    )
    
    # Pages principales
    if page == "Tendances":
        st.header("🔍 Détection des Tendances")
        if st.button("Rechercher les tendances"):
            with st.spinner("Analyse des tendances en cours..."):
                try:
                    trends = orchestrator.trend_hunter.find_trends()
                    st.success("Tendances trouvées!")
                    st.json(trends)
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
                    
    elif page == "Collecte":
        st.header("📥 Collecte de Contenu")
        keywords = st.text_input("Mots-clés de recherche")
        if st.button("Collecter du contenu"):
            with st.spinner("Recherche de vidéos..."):
                try:
                    videos = orchestrator.content_collector.collect_content(keywords)
                    st.success(f"{len(videos)} vidéos trouvées!")
                    for video in videos:
                        st.video(video['preview_url'])
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
                    
    elif page == "Édition":
        st.header("✂️ Édition de Vidéos")
        # Interface d'édition
        
    elif page == "Qualité":
        st.header("🎯 Vérification de la Qualité")
        # Interface de vérification
        
    elif page == "Publication":
        st.header("📤 Publication")
        # Interface de publication

if __name__ == "__main__":
    main() 