"""
Avaliação regional: em quais municípios (ex.: PR e SC) o biocarvão tende a dar
maior aumento de produtividade e maior incorporação de carbono no solo.

Para cada município com perfis no BDsolos, roda o simulador só com os perfis
daquele município e resume as duas vantagens:
  - produtividade: resposta média esperada e valor presente do ganho (R$/ha);
  - carbono: incremento relativo do estoque de C 0–20 cm (C do biocarvão / estoque
    nativo) e remoção creditável (tCO2e/ha);
  - viabilidade: P(VPL>0) sem e com carbono e a classe de viabilidade dominante.

Limitações: perfis antigos e pouco numerosos em muitos municípios; o resultado
indica onde priorizar amostragem e ensaios, não substitui laudos atuais.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from simulador import Cenario, simular


def veredito(p_sem: float, p_com: float, limiar: float) -> str:
    if p_sem >= limiar:
        return "Viável só com o aumento de produtividade"
    if p_com >= limiar:
        return "Viável somando produtividade e carbono"
    return "Não viável nas condições atuais"


def _metricas(c: Cenario, g: pd.DataFrame, out: dict) -> dict:
    """Indicadores de um município em unidades diretas (t/ha, R$/ha, t C/ha)."""
    from simulador import incremento_c_solo_tha, elegivel
    r, df = out["resumo"], out["simulacoes"]
    cu, s = c.cultura, c.simulacao
    T = s.horizonte_anos
    decai = (1 - c.resposta.decaimento_anual) ** np.arange(T)
    resp = r["resposta_media_usada"]
    aumento_ano1 = cu.produtividade_base_t_ha * resp
    aumento_medio = aumento_ano1 * decai.mean()
    estoque = float(g["estoque_c_0_20_tha"].median())
    c_retido = incremento_c_solo_tha(c)
    return {
        "aumento_pct_ano1": 100 * resp,
        "aumento_t_ha_ano1": aumento_ano1,
        "aumento_t_ha_medio": aumento_medio,
        "aumento_total_t_ha": aumento_ano1 * decai.sum(),
        "ganho_r_ha_ano_medio": aumento_medio * cu.preco_cultura_r_t,
        "vp_produtividade_r_ha": float(df["vp_produtividade"].median()) / cu.area_ha,
        "estoque_c_nativo_tha": estoque,
        "c_retido_tc_ha": c_retido,
        "c_retido_tco2e_ha": c_retido * 44 / 12,
        "incremento_c_pct": 100 * c_retido / estoque if estoque and estoque > 0 else np.nan,
        "gera_credito": bool(elegivel(c.biocarvao, c.carbono)),
        "credito_tco2e_ha": r["remocao_tco2e_por_ha"],
        "prob_vpl_sem_carbono": r["prob_vpl_pos_sem_carbono"],
        "prob_vpl_com_carbono": r["prob_vpl_pos_com_carbono"],
        "prob_inadimplencia": r["prob_inadimplencia"],
        "veredito": veredito(r["prob_vpl_pos_sem_carbono"], r["prob_vpl_pos_com_carbono"], s.limiar_prob_vpl),
    }


def detalhar_municipio(cenario: Cenario, perfis: pd.DataFrame, uf: str, municipio: str,
                       n_simulacoes: int = 10_000) -> dict:
    """Avaliação completa de um município: produtividade, carbono, viabilidade e solo."""
    c = copy.deepcopy(cenario)
    c.simulacao.n_simulacoes = n_simulacoes
    c.resposta.media = None
    g = perfis[(perfis["uf"] == uf) & (perfis["municipio"] == municipio)]
    if g.empty:
        raise ValueError(f"Sem perfis de solo para {municipio} ({uf}).")
    estado = perfis[perfis["uf"] == uf]
    out = simular(c, g)
    m = _metricas(c, g, out)
    r = out["resumo"]
    T = c.simulacao.horizonte_anos
    decai = (1 - c.resposta.decaimento_anual) ** np.arange(T)
    anual = pd.DataFrame({
        "Ano": np.arange(1, T + 1),
        "Aumento de produtividade (t/ha)": c.cultura.produtividade_base_t_ha * r["resposta_media_usada"] * decai,
    })
    anual["Ganho (R$/ha)"] = anual["Aumento de produtividade (t/ha)"] * c.cultura.preco_cultura_r_t
    solo = pd.DataFrame({
        "Atributo (0–20 cm)": ["pH em água", "V% (saturação por bases)", "Argila (%)", "C orgânico (g/kg)",
                               "Estoque de C (t/ha)"],
        "Município (mediana)": [g["ph"].median(), g["v_pct"].median(), g["argila_pct"].median(),
                                g["c_org_gkg"].median(), g["estoque_c_0_20_tha"].median()],
        f"{uf} (mediana)": [estado["ph"].median(), estado["v_pct"].median(), estado["argila_pct"].median(),
                            estado["c_org_gkg"].median(), estado["estoque_c_0_20_tha"].median()],
    })
    m.update({
        "uf": uf, "municipio": municipio, "n_perfis": len(g),
        "classes_solo": g["classe_n1"].value_counts().head(3).to_dict(),
        "anual": anual, "solo": solo, "resumo": r, "resultado": out,
        "resposta_necessaria_sem_carbono": r["resposta_equilibrio_sem_carbono_mediana"],
        "preco_carbono_equilibrio_usd": r["preco_carbono_equilibrio_usd_mediano"],
        "custo_inicial_r_ha": r["custo_inicial_r"] / c.cultura.area_ha,
    })
    return m


def avaliar_municipios(cenario: Cenario, perfis: pd.DataFrame, ufs=("PR", "SC"),
                       min_perfis: int = 3, n_simulacoes: int = 10_000) -> pd.DataFrame:
    c = copy.deepcopy(cenario)
    c.simulacao.n_simulacoes = n_simulacoes
    c.resposta.media = None                      # a resposta vem dos perfis de cada município
    area = c.cultura.area_ha
    c_bc_tha = c.biocarvao.dose_t_ha * c.biocarvao.c_org_frac

    base = perfis[perfis["uf"].isin(ufs)]
    linhas = []
    for (uf, mun), g in base.groupby(["uf", "municipio"]):
        if len(g) < min_perfis:
            continue
        out = simular(c, g)
        r = out["resumo"]
        geo = g.dropna(subset=["lat", "lon"])
        classes = r["classes_viabilidade"]
        linha = {
            "uf": uf,
            "municipio": mun,
            "n_perfis": len(g),
            "lat": float(geo["lat"].mean()) if len(geo) else np.nan,
            "lon": float(geo["lon"].mean()) if len(geo) else np.nan,
            "classe_solo_predominante": g["classe_n1"].mode().iat[0] if g["classe_n1"].notna().any() else "",
            "ph_mediano": float(g["ph"].median()),
            "v_mediano": float(g["v_pct"].median()),
            "argila_mediana_pct": float(g["argila_pct"].median()),
            "c_org_mediano_gkg": float(g["c_org_gkg"].median()),
            "resposta_media_pct": 100 * r["resposta_media_usada"],
            "remocao_tco2e_ha": r["remocao_tco2e_por_ha"],
            "pct_produtividade_paga": classes.get("Só a produtividade paga", 0.0) + classes.get("Cada vantagem sozinha paga", 0.0),
            "pct_carbono_paga": classes.get("Só o carbono paga", 0.0) + classes.get("Cada vantagem sozinha paga", 0.0),
            "pct_so_juntas": classes.get("Só as duas juntas pagam", 0.0),
            "pct_inviavel": classes.get("Inviável", 0.0),
        }
        linha.update(_metricas(c, g, out))
        linhas.append(linha)
    res = pd.DataFrame(linhas)
    if res.empty:
        return res

    # índices 0–1 (posição percentual dentro do conjunto avaliado) e índice combinado
    res["indice_produtividade"] = res["vp_produtividade_r_ha"].rank(pct=True)
    res["indice_carbono"] = res["incremento_c_pct"].rank(pct=True)
    res["indice_combinado"] = (res["indice_produtividade"] + res["indice_carbono"]) / 2
    return res.sort_values("indice_combinado", ascending=False).reset_index(drop=True)


def cor_por_valor(valores: pd.Series, vmin: float = 0.0, vmax: float = 1.0) -> list[str]:
    """Escala vermelho → amarelo → verde em hex RGBA para st.map."""
    x = ((valores.astype(float) - vmin) / (vmax - vmin)).clip(0, 1).fillna(0)
    cores = []
    for t in x:
        if t < 0.5:
            rr, gg = 215, int(48 + (190 - 48) * t / 0.5)
        else:
            rr, gg = int(215 - (215 - 26) * (t - 0.5) / 0.5), int(190 - (190 - 150) * (t - 0.5) / 0.5)
        cores.append(f"#{rr:02x}{gg:02x}40cc")
    return cores
