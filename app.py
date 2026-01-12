#!/usr/bin/env python3
"""
Application Streamlit pour analyser les données PAC et déterminer la loi d'eau optimale.
"""

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(
    page_title="Analyse Loi d'Eau PAC",
    page_icon="🌡️",
    layout="wide"
)

st.title("🌡️ Analyse de la Loi d'Eau Optimale")
st.markdown("---")

# Configuration Supabase
SUPABASE_URL = "https://qbmxkoqkbbyortxjxrie.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_secret_IP5CO_4fvhuGZ_FezZFFig_Noj1g6xe")


@st.cache_resource
def get_supabase_client() -> Client:
    """Initialise le client Supabase."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=300)
def load_pac_history() -> pd.DataFrame:
    """Charge les données de la table pac_history."""
    supabase = get_supabase_client()
    response = supabase.table("pac_history").select("*").execute()

    if response.data:
        df = pd.DataFrame(response.data)
        return df
    return pd.DataFrame()


def detect_columns(df: pd.DataFrame) -> dict:
    """Détecte automatiquement les colonnes pertinentes."""
    columns = {}

    # Patterns pour détecter les colonnes
    temp_ext_patterns = ['temp_ext', 'temperature_exterieure', 'outdoor_temp', 't_ext', 'text', 'outside']
    temp_eau_patterns = ['temp_eau', 'temperature_eau', 'water_temp', 't_eau', 'teau', 'flow_temp', 'temp_depart']
    temp_int_patterns = ['temp_int', 'temperature_interieure', 'indoor_temp', 't_int', 'tint', 'inside']
    consigne_patterns = ['consigne', 'setpoint', 'target', 'cible']
    timestamp_patterns = ['timestamp', 'date', 'datetime', 'created_at', 'time']
    cop_patterns = ['cop', 'coefficient', 'performance']
    power_patterns = ['power', 'puissance', 'watt', 'consumption', 'conso']

    for col in df.columns:
        col_lower = col.lower()

        if any(p in col_lower for p in temp_ext_patterns):
            columns['temp_ext'] = col
        elif any(p in col_lower for p in temp_eau_patterns):
            columns['temp_eau'] = col
        elif any(p in col_lower for p in temp_int_patterns):
            columns['temp_int'] = col
        elif any(p in col_lower for p in consigne_patterns):
            columns['consigne'] = col
        elif any(p in col_lower for p in timestamp_patterns):
            columns['timestamp'] = col
        elif any(p in col_lower for p in cop_patterns):
            columns['cop'] = col
        elif any(p in col_lower for p in power_patterns):
            columns['power'] = col

    return columns


def linear_heating_curve(t_ext, slope, offset):
    """Loi d'eau linéaire: T_eau = slope * T_ext + offset"""
    return slope * t_ext + offset


def quadratic_heating_curve(t_ext, a, b, c):
    """Loi d'eau quadratique: T_eau = a*T_ext² + b*T_ext + c"""
    return a * t_ext**2 + b * t_ext + c


def calculate_optimal_heating_curve(df: pd.DataFrame, temp_ext_col: str, temp_eau_col: str,
                                    temp_int_col: str = None, consigne_col: str = None) -> dict:
    """Calcule la loi d'eau optimale basée sur les données historiques."""

    results = {}

    # Nettoyage des données
    df_clean = df[[temp_ext_col, temp_eau_col]].dropna()

    if temp_int_col and temp_int_col in df.columns:
        df_clean[temp_int_col] = df[temp_int_col]
    if consigne_col and consigne_col in df.columns:
        df_clean[consigne_col] = df[consigne_col]

    df_clean = df_clean[df_clean[temp_ext_col].between(-20, 25)]
    df_clean = df_clean[df_clean[temp_eau_col].between(20, 65)]

    if len(df_clean) < 10:
        return {"error": "Pas assez de données pour l'analyse"}

    t_ext = df_clean[temp_ext_col].values
    t_eau = df_clean[temp_eau_col].values

    # Régression linéaire
    try:
        popt_linear, _ = curve_fit(linear_heating_curve, t_ext, t_eau)
        slope, offset = popt_linear

        t_eau_pred_linear = linear_heating_curve(t_ext, slope, offset)
        r2_linear = 1 - (np.sum((t_eau - t_eau_pred_linear)**2) / np.sum((t_eau - np.mean(t_eau))**2))
        rmse_linear = np.sqrt(np.mean((t_eau - t_eau_pred_linear)**2))

        results['linear'] = {
            'slope': slope,
            'offset': offset,
            'r2': r2_linear,
            'rmse': rmse_linear,
            'equation': f"T_eau = {slope:.2f} × T_ext + {offset:.1f}"
        }
    except Exception as e:
        results['linear'] = {"error": str(e)}

    # Régression quadratique
    try:
        popt_quad, _ = curve_fit(quadratic_heating_curve, t_ext, t_eau)
        a, b, c = popt_quad

        t_eau_pred_quad = quadratic_heating_curve(t_ext, a, b, c)
        r2_quad = 1 - (np.sum((t_eau - t_eau_pred_quad)**2) / np.sum((t_eau - np.mean(t_eau))**2))
        rmse_quad = np.sqrt(np.mean((t_eau - t_eau_pred_quad)**2))

        results['quadratic'] = {
            'a': a,
            'b': b,
            'c': c,
            'r2': r2_quad,
            'rmse': rmse_quad,
            'equation': f"T_eau = {a:.3f} × T_ext² + {b:.2f} × T_ext + {c:.1f}"
        }
    except Exception as e:
        results['quadratic'] = {"error": str(e)}

    # Statistiques générales
    results['stats'] = {
        'n_points': len(df_clean),
        'temp_ext_min': t_ext.min(),
        'temp_ext_max': t_ext.max(),
        'temp_ext_mean': t_ext.mean(),
        'temp_eau_min': t_eau.min(),
        'temp_eau_max': t_eau.max(),
        'temp_eau_mean': t_eau.mean(),
    }

    # Analyse par tranches de température
    bins = [-20, -10, 0, 5, 10, 15, 20, 25]
    df_clean['temp_bin'] = pd.cut(df_clean[temp_ext_col], bins=bins)
    bin_analysis = df_clean.groupby('temp_bin', observed=True)[temp_eau_col].agg(['mean', 'std', 'count'])
    results['bin_analysis'] = bin_analysis.to_dict()

    # Recommandations
    if 'linear' in results and 'error' not in results['linear']:
        slope = results['linear']['slope']
        offset = results['linear']['offset']

        # Points de référence standards
        t_eau_at_minus10 = linear_heating_curve(-10, slope, offset)
        t_eau_at_0 = linear_heating_curve(0, slope, offset)
        t_eau_at_plus15 = linear_heating_curve(15, slope, offset)

        results['reference_points'] = {
            'T_eau @ -10°C ext': round(t_eau_at_minus10, 1),
            'T_eau @ 0°C ext': round(t_eau_at_0, 1),
            'T_eau @ 15°C ext': round(t_eau_at_plus15, 1),
        }

        # Classification de la pente
        if slope > -1.0:
            pente_type = "faible (logement bien isolé)"
        elif slope > -1.5:
            pente_type = "moyenne (isolation standard)"
        else:
            pente_type = "forte (isolation à améliorer)"

        results['recommendations'] = {
            'pente_type': pente_type,
            'slope_value': slope,
        }

    return results


def plot_heating_curve(df: pd.DataFrame, temp_ext_col: str, temp_eau_col: str, results: dict) -> go.Figure:
    """Crée un graphique de la loi d'eau."""

    df_clean = df[[temp_ext_col, temp_eau_col]].dropna()
    df_clean = df_clean[df_clean[temp_ext_col].between(-20, 25)]
    df_clean = df_clean[df_clean[temp_eau_col].between(20, 65)]

    fig = go.Figure()

    # Points de données
    fig.add_trace(go.Scatter(
        x=df_clean[temp_ext_col],
        y=df_clean[temp_eau_col],
        mode='markers',
        name='Données mesurées',
        marker=dict(size=5, opacity=0.5, color='blue'),
    ))

    # Courbe linéaire optimale
    if 'linear' in results and 'error' not in results['linear']:
        t_ext_range = np.linspace(-15, 20, 100)
        t_eau_linear = linear_heating_curve(
            t_ext_range,
            results['linear']['slope'],
            results['linear']['offset']
        )
        fig.add_trace(go.Scatter(
            x=t_ext_range,
            y=t_eau_linear,
            mode='lines',
            name=f"Loi linéaire (R²={results['linear']['r2']:.3f})",
            line=dict(color='red', width=3),
        ))

    # Courbe quadratique
    if 'quadratic' in results and 'error' not in results['quadratic']:
        t_ext_range = np.linspace(-15, 20, 100)
        t_eau_quad = quadratic_heating_curve(
            t_ext_range,
            results['quadratic']['a'],
            results['quadratic']['b'],
            results['quadratic']['c']
        )
        fig.add_trace(go.Scatter(
            x=t_ext_range,
            y=t_eau_quad,
            mode='lines',
            name=f"Loi quadratique (R²={results['quadratic']['r2']:.3f})",
            line=dict(color='green', width=2, dash='dash'),
        ))

    fig.update_layout(
        title="Loi d'Eau - Température de départ vs Température extérieure",
        xaxis_title="Température extérieure (°C)",
        yaxis_title="Température eau de chauffage (°C)",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        hovermode='closest',
    )

    return fig


def plot_time_series(df: pd.DataFrame, timestamp_col: str, columns: dict) -> go.Figure:
    """Crée un graphique temporel des températures."""

    df_sorted = df.sort_values(timestamp_col)

    fig = go.Figure()

    if 'temp_ext' in columns:
        fig.add_trace(go.Scatter(
            x=df_sorted[timestamp_col],
            y=df_sorted[columns['temp_ext']],
            name='T° extérieure',
            line=dict(color='blue'),
        ))

    if 'temp_eau' in columns:
        fig.add_trace(go.Scatter(
            x=df_sorted[timestamp_col],
            y=df_sorted[columns['temp_eau']],
            name='T° eau',
            line=dict(color='red'),
        ))

    if 'temp_int' in columns:
        fig.add_trace(go.Scatter(
            x=df_sorted[timestamp_col],
            y=df_sorted[columns['temp_int']],
            name='T° intérieure',
            line=dict(color='green'),
        ))

    fig.update_layout(
        title="Évolution des températures dans le temps",
        xaxis_title="Date/Heure",
        yaxis_title="Température (°C)",
        hovermode='x unified',
    )

    return fig


# Interface principale
def main():
    try:
        with st.spinner("Chargement des données depuis Supabase..."):
            df = load_pac_history()

        if df.empty:
            st.error("❌ Aucune donnée trouvée dans la table pac_history")
            st.info("Vérifiez que la table contient des données et que les identifiants sont corrects.")
            return

        st.success(f"✅ {len(df)} enregistrements chargés")

        # Affichage des colonnes disponibles
        st.subheader("📊 Structure des données")

        with st.expander("Voir les colonnes disponibles"):
            st.write("**Colonnes détectées:**", list(df.columns))
            st.write("**Aperçu des données:**")
            st.dataframe(df.head(10))

        # Détection automatique des colonnes
        detected = detect_columns(df)

        st.subheader("⚙️ Configuration des colonnes")

        col1, col2 = st.columns(2)

        with col1:
            temp_ext_col = st.selectbox(
                "Colonne température extérieure",
                options=df.columns.tolist(),
                index=df.columns.tolist().index(detected.get('temp_ext', df.columns[0])) if detected.get('temp_ext') in df.columns else 0
            )

            temp_eau_col = st.selectbox(
                "Colonne température eau",
                options=df.columns.tolist(),
                index=df.columns.tolist().index(detected.get('temp_eau', df.columns[0])) if detected.get('temp_eau') in df.columns else 0
            )

        with col2:
            timestamp_col = st.selectbox(
                "Colonne timestamp",
                options=['(aucune)'] + df.columns.tolist(),
                index=df.columns.tolist().index(detected.get('timestamp', df.columns[0])) + 1 if detected.get('timestamp') in df.columns else 0
            )

            temp_int_col = st.selectbox(
                "Colonne température intérieure (optionnel)",
                options=['(aucune)'] + df.columns.tolist(),
                index=df.columns.tolist().index(detected.get('temp_int', df.columns[0])) + 1 if detected.get('temp_int') in df.columns else 0
            )

        st.markdown("---")

        # Analyse
        if st.button("🔍 Analyser et calculer la loi d'eau optimale", type="primary"):

            with st.spinner("Analyse en cours..."):
                results = calculate_optimal_heating_curve(
                    df,
                    temp_ext_col,
                    temp_eau_col,
                    temp_int_col if temp_int_col != '(aucune)' else None
                )

            if 'error' in results:
                st.error(f"❌ Erreur: {results['error']}")
                return

            # Affichage des résultats
            st.subheader("📈 Résultats de l'analyse")

            # Métriques principales
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Points analysés", results['stats']['n_points'])
            with col2:
                st.metric("T° ext. min", f"{results['stats']['temp_ext_min']:.1f}°C")
            with col3:
                st.metric("T° ext. max", f"{results['stats']['temp_ext_max']:.1f}°C")
            with col4:
                st.metric("T° eau moyenne", f"{results['stats']['temp_eau_mean']:.1f}°C")

            # Graphique principal
            fig = plot_heating_curve(df, temp_ext_col, temp_eau_col, results)
            st.plotly_chart(fig, use_container_width=True)

            # Résultats détaillés
            st.subheader("🎯 Loi d'eau optimale")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Modèle Linéaire")
                if 'linear' in results and 'error' not in results['linear']:
                    st.success(f"**Équation:** {results['linear']['equation']}")
                    st.write(f"- **Pente:** {results['linear']['slope']:.2f}")
                    st.write(f"- **Offset:** {results['linear']['offset']:.1f}°C")
                    st.write(f"- **R²:** {results['linear']['r2']:.4f}")
                    st.write(f"- **RMSE:** {results['linear']['rmse']:.2f}°C")
                else:
                    st.error("Impossible de calculer le modèle linéaire")

            with col2:
                st.markdown("### Modèle Quadratique")
                if 'quadratic' in results and 'error' not in results['quadratic']:
                    st.info(f"**Équation:** {results['quadratic']['equation']}")
                    st.write(f"- **R²:** {results['quadratic']['r2']:.4f}")
                    st.write(f"- **RMSE:** {results['quadratic']['rmse']:.2f}°C")
                else:
                    st.error("Impossible de calculer le modèle quadratique")

            # Points de référence
            if 'reference_points' in results:
                st.subheader("📍 Points de référence pour votre PAC")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "T° eau @ -10°C ext",
                        f"{results['reference_points']['T_eau @ -10°C ext']}°C",
                        help="Température d'eau recommandée quand il fait -10°C dehors"
                    )
                with col2:
                    st.metric(
                        "T° eau @ 0°C ext",
                        f"{results['reference_points']['T_eau @ 0°C ext']}°C",
                        help="Température d'eau recommandée quand il fait 0°C dehors"
                    )
                with col3:
                    st.metric(
                        "T° eau @ 15°C ext",
                        f"{results['reference_points']['T_eau @ 15°C ext']}°C",
                        help="Température d'eau recommandée quand il fait 15°C dehors"
                    )

            # Recommandations
            if 'recommendations' in results:
                st.subheader("💡 Recommandations")

                rec = results['recommendations']

                st.info(f"""
                **Type de pente détectée:** {rec['pente_type']}

                **Valeur de la pente:** {rec['slope_value']:.2f}
                """)

                # Conseils basés sur l'analyse
                slope = rec['slope_value']

                if slope > -0.8:
                    st.success("""
                    ✅ **Excellent!** Votre logement semble très bien isolé.

                    - La faible pente indique que peu d'augmentation de température d'eau est nécessaire quand il fait froid
                    - Votre PAC fonctionne dans des conditions optimales
                    - Possibilité d'utiliser des températures d'eau basses (meilleur COP)
                    """)
                elif slope > -1.2:
                    st.info("""
                    ℹ️ **Bon** - Isolation correcte.

                    - Pente typique d'un logement avec isolation standard
                    - Vérifiez l'étanchéité des fenêtres et portes
                    - Envisagez d'isoler les combles si ce n'est pas fait
                    """)
                else:
                    st.warning("""
                    ⚠️ **Attention** - Pente élevée détectée.

                    - Votre logement nécessite des températures d'eau élevées par temps froid
                    - Cela peut réduire le COP de votre PAC
                    - Recommandations:
                      - Améliorer l'isolation (murs, combles, fenêtres)
                      - Vérifier l'absence de ponts thermiques
                      - Envisager des radiateurs plus grands ou un plancher chauffant
                    """)

            # Graphique temporel
            if timestamp_col != '(aucune)':
                st.subheader("📅 Évolution temporelle")

                selected_cols = {'temp_ext': temp_ext_col, 'temp_eau': temp_eau_col}
                if temp_int_col != '(aucune)':
                    selected_cols['temp_int'] = temp_int_col

                fig_time = plot_time_series(df, timestamp_col, selected_cols)
                st.plotly_chart(fig_time, use_container_width=True)

            # Export des paramètres
            st.subheader("📤 Paramètres à configurer sur votre PAC")

            if 'linear' in results and 'error' not in results['linear']:
                st.code(f"""
# Paramètres de loi d'eau à configurer sur votre pompe à chaleur:

Pente (slope):     {results['linear']['slope']:.2f}
Décalage (offset): {results['linear']['offset']:.1f}°C

# Points de référence:
À -10°C extérieur → Eau à {results['reference_points']['T_eau @ -10°C ext']}°C
À   0°C extérieur → Eau à {results['reference_points']['T_eau @ 0°C ext']}°C
À  15°C extérieur → Eau à {results['reference_points']['T_eau @ 15°C ext']}°C
                """)

    except Exception as e:
        st.error(f"❌ Erreur lors du chargement: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()
