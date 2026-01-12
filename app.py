import streamlit as st
import pandas as pd
import plotly.express as px
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

    # Graphique températures
    fig1 = px.line(
        df,
        x='timestamp',
        y=['temp_in', 'water_avg'],
        title="Températures",
        labels={'value': 'Température (°C)', 'timestamp': 'Date/Heure', 'variable': 'Mesure'}
    )
    fig1.update_layout(hovermode='x unified')
    st.plotly_chart(fig1, use_container_width=True)

    # Graphique loi d'eau
    fig2 = px.line(
        df,
        x='timestamp',
        y=['law_min', 'law_max'],
        title="Loi d'eau",
        labels={'value': 'Température (°C)', 'timestamp': 'Date/Heure', 'variable': 'Limite'}
    )
    fig2.update_layout(hovermode='x unified')
    st.plotly_chart(fig2, use_container_width=True)

except Exception as e:
    st.error(f"Erreur: {e}")
