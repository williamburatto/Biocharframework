"""
Aba "Mercados de carbono": compara o SBCE com mercados regulados de outros países.

O app.py chama render_mercados(...) dentro da aba. Os textos em português e inglês ficam aqui,
para que o gerador da versão em inglês (gerar_app_en.py) não precise de novos índices.
"""

from __future__ import annotations

import copy

import pandas as pd

from mercados import MERCADOS, comparar_mercados, tabela_mercados
from regioes import avaliar_municipios

ROTULO_MERCADOS = "Mercados de carbono"
ROTULO_MERCADOS_EN = "Carbon markets"

T = {
    "pt": {
        "titulo": "SBCE comparado com mercados regulados de outros países",
        "intro": ("Mesmo solo, mesma lavoura e mesmo biocarvão (barra lateral); muda só o preço e a regra do "
                  "mercado onde o crédito seria vendido. Os municípios usam os perfis reais do BDsolos. "
                  "Mercados marcados como *acesso hipotético* ainda não aceitam crédito de biocarvão para "
                  "cumprimento: o resultado mostra o que mudaria se aceitassem."),
        "regras": "**Regras e preços de cada mercado** (atualize os preços antes de publicar)",
        "estados": "Estados", "minp": "Mínimo de perfis por município", "limiar": "Limiar de viabilidade P(VPL>0)",
        "nsim": "Simulações por município",
        "nota_nsim": ("Muitos municípios ficam perto do limiar; use pelo menos 10.000 simulações para que a "
                      "contagem de viáveis não mude entre rodadas."),
        "rodar": "Comparar mercados",
        "res": "**Municípios viáveis por mercado**",
        "col": {"mercado": "Mercado", "preco": "Preço (US$/tCO₂e)", "viaveis": "Viáveis",
                "so_prod": "Viáveis só com produtividade", "p_med": "P(VPL>0) mediana", "acesso": "Acesso"},
        "hip": "hipotético", "real": "atual/prospectivo",
        "curva": "Curva: municípios viáveis em função do preço do carbono",
        "curva_cap": ("Cada ponto roda todos os municípios com um preço fixo. Compare com a faixa de preço de "
                      "cada mercado na tabela acima."),
        "eixo_x": "Preço do carbono (US$/tCO₂e)", "eixo_y": "Municípios viáveis",
        "top": "Municípios viáveis no mercado selecionado",
        "sel": "Mercado para listar os municípios",
        "tab": {"mercado": "Mercado", "tipo": "Tipo", "biocarvao": "Biocarvão aceito?", "limite": "Limite de uso",
                "preco_usd": "Preço (US$/t)", "fonte_preco": "Fonte do preço", "situacao": "Situação"},
        "sem_perfis": "Arquivo perfis_bdsolos_0_20.csv não encontrado.",
    },
    "en": {
        "titulo": "SBCE compared with compliance markets in other countries",
        "intro": ("Same soil, crop and biochar (sidebar); only the price and rules of the market where the credit "
                  "would be sold change. Municipalities use real BDsolos profiles. Markets marked *hypothetical "
                  "access* do not yet accept biochar credits for compliance: the result shows what would change "
                  "if they did."),
        "regras": "**Rules and prices of each market** (update prices before publishing)",
        "estados": "States", "minp": "Minimum profiles per municipality", "limiar": "Viability threshold P(NPV>0)",
        "nsim": "Simulations per municipality",
        "nota_nsim": ("Many municipalities lie close to the threshold; use at least 10,000 simulations so that the "
                      "number of viable municipalities does not change between runs."),
        "rodar": "Compare markets",
        "res": "**Viable municipalities by market**",
        "col": {"mercado": "Market", "preco": "Price (US$/tCO₂e)", "viaveis": "Viable",
                "so_prod": "Viable from yield alone", "p_med": "Median P(NPV>0)", "acesso": "Access"},
        "hip": "hypothetical", "real": "current/prospective",
        "curva": "Curve: viable municipalities as a function of the carbon price",
        "curva_cap": ("Each point runs all municipalities at a fixed price. Compare with each market's price range "
                      "in the table above."),
        "eixo_x": "Carbon price (US$/tCO₂e)", "eixo_y": "Viable municipalities",
        "top": "Viable municipalities in the selected market",
        "sel": "Market to list municipalities",
        "tab": {"mercado": "Market", "tipo": "Type", "biocarvao": "Biochar accepted?", "limite": "Use limit",
                "preco_usd": "Price (US$/t)", "fonte_preco": "Price source", "situacao": "Status"},
        "sem_perfis": "File perfis_bdsolos_0_20.csv not found.",
    },
}


def _curva(cenario, perfis, ufs, min_perfis, n, limiar, precos):
    c = copy.deepcopy(cenario)
    linhas = []
    for pr in precos:
        c.carbono.preco_min_usd_t = c.carbono.preco_max_usd_t = float(pr)
        r = avaliar_municipios(c, perfis, ufs=ufs, min_perfis=min_perfis, n_simulacoes=n)
        linhas.append({"preco": pr, "viaveis": int((r.prob_vpl_com_carbono >= limiar).sum())})
    return pd.DataFrame(linhas)


def render_mercados(st, cenario, perfis, lang: str = "pt"):
    t = T[lang]
    nome = "nome_en" if lang == "en" else "nome_pt"
    st.subheader(t["titulo"])
    st.markdown(t["intro"])
    st.markdown(t["regras"])
    st.dataframe(tabela_mercados(lang).rename(columns=t["tab"]), hide_index=True, width="stretch")
    if perfis is None:
        st.warning(t["sem_perfis"])
        return
    c1, c2, c3, c4 = st.columns(4)
    ufs = tuple(c1.multiselect(t["estados"], ["PR", "SC"], default=["PR", "SC"], key="mk_0"))
    minp = c2.slider(t["minp"], 1, 20, 3, key="mk_1")
    limiar = c3.slider(t["limiar"], 0.5, 0.95, 0.70, 0.05, key="mk_2")
    nsim = c4.select_slider(t["nsim"], [2000, 5000, 10000, 20000], 10000, key="mk_3")
    st.caption(t["nota_nsim"])

    @st.cache_data(show_spinner="...")
    def _comparar(_cen, cen_dict, ufs, minp, nsim, limiar):
        return comparar_mercados(_cen, perfis, ufs=ufs, min_perfis=minp, n_simulacoes=nsim, limiar=limiar)

    @st.cache_data(show_spinner="...")
    def _curva_c(_cen, cen_dict, ufs, minp, nsim, limiar):
        return _curva(_cen, perfis, ufs, minp, nsim, limiar, list(range(0, 251, 20)))

    resumo, rankings = _comparar(cenario, cenario.to_dict(), ufs, minp, nsim, limiar)
    col = t["col"]
    tab = pd.DataFrame({
        col["mercado"]: [MERCADOS[k][nome] for k in resumo.chave],
        col["preco"]: [f"{a:.0f}–{b:.0f}" for a, b in zip(resumo.preco_min, resumo.preco_max)],
        col["viaveis"]: resumo.viaveis,
        col["so_prod"]: resumo.viaveis_so_produtividade,
        col["p_med"]: resumo.p_mediana.round(2),
        col["acesso"]: [t["hip"] if h else t["real"] for h in resumo.hipotetico],
    })
    st.markdown(t["res"] + f" ({int(resumo.n_municipios.iloc[0])})")
    st.bar_chart(tab.set_index(col["mercado"])[[col["viaveis"]]], horizontal=True)
    st.dataframe(tab, hide_index=True, width="stretch")

    st.markdown(f"**{t['curva']}**")
    cv = _curva_c(cenario, cenario.to_dict(), ufs, minp, nsim, limiar)
    st.line_chart(cv.rename(columns={"preco": t["eixo_x"], "viaveis": t["eixo_y"]}).set_index(t["eixo_x"]))
    st.caption(t["curva_cap"])

    k_sel = st.selectbox(t["sel"], list(resumo.chave), format_func=lambda k: MERCADOS[k][nome], key="mk_4")
    r = rankings[k_sel]
    v = r[r.prob_vpl_com_carbono >= limiar].sort_values("prob_vpl_com_carbono", ascending=False)
    st.markdown(f"**{t['top']}**: {len(v)}")
    cols = ["uf", "municipio", "aumento_pct_ano1", "credito_tco2e_ha", "prob_vpl_sem_carbono", "prob_vpl_com_carbono"]
    st.dataframe(v[cols].round(3), hide_index=True, width="stretch")


def render_mercados_en(st, cenario, perfis, lang: str = "en"):
    render_mercados(st, cenario, perfis, "en")
