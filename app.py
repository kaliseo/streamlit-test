import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client

# Configuration page
st.set_page_config(
    page_title="PAC Stats",
    page_icon="🌡️",
    layout="wide"
)

# Configuration Supabase via secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]


@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=60)
def load_data():
    supabase = get_supabase()
    data = supabase.table("pac_stats").select("*").order("timestamp", desc=True).limit(1440).execute()
    df = pd.DataFrame(data.data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp')


# Titre
st.title("🌡️ PAC Stats")

# Chargement des données
try:
    df = load_data()
    latest = df.iloc[-1]

    # Valeurs actuelles en entête (une ligne)
    st.markdown(f"**Extérieur:** {latest['temp_out']:.1f}°C · **Intérieur:** {latest['temp_in']:.1f}°C · **Eau cible:** {latest['water_target']:.1f}°C · **Eau réelle:** {latest['water_avg']:.1f}°C")

    # Graphique à double axe Y
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Axe gauche : Températures air (intérieur / extérieur)
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['temp_out'], name="T° extérieure", line=dict(color="#FF8C00")),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['temp_in'], name="T° intérieure", line=dict(color="#FFD700")),
        secondary_y=False
    )

    # Axe droit : Températures eau (cible / réelle)
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['water_target'], name="Eau cible", line=dict(color="#2ECC71")),
        secondary_y=True
    )
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['water_avg'], name="Eau réelle", line=dict(color="#87CEEB")),
        secondary_y=True
    )

    # Configuration des axes
    fig.update_xaxes(title_text="Date/Heure")
    fig.update_yaxes(title_text="T° air (°C)", secondary_y=False)
    fig.update_yaxes(title_text="T° eau (°C)", secondary_y=True)

    fig.update_layout(
        title="Températures PAC",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erreur: {e}")
