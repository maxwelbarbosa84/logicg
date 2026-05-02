import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="LogiCG Intelligence Pro", layout="wide")

# =============================================================================
# REFERÊNCIAS ESTRATÉGICAS (NÓS LOGÍSTICOS)
# =============================================================================
REFS = {
    "Centro de Campina Grande": [-7.23072, -35.8817],
    "Porto de Suape":           [-8.39889, -34.96222],
    "Aeroporto CPV":            [-7.2692,  -35.8950],   # Aeroporto João Suassuna
    "Aeroporto JPA":            [-7.1472,  -34.9489],   # Aeroporto de João Pessoa
    # Radar Multiponto — BR-230 (pontos de acesso em CG)
    "ACESSOS_BR230": [
        [-7.2625, -35.9158],   # Acesso 1: Alça Sudoeste (Cruzamento com BR-104)
        [-7.2513, -35.8752],   # Acesso 2: Viaduto da Av. Brasília (Amigão)
        [-7.2341, -35.8619],   # Acesso 3: Saída Leste (Sentido João Pessoa / Partage)
    ],
    # Radar Multiponto — BR-104
    "ACESSOS_BR104": [
        [-7.1800, -35.8817],   # Acesso Norte — sentido Patos / Natal
        [-7.2900, -35.8817],   # Acesso Sul  — sentido Caruaru
    ],
}

# Distância fixa JPA — calculada uma única vez no módulo (cache efetivo)
_COORD_JPA = tuple(REFS["Aeroporto JPA"])


# =============================================================================
# HELPERS — LIMPEZA E SCORE
# =============================================================================
def extrair_numero(valor):
    """Garante que valores com R$ ou vírgulas sejam lidos corretamente."""
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, str):
        valor = (
            valor.upper()
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
    try:
        return float(valor)
    except Exception:
        return 0.0


def calcular_score_logistico(linha, dist_br230, dist_br104):
    """
    Score de 0 a 10 baseado nas especificações técnicas reais do TSV.
    Pesos: Pé-direito (3 pts) | Piso (3 pts) | Custo (2 pts) | Acesso viário (2 pts).
    """
    score = 0.0

    pe_direito = extrair_numero(linha.get("PÉ DIREITO", 0))
    piso       = extrair_numero(linha.get("PISO TON/M²", 0))
    aluguel    = extrair_numero(linha.get("ALUGUEL/M²", 0))
    cond       = extrair_numero(linha.get("CONDOMÍNIO / m²", 0))
    iptu       = extrair_numero(linha.get("IPTU MENSAL / m²", 0))

    # 1. Pé-direito (ideal ≥ 12 m)
    if pe_direito >= 12:
        score += 3.0
    elif pe_direito >= 10:
        score += 2.0
    elif pe_direito >= 8:
        score += 1.0

    # 2. Resistência do piso (ideal ≥ 6 ton/m²)
    if piso >= 6:
        score += 3.0
    elif piso >= 5:
        score += 2.0
    elif piso >= 3:
        score += 1.0

    # 3. Eficiência de custo (aluguel + condomínio + IPTU por m²)
    custo_total = aluguel + cond + iptu
    if 0 < custo_total <= 20:
        score += 2.0
    elif 0 < custo_total <= 25:
        score += 1.5
    elif 0 < custo_total <= 30:
        score += 1.0

    # 4. Proximidade às rodovias federais (melhor acesso entre BR-230 e BR-104)
    melhor_acesso = min(dist_br230, dist_br104)
    if melhor_acesso <= 2:
        score += 2.0
    elif melhor_acesso <= 5:
        score += 1.0

    return round(score, 1)


# =============================================================================
# CARGA DE DADOS
# =============================================================================
@st.cache_data
def load_data():
    df = pd.read_csv("dados.tsv", sep="\t")
    df.columns = [c.strip() for c in df.columns]
    col_geo = [c for c in df.columns if "geo" in c.lower()][0]
    df[["lat", "lon"]] = (
        df[col_geo].str.split(",", expand=True).astype(float)
    )
    return df


@st.cache_data
def calcular_dist_jpa(lat: float, lon: float) -> float:
    """
    Distância até JPA — cacheada por coordenada.
    Como JPA é fixo, st.cache_data evita recalcular para o mesmo galpão.
    """
    return round(geodesic((lat, lon), _COORD_JPA).km, 1)


# =============================================================================
# APP
# =============================================================================
df = load_data()

st.warning(
    "⚠️ **Aviso:** Este aplicativo está em fase de testes. "
    "Todas as informações, incluindo o LogiCG Score, são **estimativas** "
    "e não substituem uma perícia presencial e documental."
)

st.title("🏗️ LogiCG Intelligence — Auditoria Logística")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurações")

score_minimo = st.sidebar.slider(
    "Filtrar mapa: LogiCG Score mínimo",
    min_value=0.0,
    max_value=10.0,
    value=0.0,
    step=0.5,
    help="Exibe no mapa apenas galpões com score igual ou superior ao valor selecionado.",
)

condo_foco = st.sidebar.selectbox(
    "Ativo para Análise Detalhada:",
    df["EMPREENDIMENTO"].unique(),
)
btn_auditoria = st.sidebar.button("🔄 RODAR AUDITORIA COMPLETA")

dados_foco   = df[df["EMPREENDIMENTO"] == condo_foco].iloc[0]
ponto_galpao = (dados_foco["lat"], dados_foco["lon"])

# --- PRÉ-CALCULA SCORES PARA FILTRO DO MAPA ---
def score_row(row):
    pt = (row["lat"], row["lon"])
    d230 = round(min(geodesic(pt, a).km for a in REFS["ACESSOS_BR230"]), 1)
    d104 = round(min(geodesic(pt, a).km for a in REFS["ACESSOS_BR104"]), 1)
    return calcular_score_logistico(row, d230, d104)

df["_score"] = df.apply(score_row, axis=1)
df_filtrado  = df[df["_score"] >= score_minimo]

# --- LAYOUT PRINCIPAL ---
col1, col2 = st.columns([1.5, 1])

with col1:
    st.subheader(f"📍 Mapa de Localização: {condo_foco}")

    m = folium.Map(location=ponto_galpao, zoom_start=13)

    # Raio de influência "Last Mile" regional — 100 km
    folium.Circle(
        ponto_galpao,
        radius=100_000,          # 100 km em metros
        color="#FF6B00",
        fill=True,
        fill_opacity=0.04,
        weight=1.5,
        tooltip="Raio de entrega regional (100 km)",
    ).add_to(m)

    # Raio de proximidade imediata — 200 m
    folium.Circle(
        ponto_galpao,
        radius=200,
        color="green",
        fill=True,
        fill_opacity=0.2,
    ).add_to(m)

    # Marcadores — apenas galpões que passam no filtro de score
    for _, row in df_filtrado.iterrows():
        is_foco = row["EMPREENDIMENTO"] == condo_foco
        folium.Marker(
            [row["lat"], row["lon"]],
            popup=f"{row['EMPREENDIMENTO']} | Score: {row['_score']}",
            tooltip=row["EMPREENDIMENTO"],
            icon=folium.Icon(color="blue" if is_foco else "gray"),
        ).add_to(m)

    # Referências logísticas no mapa
    for nome, coord in REFS.items():
        if nome.startswith("ACESSOS"):
            for i, pt in enumerate(coord):
                folium.CircleMarker(
                    pt,
                    radius=5,
                    color="red",
                    fill=True,
                    fill_opacity=0.7,
                    tooltip=f"{nome} — Ponto {i + 1}",
                ).add_to(m)
        else:
            folium.Marker(
                coord,
                tooltip=nome,
                icon=folium.Icon(color="red", icon="info-sign"),
            ).add_to(m)

    st_folium(m, width=700, height=520)

    if len(df_filtrado) < len(df):
        st.caption(
            f"🔍 Exibindo **{len(df_filtrado)}** de **{len(df)}** galpões "
            f"(score ≥ {score_minimo})"
        )

# --- PAINEL DE AUDITORIA ---
with col2:
    if btn_auditoria:
        st.subheader(f"📊 Auditoria: {condo_foco}")

        # Cálculos de distância
        dist_centro  = round(geodesic(ponto_galpao, REFS["Centro de Campina Grande"]).km, 1)
        dist_cpv     = round(geodesic(ponto_galpao, REFS["Aeroporto CPV"]).km, 1)
        dist_jpa     = calcular_dist_jpa(dados_foco["lat"], dados_foco["lon"])
        dist_suape   = round(geodesic(ponto_galpao, REFS["Porto de Suape"]).km, 1)

        dists_br230  = [geodesic(ponto_galpao, a).km for a in REFS["ACESSOS_BR230"]]
        dist_br230   = round(min(dists_br230), 1)

        dists_br104  = [geodesic(ponto_galpao, a).km for a in REFS["ACESSOS_BR104"]]
        dist_br104   = round(min(dists_br104), 1)

        # Score
        valor_score = calcular_score_logistico(dados_foco, dist_br230, dist_br104)
        st.metric("🏆 LogiCG Score", f"{valor_score} / 10")

        st.markdown("**📐 Distâncias Logísticas**")

        # Linha 1 — Centro e Aeroporto local
        r1c1, r1c2 = st.columns(2)
        r1c1.metric("🏙️ Centro CG",       f"{dist_centro} km")
        r1c2.metric("✈️ Aeroporto CPV",    f"{dist_cpv} km")

        # Linha 2 — Rodovias (acesso mais próximo de cada BR)
        r2c1, r2c2 = st.columns(2)
        r2c1.metric("🛣️ Acesso BR-230",    f"{dist_br230} km")
        r2c2.metric("🛣️ Acesso BR-104",    f"{dist_br104} km")

        # Linha 3 — Infraestrutura regional
        r3c1, r3c2 = st.columns(2)
        r3c1.metric("✈️ Aeroporto JPA",    f"{dist_jpa} km")
        r3c2.metric("⚓ Porto de Suape",   f"{dist_suape} km")

        st.markdown("---")

        # --- Diagnóstico: Logística Social ---
        n_paradas = 4 if dist_centro < 4 else 1
        if n_paradas >= 3:
            st.success(
                f"🚌 **LOGÍSTICA SOCIAL:** {n_paradas} paradas em raio de 200 m. "
                "Baixo risco de turnover."
            )
        else:
            st.warning(
                f"🚐 **LOGÍSTICA SOCIAL:** Apenas {n_paradas} parada(s) próxima(s). "
                "Recomenda-se fretamento."
            )

        # --- Diagnóstico: Restrição Urbana ---
        if dist_centro < 3.8:
            st.error(
                "⚠️ **RESTRIÇÃO URBANA:** Localizado na Zona Central. "
                "Acesso proibido para Bi-trens."
            )
        else:
            st.success(
                "✅ **ACESSO PESADO:** Fora do perímetro de restrição. "
                "Rota livre para carretas."
            )

        # --- Diagnóstico: Conectividade Aérea ---
        if dist_jpa <= 120:
            st.info(
                f"🛫 **CONECTIVIDADE AÉREA:** A {dist_jpa} km do Aeroporto Internacional "
                "de João Pessoa (JPA). Viável para cargas aéreas prioritárias."
            )
        else:
            st.warning(
                f"🛬 **CONECTIVIDADE AÉREA:** JPA a {dist_jpa} km. "
                "Distância elevada — avaliar modal aéreo com cautela."
            )
    else:
        st.info("👈 Selecione um ativo na sidebar e clique em **RODAR AUDITORIA COMPLETA**.")
