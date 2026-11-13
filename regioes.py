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


def avaliar_municipios(cenario: Cenario, perfis: pd.DataFrame, ufs=("PR", "SC"),
                       min_perfis: int = 3, n_simulacoes: int = 2000) -> pd.DataFrame:
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
        r, df = out["resumo"], out["simulacoes"]
        estoque = float(g["estoque_c_0_20_tha"].median())
        geo = g.dropna(subset=["lat", "lon"])
        classes = r["classes_viabilidade"]
        linhas.append({
            "uf": uf,
            "municipio": mun,
            "n_perfis": len(g),
            "lat": float(geo["lat"].mean()) if len(geo) else np.nan,
            "lon": float(geo["lon"].mean()) if len(geo) else np.nan,
            "classe_solo_predominante": g["classe_n1"].mode().iat[0] if g["classe_n1"].notna().any() else "",
            "ph_mediano": float(g["ph"].median()),
            "v_mediano": float(g["v_pct"].median()),
            "resposta_media_pct": 100 * r["resposta_media_usada"],
            "vp_produtividade_r_ha": float(df["vp_produtividade"].median()) / area,
            "estoque_c_nativo_tha": estoque,
            "incremento_c_pct": 100 * c_bc_tha / estoque if estoque and estoque > 0 else np.nan,
            "remocao_tco2e_ha": r["remocao_tco2e_por_ha"],
            "prob_vpl_sem_carbono": r["prob_vpl_pos_sem_carbono"],
            "prob_vpl_com_carbono": r["prob_vpl_pos_com_carbono"],
            "prob_inadimplencia": r["prob_inadimplencia"],
            "argila_mediana_pct": float(g["argila_pct"].median()),
            "c_org_mediano_gkg": float(g["c_org_gkg"].median()),
            "pct_produtividade_paga": classes.get("Só a produtividade paga", 0.0) + classes.get("Cada vantagem sozinha paga", 0.0),
            "pct_carbono_paga": classes.get("Só o carbono paga", 0.0) + classes.get("Cada vantagem sozinha paga", 0.0),
            "pct_so_juntas": classes.get("Só as duas juntas pagam", 0.0),
            "pct_inviavel": classes.get("Inviável", 0.0),
        })
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
