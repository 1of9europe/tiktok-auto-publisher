from TrendHunter.trend_hunter import TrendHunter
import json
from datetime import datetime
from pathlib import Path

def main():
    # Charger la configuration
    with open('config/settings.json') as f:
        config = json.load(f)

    # Initialiser le TrendHunter
    trend_hunter = TrendHunter(config)

    # Détecter les tendances
    print("🔍 Détection des tendances en cours...")
    trends = trend_hunter.find_trends()

    # Créer le dossier de sortie s'il n'existe pas
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    # Sauvegarder les résultats avec un timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'trends_{timestamp}.json'
    
    # Conversion des objets Trend en dictionnaires avec sérialisation datetime
    trends_data = []
    for trend in trends:
        trend_dict = trend.dict()
        trend_dict['timestamp'] = trend_dict['timestamp'].isoformat()
        trends_data.append(trend_dict)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(trends_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Tendances sauvegardées dans {output_file}")
    print("\n📊 Résultats :")
    print(json.dumps(trends_data, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main() 