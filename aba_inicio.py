"""
Aba "Início rápido": assistente em 3 passos com resultado em semáforo, explicação, "o que mudaria",
entrada da análise de solo do talhão, nível de confiança, resposta instantânea (pré-calculada) e
relatório em PDF. Textos em PT e EN ficam aqui para não alterar os índices do gerador do app em inglês.
"""

from __future__ import annotations

import pandas as pd

from assistente import (ADUBACOES, BIOCARVOES, CULTURAS_ASSIST, TXT, _n, avaliar, carregar_precalculado,
                        consulta_rapida, gerar_pdf, montar_cenario, perfil_talhao, semaforo)

ROTULO_INICIO = "Início rápido"
ROTULO_INICIO_EN = "Quick start"

CULT_EN = {"soja": "soybean", "milho": "maize", "feijão": "common bean", "milho safrinha": "second-crop maize",
           "trigo": "wheat"}

T = {
    "pt": {
        "titulo": "Vale a pena usar biocarvão na sua área?",
        "intro": "Responda três perguntas. O app escolhe o restante com valores da literatura e do artigo; "
                 "para ajustar tudo, use o **modo avançado** (barra lateral e demais abas).",
        "modo": "Modo", "simples": "Simples (assistente)", "avancado": "Avançado (usar a barra lateral)",
        "p1": "1. Onde fica sua área?", "estado": "Estado", "municipio": "Município",
        "talhao": "Tenho a análise de solo do meu talhão (0–20 cm)",
        "ph": "pH em água", "v": "V% (saturação por bases)", "argila": "Argila (%)",
        "c": "Carbono orgânico (g/kg)", "mo_dica": "Se o laudo traz matéria orgânica (MO), use C = MO ÷ 1,724.",
        "p2": "2. O que você planta?", "cultura": "Cultura",
        "p3": "3. Como você aduba hoje e qual biocarvão usaria?", "adubacao": "Adubação", "biocarvao": "Biocarvão",
        "rapido": "Resposta instantânea (cenário pré-calculado). Refinando com mais simulações…",
        "pronto": "Resultado refinado",
        "m_aum": "Aumento de produtividade (1º ano)", "m_cred": "Crédito de carbono", "m_custo": "Custo inicial",
        "m_ret": "Retorno líquido em 8 anos", "sem_credito": "não gera",
        "pq": "**Por que deu esse resultado**", "mud": "**O que mudaria o resultado**", "conf": "**Confiança**",
        "pdf": "Baixar relatório em PDF", "anual": "Aumento de produtividade por ano (t/ha)",
        "avancado_txt": "Modo avançado: o resultado abaixo usa todos os parâmetros da barra lateral.",
        "sem_perfis": "Arquivo perfis_bdsolos_0_20.csv não encontrado.",
        "sem_mun": "Sem perfis de solo neste município. Informe a análise do seu talhão.",
        "ano": "Ano",
    },
    "en": {
        "titulo": "Is biochar worth it on your land?",
        "intro": "Answer three questions. The app fills in the rest with values from the literature and the paper; "
                 "to adjust everything, use the **advanced mode** (sidebar and other tabs).",
        "modo": "Mode", "simples": "Simple (assistant)", "avancado": "Advanced (use the sidebar)",
        "p1": "1. Where is your land?", "estado": "State", "municipio": "Municipality",
        "talhao": "I have my field's soil analysis (0–20 cm)",
        "ph": "pH in water", "v": "Base saturation V (%)", "argila": "Clay (%)",
        "c": "Organic carbon (g/kg)", "mo_dica": "If the report gives organic matter (OM), use C = OM ÷ 1.724.",
        "p2": "2. What do you grow?", "cultura": "Crop",
        "p3": "3. How do you fertilise today and which biochar would you use?", "adubacao": "Fertilisation",
        "biocarvao": "Biochar",
        "rapido": "Instant answer (pre-computed scenario). Refining with more simulations…",
        "pronto": "Refined result",
        "m_aum": "Yield increase (year 1)", "m_cred": "Carbon credit", "m_custo": "Upfront cost",
        "m_ret": "Net return over 8 years", "sem_credito": "none",
        "pq": "**Why this result**", "mud": "**What would change the result**", "conf": "**Confidence**",
        "pdf": "Download PDF report", "anual": "Yield increase by year (t/ha)",
        "avancado_txt": "Advanced mode: the result below uses every sidebar parameter.",
        "sem_perfis": "File perfis_bdsolos_0_20.csv not found.",
        "sem_mun": "No soil profiles for this municipality. Enter your field's soil analysis.",
        "ano": "Year",
    },
}


def _caixa(st, sem: str, texto: str):
    {"verde": st.success, "amarelo": st.warning, "vermelho": st.error}[sem](texto)


def render_inicio(st, cenario_avancado, perfis, lang: str = "pt"):
    t, tx = T[lang], TXT[lang]
    N = lambda x, dec=0: _n(x, dec, lang)  # noqa: E731
    st.subheader(t["titulo"])
    st.markdown(t["intro"])
    if perfis is None:
        st.warning(t["sem_perfis"])
        return
    modo = st.radio(t["modo"], [t["simples"], t["avancado"]], horizontal=True)

    st.markdown(f"**{t['p1']}**")
    c1, c2 = st.columns(2)
    ufs = sorted(perfis.uf.dropna().unique())
    uf = c1.selectbox(t["estado"], ufs, index=ufs.index("PR") if "PR" in ufs else 0)
    muns = sorted(perfis[perfis.uf == uf].municipio.dropna().unique())
    municipio = c2.selectbox(t["municipio"], muns)
    talhao = None
    if st.checkbox(t["talhao"]):
        a1, a2, a3, a4 = st.columns(4)
        ph = a1.number_input(t["ph"], 3.0, 9.0, 5.0, 0.1)
        v = a2.number_input(t["v"], 0.0, 100.0, 40.0, 1.0)
        arg = a3.number_input(t["argila"], 0.0, 90.0, 25.0, 1.0)
        corg = a4.number_input(t["c"], 0.0, 200.0, 15.0, 0.5)
        st.caption(t["mo_dica"])
        talhao = perfil_talhao(ph, v, arg, corg)

    if modo == t["simples"]:
        st.markdown(f"**{t['p2']}**")
        cultura = st.selectbox(t["cultura"], CULTURAS_ASSIST,
                               format_func=(lambda x: CULT_EN.get(x, x)) if lang == "en" else (lambda x: x))
        st.markdown(f"**{t['p3']}**")
        b1, b2 = st.columns(2)
        adub = b1.radio(t["adubacao"], ADUBACOES, format_func=lambda k: tx[k], index=1)
        bio = b2.radio(t["biocarvao"], list(BIOCARVOES), format_func=lambda k: tx[k])
        cen = montar_cenario(cultura, adub, bio, n_simulacoes=10000)
        rapido = None if talhao is not None else consulta_rapida(_pre(st), uf, municipio, cultura, adub, bio)
    else:
        st.info(t["avancado_txt"])
        cen = cenario_avancado
        rapido = None

    ph_slot = st.empty()
    if rapido is not None:
        with ph_slot.container():
            _caixa(st, semaforo(rapido["prob_vpl_com_carbono"]),
                   f"{tx[semaforo(rapido['prob_vpl_com_carbono']) + '_sem']} — "
                   + tx["frase_prob"].format(p=N(100 * rapido["prob_vpl_com_carbono"])))
            st.caption(t["rapido"])

    try:
        res = _avaliar(st, cen, perfis, uf, municipio, talhao, lang)
    except ValueError:
        ph_slot.empty()
        st.warning(t["sem_mun"])
        return
    ph_slot.empty()

    _caixa(st, res["semaforo"], f"**{res['rotulo']}** — {res['frase_prob']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t["m_aum"], f"+{N(res['aumento_pct'], 1)}%", f"+{N(res['aumento_t_ha'], 2)} t/ha", delta_color="off")
    m2.metric(t["m_cred"], f"{N(res['credito_tco2e_ha'], 1)} tCO₂e/ha" if res["gera_credito"] else t["sem_credito"])
    m3.metric(t["m_custo"], f"R$ {N(res['custo_r_ha'])}/ha")
    m4.metric(t["m_ret"], f"R$ {N(res['retorno_liquido_r_ha'])}/ha")

    e1, e2 = st.columns(2)
    with e1:
        st.markdown(t["pq"])
        st.markdown("\n".join(f"- {x}" for x in res["explicacao"]))
    with e2:
        st.markdown(t["mud"])
        st.markdown("\n".join(f"- {x}" for x in res["mudaria"]))
    st.markdown(t["conf"])
    st.caption(res["confianca_txt"])

    an = res["anual"].iloc[:, :2].copy()
    an.columns = [t["ano"], t["anual"]]
    st.bar_chart(an.set_index(t["ano"]))
    st.download_button(t["pdf"], data=gerar_pdf(res, lang),
                       file_name=f"biocredito_{res['municipio']}_{res['cultura']}.pdf".replace(" ", "_"),
                       mime="application/pdf")


def _pre(st):
    @st.cache_data(show_spinner=False)
    def _ler():
        return carregar_precalculado()
    return _ler()


def _avaliar(st, cen, perfis, uf, municipio, talhao, lang):
    @st.cache_data(show_spinner="…")
    def _calc(_cen, cen_dict, uf, municipio, talhao_dict, lang):
        tal = pd.DataFrame([talhao_dict]) if talhao_dict else None
        return avaliar(_cen, perfis, uf, municipio, talhao=tal, lang=lang)
    tal_dict = talhao.iloc[0].to_dict() if talhao is not None else None
    return _calc(cen, cen.to_dict(), uf, municipio, tal_dict, lang)


def render_inicio_en(st, cenario_avancado, perfis, lang: str = "en"):
    render_inicio(st, cenario_avancado, perfis, "en")
