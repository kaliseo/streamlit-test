#!/usr/bin/env python3
"""
Analyse des données PAC pour déterminer la loi d'eau optimale.
Script Python classique (sans Streamlit).
"""

import json
import urllib.request
import urllib.error
import ssl
from typing import Optional

# Configuration Supabase
SUPABASE_URL = "https://qbmxkoqkbbyortxjxrie.supabase.co"
SUPABASE_KEY = "sb_secret_IP5CO_4fvhuGZ_FezZFFig_Noj1g6xe"


def fetch_data(table: str = "pac_history", limit: Optional[int] = None) -> list:
    """Récupère les données depuis Supabase via l'API REST."""

    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    if limit:
        url += f"&limit={limit}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, headers=headers)

    # Désactiver la vérification SSL si nécessaire (dev only)
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except urllib.error.HTTPError as e:
        print(f"Erreur HTTP {e.code}: {e.reason}")
        return []
    except urllib.error.URLError as e:
        print(f"Erreur de connexion: {e.reason}")
        return []


def detect_columns(data: list) -> dict:
    """Détecte automatiquement les colonnes pertinentes."""
    if not data:
        return {}

    columns = {}
    available_cols = list(data[0].keys())

    patterns = {
        'temp_ext': ['temp_ext', 'temperature_exterieure', 'outdoor', 't_ext', 'text', 'outside', 'ext'],
        'temp_eau': ['temp_eau', 'temperature_eau', 'water', 't_eau', 'teau', 'flow', 'depart', 'eau'],
        'temp_int': ['temp_int', 'temperature_interieure', 'indoor', 't_int', 'tint', 'inside', 'int'],
        'timestamp': ['timestamp', 'date', 'datetime', 'created_at', 'time', 'recorded'],
    }

    for col in available_cols:
        col_lower = col.lower()
        for key, pats in patterns.items():
            if any(p in col_lower for p in pats):
                if key not in columns:
                    columns[key] = col
                break

    return columns


def calculate_linear_regression(x: list, y: list) -> dict:
    """Calcule une régression linéaire simple sans numpy/scipy."""
    n = len(x)
    if n < 2:
        return {"error": "Pas assez de points"}

    # Moyennes
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calcul de la pente et de l'ordonnée à l'origine
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return {"error": "Division par zéro"}

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    # Calcul du R²
    y_pred = [slope * x[i] + intercept for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))

    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    rmse = (ss_res / n) ** 0.5

    return {
        'slope': slope,
        'intercept': intercept,
        'r2': r2,
        'rmse': rmse
    }


def analyze_heating_curve(data: list, temp_ext_col: str, temp_eau_col: str) -> dict:
    """Analyse la loi d'eau à partir des données."""

    results = {
        'data_points': len(data),
        'columns_used': {
            'temp_ext': temp_ext_col,
            'temp_eau': temp_eau_col
        }
    }

    # Extraire et filtrer les données
    valid_points = []
    for row in data:
        try:
            t_ext = float(row.get(temp_ext_col, 0))
            t_eau = float(row.get(temp_eau_col, 0))

            # Filtrer les valeurs aberrantes
            if -20 <= t_ext <= 25 and 20 <= t_eau <= 65:
                valid_points.append((t_ext, t_eau))
        except (ValueError, TypeError):
            continue

    if len(valid_points) < 10:
        return {"error": f"Pas assez de données valides ({len(valid_points)} points)"}

    results['valid_points'] = len(valid_points)

    # Séparer les coordonnées
    x = [p[0] for p in valid_points]
    y = [p[1] for p in valid_points]

    # Statistiques de base
    results['stats'] = {
        'temp_ext_min': min(x),
        'temp_ext_max': max(x),
        'temp_ext_mean': sum(x) / len(x),
        'temp_eau_min': min(y),
        'temp_eau_max': max(y),
        'temp_eau_mean': sum(y) / len(y),
    }

    # Régression linéaire
    regression = calculate_linear_regression(x, y)

    if 'error' in regression:
        return {"error": regression['error']}

    results['linear_model'] = regression
    results['equation'] = f"T_eau = {regression['slope']:.2f} × T_ext + {regression['intercept']:.1f}"

    # Points de référence
    slope = regression['slope']
    intercept = regression['intercept']

    results['reference_points'] = {
        'T_eau_at_-10C': round(slope * (-10) + intercept, 1),
        'T_eau_at_0C': round(slope * 0 + intercept, 1),
        'T_eau_at_5C': round(slope * 5 + intercept, 1),
        'T_eau_at_10C': round(slope * 10 + intercept, 1),
        'T_eau_at_15C': round(slope * 15 + intercept, 1),
    }

    # Analyse de la pente
    if slope > -0.8:
        slope_analysis = "FAIBLE - Logement très bien isolé"
        recommendations = [
            "Excellent ! Votre logement est très bien isolé.",
            "Vous pouvez utiliser des températures d'eau basses (meilleur COP).",
            "Envisagez le mode basse température si disponible."
        ]
    elif slope > -1.2:
        slope_analysis = "MOYENNE - Isolation standard"
        recommendations = [
            "Isolation correcte pour un logement standard.",
            "Vérifiez l'étanchéité des fenêtres et portes.",
            "L'isolation des combles pourrait améliorer les performances."
        ]
    elif slope > -1.5:
        slope_analysis = "ÉLEVÉE - Isolation à améliorer"
        recommendations = [
            "La PAC doit fournir des températures élevées par temps froid.",
            "Envisagez d'améliorer l'isolation (murs, fenêtres, combles).",
            "Des radiateurs plus grands pourraient réduire la température requise."
        ]
    else:
        slope_analysis = "TRÈS ÉLEVÉE - Isolation insuffisante"
        recommendations = [
            "Attention : températures d'eau très élevées nécessaires.",
            "Le COP de votre PAC est probablement dégradé.",
            "Priorité : travaux d'isolation importants recommandés.",
            "Vérifiez l'absence de ponts thermiques majeurs."
        ]

    results['slope_analysis'] = slope_analysis
    results['recommendations'] = recommendations

    return results


def print_results(results: dict):
    """Affiche les résultats de manière formatée."""

    print("\n" + "=" * 60)
    print("   ANALYSE DE LA LOI D'EAU OPTIMALE")
    print("=" * 60)

    if 'error' in results:
        print(f"\n❌ ERREUR: {results['error']}")
        return

    print(f"\n📊 DONNÉES ANALYSÉES")
    print(f"   Points totaux: {results['data_points']}")
    print(f"   Points valides: {results['valid_points']}")
    print(f"   Colonnes: {results['columns_used']}")

    stats = results['stats']
    print(f"\n📈 STATISTIQUES")
    print(f"   T° extérieure: {stats['temp_ext_min']:.1f}°C à {stats['temp_ext_max']:.1f}°C (moy: {stats['temp_ext_mean']:.1f}°C)")
    print(f"   T° eau:        {stats['temp_eau_min']:.1f}°C à {stats['temp_eau_max']:.1f}°C (moy: {stats['temp_eau_mean']:.1f}°C)")

    model = results['linear_model']
    print(f"\n🎯 LOI D'EAU OPTIMALE")
    print(f"   {results['equation']}")
    print(f"   Pente:  {model['slope']:.3f}")
    print(f"   Offset: {model['intercept']:.1f}°C")
    print(f"   R²:     {model['r2']:.4f}")
    print(f"   RMSE:   {model['rmse']:.2f}°C")

    print(f"\n📍 POINTS DE RÉFÉRENCE POUR VOTRE PAC")
    refs = results['reference_points']
    print(f"   À -10°C ext → Eau à {refs['T_eau_at_-10C']}°C")
    print(f"   À   0°C ext → Eau à {refs['T_eau_at_0C']}°C")
    print(f"   À   5°C ext → Eau à {refs['T_eau_at_5C']}°C")
    print(f"   À  10°C ext → Eau à {refs['T_eau_at_10C']}°C")
    print(f"   À  15°C ext → Eau à {refs['T_eau_at_15C']}°C")

    print(f"\n💡 ANALYSE DE LA PENTE")
    print(f"   Type: {results['slope_analysis']}")

    print(f"\n📋 RECOMMANDATIONS")
    for rec in results['recommendations']:
        print(f"   • {rec}")

    print("\n" + "=" * 60)
    print("   PARAMÈTRES À CONFIGURER SUR VOTRE PAC")
    print("=" * 60)
    print(f"""
   Pente (slope):     {model['slope']:.2f}
   Décalage (offset): {model['intercept']:.1f}°C

   Ou utilisez les points de référence ci-dessus
   pour configurer la courbe manuellement.
""")


def main():
    print("🔄 Connexion à Supabase...")

    # Charger les données
    data = fetch_data("pac_history")

    if not data:
        print("❌ Impossible de charger les données.")
        print("   Vérifiez votre connexion et vos identifiants Supabase.")
        return

    print(f"✅ {len(data)} enregistrements chargés")

    # Détecter les colonnes
    columns = detect_columns(data)
    print(f"📋 Colonnes détectées: {columns}")
    print(f"📋 Colonnes disponibles: {list(data[0].keys())}")

    if 'temp_ext' not in columns or 'temp_eau' not in columns:
        print("\n⚠️  Colonnes température non détectées automatiquement.")
        print("    Colonnes disponibles:", list(data[0].keys()))
        print("\n    Veuillez modifier le script pour spécifier les bonnes colonnes.")
        return

    # Analyser
    results = analyze_heating_curve(data, columns['temp_ext'], columns['temp_eau'])

    # Afficher les résultats
    print_results(results)


if __name__ == "__main__":
    main()
