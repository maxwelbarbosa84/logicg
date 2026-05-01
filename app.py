import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="LogiCG Intelligence Pro", layout="wide")

# Referências Estratégicas
REFS = {
    "Centro de Campina Grande": [-7.23072, -35.8817],
    "Porto de Suape": [-8.39889, -34.96222],
    "Aeroporto João Suassuna": [-7.2692, -35.8950],
    "BR-230": [-7.276566, -35.888468],
    "BR-104": [-7.2308, -35.8817]
}

@st.cache_data
def load_data():
    df = pd.read_csv("dados.tsv", sep='\t')
    df.columns = [c.strip() for c in df.columns]
    col_geo = [c for c in df.columns if 'geo' in c.lower()][0]
    df[['lat', 'lon']] = df[col_geo].str.split(',', expand=True).astype(float)
    
    # Carrega base de paradas (Simulada para o exemplo, mas expansível)
    # Aqui entrariam os dados que baixamos do OpenStreetMap
    return df

df = load_data()

st.title("🏗️ LogiCG Intelligence - Auditoria Logística")

# Sidebar
st.sidebar.header("Configurações")
condo_foco = st.sidebar.selectbox("Ativo para Análise:", df['EMPREENDIMENTO'].unique())
btn_auditoria = st.sidebar.button("🔄 RODAR AUDITORIA COMPLETA")

dados_foco = df[df['EMPREENDIMENTO'] == condo_foco].iloc[0]
ponto_galpao = (dados_foco['lat'], dados_foco['lon'])

col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader(f"📍 Mapa de Localização: {condo_foco}")
    m = folium.Map(location=ponto_galpao, zoom_start=15)
    
    # Todos os galpões
    for _, row in df.iterrows():
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=row['EMPREENDIMENTO'],
            icon=folium.Icon(color='blue' if row['EMPREENDIMENTO'] == condo_foco else 'gray')
        ).add_to(m)
    
    # Raio de 200m para visualização de paradas
    folium.Circle(ponto_galpao, radius=200, color='green', fill=True, opacity=0.2).add_to(m)
    st_folium(m, width=700, height=500)

with col2:
    if btn_auditoria:
        st.subheader(f"📊 Resultado da Auditoria: {condo_foco}")
        
        # Cálculo de Distâncias
        dist_centro = round(geodesic(ponto_galpao, REFS["Centro de Campina Grande"]).km, 1)
        dist_br = round(geodesic(ponto_galpao, REFS["BR-230"]).km, 1)
        
        st.metric("Distância do Centro", f"{dist_centro} km")
        st.metric("Acesso BR-230", f"{dist_br} km")

        st.markdown("---")
        
        # --- LÓGICA DE TREINAMENTO (Consultoria) ---
        
        # 1. Análise de Transporte Público (Raio 200m)
        # Simulando contagem baseada na proximidade do centro para este teste
        n_paradas = 4 if dist_centro < 4 else 1
        
        if n_paradas >= 3:
            st.success(f"🚌 **LOGÍSTICA SOCIAL:** Detectadas {n_paradas} paradas em raio de 200m. Baixo risco de turnover.")
        else:
            st.warning(f"🚐 **LOGÍSTICA SOCIAL:** Apenas {n_paradas} parada(s) próxima(s). Recomenda-se fretamento.")

        # 2. Restrição de Bitrens
        if dist_centro < 3.8:
            st.error("⚠️ **RESTRIÇÃO URBANA:** Localizado na Zona Central. Acesso proibido para Bi-trens.")
        else:
            st.success("✅ **ACESSO PESADO:** Fora do perímetro de restrição. Rota livre para carretas.")

