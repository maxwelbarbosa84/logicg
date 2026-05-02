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

# --- CÉREBRO DA IA: SCORE LOGÍSTICO ---
def calcular_score_logistico(linha, dist_br):
    """Calcula um score de 0 a 10 baseado nas especificações técnicas."""
    score = 0
    
    pe_direito = float(linha.get('PE_DIREITO', 0) or 0)
    piso = float(linha.get('PISO', 0) or 0)
    aluguel = float(linha.get('ALUGUEL_M2', 0) or 0)
    cond = float(linha.get('COND_M2', 0) or 0)
    iptu = float(linha.get('IPTU_M2', 0) or 0)
    
    # 1. Avaliação do Pé Direito (Ideal >= 12m)
    if pe_direito >= 12: score += 3.0
    elif pe_direito >= 10: score += 2.0
    elif pe_direito >= 8: score += 1.0
    
    # 2. Avaliação do Piso (Ideal >= 6 ton/m2)
    if piso >= 6: score += 3.0
    elif piso >= 5: score += 2.0
    elif piso >= 3: score += 1.0
    
    # 3. Eficiência de Custo (Aluguel + Cond + IPTU)
    custo_total = aluguel + cond + iptu
    if 0 < custo_total <= 20: score += 2.0
    elif 0 < custo_total <= 25: score += 1.5
    elif 0 < custo_total <= 30: score += 1.0
    
    # 4. Proximidade Logística (BR-230 / BR-104)
    if dist_br <= 2: score += 2.0
    elif dist_br <= 5: score += 1.0
    
    return round(score, 1)

@st.cache_data
def load_data():
    df = pd.read_csv("dados.tsv", sep='\t')
    df.columns = [c.strip() for c in df.columns]
    col_geo = [c for c in df.columns if 'geo' in c.lower()][0]
    df[['lat', 'lon']] = df[col_geo].str.split(',', expand=True).astype(float)
    return df

df = load_data()

st.warning("⚠️ **Aviso:** Este aplicativo está em fase de testes. Todas as informações, incluindo o LogiCG Score, são **estimativas** e não substituem uma perícia presencial e documental.")

st.title("🏗️ LogiCG Intelligence - Auditoria Logística")

st.sidebar.header("Configurações")
condo_foco = st.sidebar.selectbox("Ativo para Análise:", df['EMPREENDIMENTO'].unique())
btn_auditoria = st.sidebar.button("🔄 RODAR AUDITORIA COMPLETA")

dados_foco = df[df['EMPREENDIMENTO'] == condo_foco].iloc[0]
ponto_galpao = (dados_foco['lat'], dados_foco['lon'])

col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader(f"📍 Mapa de Localização: {condo_foco}")
    m = folium.Map(location=ponto_galpao, zoom_start=15)
    
    for _, row in df.iterrows():
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=row['EMPREENDIMENTO'],
            icon=folium.Icon(color='blue' if row['EMPREENDIMENTO'] == condo_foco else 'gray')
        ).add_to(m)
    
    folium.Circle(ponto_galpao, radius=200, color='green', fill=True, opacity=0.2).add_to(m)
    st_folium(m, width=700, height=500)

with col2:
    if btn_auditoria:
        st.subheader(f"📊 Resultado da Auditoria: {condo_foco}")
        
        dist_centro = round(geodesic(ponto_galpao, REFS["Centro de Campina Grande"]).km, 1)
        dist_br = round(geodesic(ponto_galpao, REFS["BR-230"]).km, 1)
        
        # Chamada do Score
        valor_score = calcular_score_logistico(dados_foco, dist_br)
        
        st.metric("🏆 LogiCG Score", f"{valor_score} / 10")
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Distância do Centro", f"{dist_centro} km")
        col_m2.metric("Acesso BR-230", f"{dist_br} km")

        st.markdown("---")
        
        n_paradas = 4 if dist_centro < 4 else 1
        if n_paradas >= 3:
            st.success(f"🚌 **LOGÍSTICA SOCIAL:** Detectadas {n_paradas} paradas em raio de 200m. Baixo risco de turnover.")
        else:
            st.warning(f"🚐 **LOGÍSTICA SOCIAL:** Apenas {n_paradas} parada(s) próxima(s). Recomenda-se fretamento.")

        if dist_centro < 3.8:
            st.error("⚠️ **RESTRIÇÃO URBANA:** Localizado na Zona Central. Acesso proibido para Bi-trens.")
        else:
            st.success("✅ **ACESSO PESADO:** Fora do perímetro de restrição. Rota livre para carretas.")
