"""
Aba "Brasil — áreas degradadas": roda o modelo em todos os municípios do BDsolos com perfis suficientes,
para soja, milho ou feijão, e mostra mapa, ranking e resumo por região prioritária para recuperação.

O app.py chama render_brasil(...) dentro da aba. Textos em português e inglês ficam aqui, como em
aba_mercados.py, para não mudar os índices do gerador da versão em inglês.
"""

from __future__ import annotations

import copy

import pandas as pd

from regioes import avaliar_municipios
from simulador import CULTURAS
from assistente import BIOCARVOES, TXT, carregar_precalculado

ROTULO_BRASIL = "Brasil — áreas degradadas"
ROTULO_BRASIL_EN = "Brazil — degraded land"

REGIOES = {
    "Cerrado central (GO, MT, MS, DF)": ("GO", "MT", "MS", "DF"),
    "MATOPIBA (MA, TO, PI, BA)": ("MA", "TO", "PI", "BA"),
    "Minas Gerais": ("MG",),
    "Amazônia já aberta (PA, RO)": ("PA", "RO"),
    "Litoral e semiárido do Nordeste (CE, PE, PB, RN)": ("CE", "PE", "PB", "RN"),
    "Sul e Sudeste (PR, RS, SP)": ("PR", "RS", "SP"),
}
REGIOES_EN = {
    "Cerrado central (GO, MT, MS, DF)": "Central Cerrado (GO, MT, MS, DF)",
    "MATOPIBA (MA, TO, PI, BA)": "MATOPIBA (MA, TO, PI, BA)",
    "Minas Gerais": "Minas Gerais",
    "Amazônia já aberta (PA, RO)": "Already-cleared Amazon (PA, RO)",
    "Litoral e semiárido do Nordeste (CE, PE, PB, RN)": "Northeast coast and semi-arid (CE, PE, PB, RN)",
    "Sul e Sudeste (PR, RS, SP)": "South and South-east (PR, RS, SP)",
}
CULT_EN = {"soja": "soybean", "milho": "maize", "feijão": "common bean"}

T = {
    "pt": {
        "titulo": "Onde o biocarvão viabiliza lavouras em áreas degradadas do Brasil",
        "intro": ("Roda o modelo em todos os municípios do BDsolos com perfis suficientes, com o solo, o biocarvão, a "
                  "adubação, o crédito e o preço de carbono escolhidos na barra lateral. Para recuperação de pastagens "
                  "degradadas, use na barra lateral **sem adubação**, um biocarvão rico em nutrientes e a correção "
                  "com calcário."),
        "contexto": ("O Brasil tem cerca de 165 milhões de hectares de pastagens, dos quais 82 milhões apresentam algum "
                     "grau de degradação; o programa Caminho Verde Brasil quer recuperar até 40 milhões de hectares em "
                     "dez anos, com crédito rural a juros menores."),
        "cultura": "Cultura", "regiao": "Região", "todas": "Todas as regiões", "minp": "Mínimo de perfis por município",
        "limiar": "Limiar de viabilidade P(VPL>0)", "nsim": "Simulações por município",
        "m_munis": "Municípios avaliados", "m_viaveis": "Viáveis", "m_prod": "Viáveis só com produtividade",
        "m_aum": "Aumento mediano no ano 1",
        "mapa": "**Mapa** (verde: viável; laranja: perto do limiar; cinza: não viável)",
        "resumo": "**Resumo por região prioritária**",
        "rank": "**Ranking de municípios**",
        "col": {"regiao": "Região", "munis": "Municípios", "viaveis": "Viáveis", "so_prod": "Só produtividade",
                "ph": "pH mediano", "aum": "Aumento ano 1 (%)"},
        "cols_rank": {"uf": "UF", "municipio": "Município", "n_perfis": "Perfis", "ph_mediano": "pH",
                      "aumento_pct_ano1": "Aumento ano 1 (%)", "credito_tco2e_ha": "Crédito (tCO₂e/ha)",
                      "prob_vpl_sem_carbono": "P(VPL>0) sem carbono", "prob_vpl_com_carbono": "P(VPL>0) com carbono"},
        "cuidados": ("**Cuidados.** O modelo usa a produtividade padrão de cada cultura e não representa a falta de "
                     "água no semiárido; os perfis do BDsolos descrevem o solo do município, não necessariamente a área "
                     "degradada; na Amazônia, vale só para áreas já abertas (o Caminho Verde não admite desmatamento). "
                     "Em solos neutros ou alcalinos do semiárido cristalino (ex.: Cabrobó, Seridó) o biocarvão quase "
                     "não aumenta a produtividade: ali o limite é a água."),
        "sem_perfis": "Arquivo perfis_bdsolos_0_20.csv não encontrado.",
        "instant": "Resposta instantânea (cenário pré-calculado; desligue para usar a barra lateral)", "adub": "Adubação", "bio": "Biocarvão",
    },
    "en": {
        "titulo": "Where biochar makes crops viable on degraded land in Brazil",
        "intro": ("Runs the model in every BDsolos municipality with enough profiles, using the soil, biochar, "
                  "fertilisation, credit and carbon price chosen in the sidebar. For degraded-pasture recovery, choose "
                  "**no fertilisation**, a nutrient-rich biochar and liming correction in the sidebar."),
        "contexto": ("Brazil has about 165 million hectares of pasture, of which 82 million show some degree of "
                     "degradation; the Caminho Verde Brasil programme aims to recover up to 40 million hectares in ten "
                     "years with lower-interest rural credit."),
        "cultura": "Crop", "regiao": "Region", "todas": "All regions", "minp": "Minimum profiles per municipality",
        "limiar": "Viability threshold P(NPV>0)", "nsim": "Simulations per municipality",
        "m_munis": "Municipalities assessed", "m_viaveis": "Viable", "m_prod": "Viable from yield alone",
        "m_aum": "Median year-1 increase",
        "mapa": "**Map** (green: viable; orange: near the threshold; grey: not viable)",
        "resumo": "**Summary by priority region**",
        "rank": "**Municipality ranking**",
        "col": {"regiao": "Region", "munis": "Municipalities", "viaveis": "Viable", "so_prod": "Yield alone",
                "ph": "Median pH", "aum": "Year-1 increase (%)"},
        "cols_rank": {"uf": "State", "municipio": "Municipality", "n_perfis": "Profiles", "ph_mediano": "pH",
                      "aumento_pct_ano1": "Year-1 increase (%)", "credito_tco2e_ha": "Credit (tCO₂e/ha)",
                      "prob_vpl_sem_carbono": "P(NPV>0) without carbon", "prob_vpl_com_carbono": "P(NPV>0) with carbon"},
        "cuidados": ("**Caveats.** The model uses each crop's default yield and does not represent water deficit in the "
                     "semi-arid region; BDsolos profiles describe the municipality's soil, not necessarily the degraded "
                     "area; in the Amazon it applies only to already-cleared land (Caminho Verde does not allow "
                     "deforestation). In neutral or alkaline crystalline soils of the semi-arid region (e.g. Cabrobó, "
                     "Seridó) biochar barely raises yield: water is the limit there."),
        "sem_perfis": "File perfis_bdsolos_0_20.csv not found.",
        "instant": "Instant answer (pre-computed scenario; switch off to use the sidebar)", "adub": "Fertilisation", "bio": "Biochar",
    },
}


def cenario_cultura(cenario, cultura: str):
    c = copy.deepcopy(cenario)
    k = CULTURAS[cultura]
    c.cultura.cultura = cultura
    c.cultura.produtividade_base_t_ha = k["produtividade_t_ha"]
    c.cultura.preco_cultura_r_t = k["preco_r_t"]
    c.cultura.preco_cultura_cv = k["cv_preco"]
    c.cultura.margem_base_r_ha = k["margem_r_ha"]
    c.cultura.fator_resposta_cultura = k["fator_resposta"]
    return c


def regiao_de(uf: str) -> str | None:
    for nome, ufs in REGIOES.items():
        if uf in ufs:
            return nome
    return None


def resumo_regioes(r: pd.DataFrame, limiar: float = 0.70) -> pd.DataFrame:
    linhas = []
    for nome, ufs in REGIOES.items():
        d = r[r.uf.isin(ufs)]
        if not len(d):
            continue
        linhas.append({"regiao": nome, "munis": len(d), "viaveis": int((d.prob_vpl_com_carbono >= limiar).sum()),
                       "so_prod": int((d.prob_vpl_sem_carbono >= limiar).sum()),
                       "ph": round(float(d.ph_mediano.median()), 1),
                       "aum": round(float(d.aumento_pct_ano1.median()), 1)})
    return pd.DataFrame(linhas)


def render_brasil(st, cenario, perfis, lang: str = "pt"):
    t = T[lang]
    st.subheader(t["titulo"])
    st.markdown(t["intro"])
    st.caption(t["contexto"])
    if perfis is None:
        st.warning(t["sem_perfis"])
        return
    c1, c2, c3, c4 = st.columns(4)
    cultura = c1.selectbox(t["cultura"], ["soja", "milho", "feijão"],
                           format_func=(lambda x: CULT_EN[x]) if lang == "en" else (lambda x: x))
    opcoes = [t["todas"]] + list(REGIOES)
    regiao = c2.selectbox(t["regiao"], opcoes,
                          format_func=(lambda x: REGIOES_EN.get(x, x)) if lang == "en" else (lambda x: x))
    minp = c3.slider(t["minp"], 1, 20, 3)
    limiar = c4.slider(t["limiar"], 0.5, 0.95, 0.70, 0.05)
    ufs = tuple(sorted(perfis.uf.dropna().unique()))

    @st.cache_data(show_spinner=False)
    def _pre():
        return carregar_precalculado()

    pre = _pre()
    instant = pre is not None and st.checkbox(t["instant"], value=True)
    if instant:
        tx = TXT[lang]
        k1, k2 = st.columns(2)
        adub = k1.radio(t["adub"], ["sem_adubacao", "completa"], format_func=lambda k: tx[k], horizontal=True)
        bio = k2.radio(t["bio"], list(BIOCARVOES), format_func=lambda k: tx[k], horizontal=True)
        r = pre[(pre.cultura == cultura) & (pre.adubacao == adub) & (pre.biocarvao == bio) & (pre.n_perfis >= minp)].copy()
    else:
        nsim = st.select_slider(t["nsim"], [2000, 5000, 10000, 20000], 10000)

        @st.cache_data(show_spinner="...")
        def _avaliar(_cen, cen_dict, cultura, ufs, minp, nsim):
            return avaliar_municipios(cenario_cultura(_cen, cultura), perfis, ufs=ufs, min_perfis=minp, n_simulacoes=nsim)

        r = _avaliar(cenario, cenario.to_dict(), cultura, ufs, minp, nsim)
    if regiao != t["todas"]:
        r = r[r.uf.isin(REGIOES[regiao])]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t["m_munis"], len(r))
    m2.metric(t["m_viaveis"], int((r.prob_vpl_com_carbono >= limiar).sum()))
    m3.metric(t["m_prod"], int((r.prob_vpl_sem_carbono >= limiar).sum()))
    m4.metric(t["m_aum"], f"{r.aumento_pct_ano1.median():.1f}%" if len(r) else "—")

    st.markdown(t["mapa"])
    mapa = r.dropna(subset=["lat", "lon"]).copy()
    p = mapa.prob_vpl_com_carbono
    mapa["cor"] = ["#2f855a" if v >= limiar else ("#d97706" if v >= limiar - 0.15 else "#9ca3af") for v in p]
    mapa["tam"] = 4000 + 16000 * p
    st.map(mapa, latitude="lat", longitude="lon", color="cor", size="tam")

    if regiao == t["todas"]:
        st.markdown(t["resumo"])
        res = resumo_regioes(r, limiar)
        if lang == "en":
            res["regiao"] = res["regiao"].map(REGIOES_EN)
        st.dataframe(res.rename(columns=t["col"]), hide_index=True, use_container_width=True)

    st.markdown(t["rank"])
    cols = list(t["cols_rank"])
    st.dataframe(r.sort_values("prob_vpl_com_carbono", ascending=False)[cols].round(2).rename(columns=t["cols_rank"]),
                 hide_index=True, use_container_width=True)
    st.markdown(t["cuidados"])


def render_brasil_en(st, cenario, perfis, lang: str = "en"):
    render_brasil(st, cenario, perfis, "en")
