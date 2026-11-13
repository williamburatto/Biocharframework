"""
Validação do simulador com a literatura (produtividade e carbono no solo).

Fontes (todas citadas no app, aba "Validação"):
  [1] Chagas, J. K. M.; Nardoto, G. B.; Madari, B. E.; Figueiredo, C. C. (2024). Seven-year effects of
      sewage sludge biochar on soil organic carbon pools and yield. Soil Use and Management 40:e70001.
      https://doi.org/10.1111/sum.70001
  [2] Latawiec, A. E. et al. (2019). Biochar amendment improves degraded pasturelands in Brazil:
      environmental and cost-benefit analysis. Scientific Reports 9:11993.
      https://doi.org/10.1038/s41598-019-47647-x
  [3] Rani, R.; Garg, N. (2025). Role of biochar in modulating soil properties, plant productivity and
      abiotic stresses: a review. Journal of Soil Science and Plant Nutrition 25:3285–3305.
      https://doi.org/10.1007/s42729-025-02335-w
  [4] Al-Gaashani, R. et al. (2026). Productivity evaluation, multi-scale characterisation, and safety
      assessment of biochar derived from green and woody agricultural biomass in Qatar.
      Scientific Reports 16:23914. https://doi.org/10.1038/s41598-026-54140-9
  [5] Lin, G.; Wang, Y.; Wu, X.; Meng, J.; Ok, Y. S.; Wang, C.-H. (2025). Enhancing agricultural productivity
      with biochar: evaluating feedstock and quality standards. Bioresource Technology Reports 29:102059.
      https://doi.org/10.1016/j.biteb.2025.102059
  [0] Buratto, W. G. et al. Biochar framework for carbon capture and credit certification across
      regulatory standards. GCB Bioenergy (manuscrito).

Premissas: quando o artigo não informa pH, argila ou C do solo, o valor usado está marcado
como "assumido" na coluna de premissas. Os valores observados vêm do texto dos artigos.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from simulador import (Cenario, ParametrosBiocarvao, ParametrosSolo, resposta_media_vetor, fator_dose,
                       FATOR_ADUBACAO, fator_adubacao, fator_permanencia, checar_padrao, PADROES)

REFERENCIAS = {
    "GCB": "Buratto, W. G.; Muniz, R. N.; Villarubia González, G.; Barros, C. F. O.; Costa, V. J.; Nied, A. "
           "Biochar framework for carbon capture and credit certification across regulatory standards. "
           "GCB Bioenergy (manuscrito).",
    "Chagas2024": "Chagas, J. K. M.; Nardoto, G. B.; Madari, B. E.; Figueiredo, C. C. Seven-year effects of sewage "
                  "sludge biochar on soil organic carbon pools and yield. Soil Use and Management, 40, e70001, 2024. "
                  "https://doi.org/10.1111/sum.70001",
    "Latawiec2019": "Latawiec, A. E. et al. Biochar amendment improves degraded pasturelands in Brazil: environmental "
                    "and cost-benefit analysis. Scientific Reports, 9, 11993, 2019. "
                    "https://doi.org/10.1038/s41598-019-47647-x",
    "Rani2025": "Rani, R.; Garg, N. Role of biochar in modulating soil properties, plant productivity and abiotic "
                "stresses: a review. Journal of Soil Science and Plant Nutrition, 25, 3285–3305, 2025. "
                "https://doi.org/10.1007/s42729-025-02335-w",
    "AlGaashani2026": "Al-Gaashani, R. et al. Productivity evaluation, multi-scale characterisation, and safety "
                      "assessment of biochar derived from green and woody agricultural biomass in Qatar. "
                      "Scientific Reports, 16, 23914, 2026. https://doi.org/10.1038/s41598-026-54140-9",
    "Lin2025": "Lin, G.; Wang, Y.; Wu, X.; Meng, J.; Ok, Y. S.; Wang, C.-H. Enhancing agricultural productivity with "
               "biochar: evaluating feedstock and quality standards. Bioresource Technology Reports, 29, 102059, "
               "2025. https://doi.org/10.1016/j.biteb.2025.102059",
    "Jeffery2017": "Jeffery, S. et al. Biochar boosts tropical but not temperate crop yields. Environmental Research "
                   "Letters, 12, 053001, 2017. https://doi.org/10.1088/1748-9326/aa67bd",
}

# ----------------------------------------------------------------------------- presets de biocarvão
# Propriedades relatadas nos artigos. H/C e O/C molares.
PRESETS_BIOCARVAO = {
    "Madeira/lenhoso ≥ 500 °C (Al-Gaashani 2026)": {
        "c_org_frac": 0.66, "h_c_org": 0.30, "o_c_org": 0.20, "tipo": "estrutural",
        "fonte": "AlGaashani2026", "nota": "C médio 66,1% (todas as condições); H/C 0,30 a 600 °C; O/C < 0,24 a ≥ 500 °C"},
    "Resíduo agrícola verde ≥ 500 °C (Al-Gaashani 2026)": {
        "c_org_frac": 0.55, "h_c_org": 0.35, "o_c_org": 0.20, "tipo": "nutriente",
        "fonte": "AlGaashani2026", "nota": "C médio 54,8%; H/C 0,35; rico em K e Ca"},
    "Resíduo agrícola verde 300 °C (Al-Gaashani 2026)": {
        "c_org_frac": 0.55, "h_c_org": 0.89, "o_c_org": 0.35, "tipo": "nutriente",
        "fonte": "AlGaashani2026", "nota": "H/C 0,79–0,99 a 300 °C (média usada); O/C assumido"},
    "Lodo de esgoto 500 °C (Chagas 2024)": {
        "c_org_frac": 0.19, "h_c_org": 1.1, "o_c_org": 3.0, "tipo": "nutriente",
        "fonte": "Chagas2024", "nota": "C 19,0%; H/C 1,1; O/C 3,0; cinzas 62,7% (Tabela 1)"},
    "Lodo de esgoto 300 °C (Chagas 2024)": {
        "c_org_frac": 0.234, "h_c_org": 1.8, "o_c_org": 2.2, "tipo": "nutriente",
        "fonte": "Chagas2024", "nota": "C 23,4%; H/C 1,8; O/C 2,2; cinzas 53,1% (Tabela 1)"},
}

# ----------------------------------------------------------------------------- casos de campo (produtividade)
CASOS_PRODUTIVIDADE = [
    {"caso": "Chagas 2024 · SSB300 + NPK vs. NPK (milho, 7 safras)", "fonte": "Chagas2024",
     "observado": 9.58 / 8.63 - 1, "adubacao": "completa", "dose": 30.0, "tipo": "nutriente",
     "ph": 5.6, "v": 55.0, "argila": 50.0, "c_solo": 26.4,
     "premissas": "V% 55 (calagem relatada); C do solo 26,4 g/kg (controle); pH 5,6 e argila 50% assumidos (Latossolo argiloso)"},
    {"caso": "Chagas 2024 · SSB500 + NPK vs. NPK", "fonte": "Chagas2024",
     "observado": 8.82 / 8.63 - 1, "adubacao": "completa", "dose": 30.0, "tipo": "nutriente",
     "ph": 5.6, "v": 55.0, "argila": 50.0, "c_solo": 26.4, "premissas": "idem"},
    {"caso": "Chagas 2024 · SSB300 sem NPK vs. controle", "fonte": "Chagas2024",
     "observado": 0.498, "adubacao": "sem_adubacao", "dose": 30.0, "tipo": "nutriente",
     "ph": 5.6, "v": 55.0, "argila": 50.0, "c_solo": 26.4, "premissas": "idem"},
    {"caso": "Chagas 2024 · SSB500 sem NPK vs. controle", "fonte": "Chagas2024",
     "observado": 0.417, "adubacao": "sem_adubacao", "dose": 30.0, "tipo": "nutriente",
     "ph": 5.6, "v": 55.0, "argila": 50.0, "c_solo": 26.4, "premissas": "idem"},
    {"caso": "Latawiec 2019 · Brachiaria, biocarvão vs. controle (2 anos)", "fonte": "Latawiec2019",
     "observado": 0.27, "adubacao": "sem_adubacao", "dose": 15.0, "tipo": "estrutural",
     "ph": 5.0, "v": 35.0, "argila": 15.0, "c_solo": 10.0,
     "premissas": "Planossolo de pastagem degradada; pH 5,0, V% 35, argila 15% e C 10 g/kg assumidos"},
]

# Faixas gerais (sem condições de solo detalhadas): servem de verificação de ordem de grandeza.
FAIXAS_LITERATURA = [
    {"evidencia": "Meta-análise com > 100 estudos (Liu et al., 2019, citada em Rani & Garg 2025)",
     "efeito_medio": 0.13, "fonte": "Rani2025"},
    {"evidencia": "Meta-análise com 114 publicações (Chen et al., 2023, citada em Rani & Garg 2025)",
     "efeito_medio": 0.20, "fonte": "Rani2025"},
    {"evidencia": "Soja, 20 t/ha de resíduos agrícolas (Liu et al., 2017, em Rani & Garg 2025)",
     "efeito_medio": 0.07, "fonte": "Rani2025"},
    {"evidencia": "Milho, biocarvão de eucalipto (Puga et al., 2020, em Rani & Garg 2025)",
     "efeito_medio": 0.26, "fonte": "Rani2025"},
]


def prever_resposta(caso: dict, com_dose_e_adubacao: bool = True, meia_saturacao: float = 5.0,
                    referencia: float = 15.0, fatores_adubacao: dict | None = None) -> float:
    base = float(resposta_media_vetor(caso["ph"], caso["v"], caso["tipo"], caso["argila"], caso["c_solo"]))
    if not com_dose_e_adubacao:
        return base
    fa = fatores_adubacao[caso["adubacao"]] if fatores_adubacao else fator_adubacao(caso["adubacao"], caso["tipo"])
    return base * fator_dose(caso["dose"], referencia, meia_saturacao) * fa


def validar_produtividade(meia_saturacao: float = 5.0, referencia: float = 15.0) -> pd.DataFrame:
    linhas = []
    for c in CASOS_PRODUTIVIDADE:
        antes = prever_resposta(c, com_dose_e_adubacao=False)
        depois = prever_resposta(c, True, meia_saturacao, referencia)
        linhas.append({"caso": c["caso"], "fonte": c["fonte"], "dose_t_ha": c["dose"], "adubacao": c["adubacao"],
                       "observado": c["observado"], "previsto_modelo_anterior": antes,
                       "previsto_calibrado": depois, "erro_anterior_pp": 100 * (antes - c["observado"]),
                       "erro_calibrado_pp": 100 * (depois - c["observado"]), "premissas": c["premissas"]})
    return pd.DataFrame(linhas)


def calibrar_fatores_adubacao() -> dict:
    """Fator que iguala, em média geométrica, o previsto (com dose) ao observado em cada manejo."""
    out = {}
    for manejo in ("completa", "sem_adubacao"):
        for tipo in ("estrutural", "nutriente"):
            razoes = [c["observado"] / prever_resposta(c, True, fatores_adubacao={manejo: 1.0})
                      for c in CASOS_PRODUTIVIDADE if c["adubacao"] == manejo and c["tipo"] == tipo]
            out[f"{manejo}/{tipo}"] = {"fator": float(np.exp(np.mean(np.log(razoes)))) if razoes else None,
                                       "n_ensaios": len(razoes)}
    return out


# ----------------------------------------------------------------------------- carbono no solo
def validar_carbono(perm_a: float = 1.13, perm_b: float = 0.46, padrao: str = "EBC") -> pd.DataFrame:
    """Compara o C retido previsto (dose × C × F_perm) com o medido em campo."""
    from simulador import ParametrosCarbono
    cb = ParametrosCarbono(perm_intercepto=perm_a, perm_inclinacao=perm_b)
    casos = [
        {"caso": "Chagas 2024 · SSB500 (+NPK), 30 t/ha, 7 safras, 0–20 cm", "fonte": "Chagas2024",
         "dose": 30.0, "c_org": 0.19, "h_c": 1.1, "o_c": 3.0,
         # 49,47 Mg/ha = +6,53% sobre a média de controle e NPK -> diferença de ~3,03 Mg C/ha
         "observado_tc_ha": 49.47 - 49.47 / 1.0653,
         "nota": "estoque 49,47 Mg/ha, +6,53% sobre controle/NPK; SSB300 sem aumento significativo"},
        {"caso": "Latawiec 2019 · biocarvão de gliricídia, 15 t/ha (balanço de massa em vaso)", "fonte": "Latawiec2019",
         "dose": 15.0, "c_org": 0.66, "h_c": 0.30, "o_c": 0.20,
         "observado_tc_ha": 13.0 * 12 / 44,
         "nota": "13 tCO2e/ha relatados; C, H/C e O/C do biocarvão não informados (usado preset lenhoso, assumido)"},
    ]
    linhas = []
    for k in casos:
        bc = ParametrosBiocarvao(dose_t_ha=k["dose"], c_org_frac=k["c_org"], h_c_org=k["h_c"], o_c_org=k["o_c"])
        f = fator_permanencia(bc, cb, ParametrosSolo())
        aplicado = k["dose"] * k["c_org"]
        previsto = aplicado * f
        ok, motivos = checar_padrao(k["c_org"], k["h_c"], k["o_c"], padrao)
        linhas.append({"caso": k["caso"], "fonte": k["fonte"], "c_aplicado_tc_ha": aplicado,
                       "fator_permanencia": f, "previsto_tc_ha": previsto, "observado_tc_ha": k["observado_tc_ha"],
                       "razao_prev_obs": previsto / k["observado_tc_ha"],
                       "elegivel_" + padrao: ok, "motivos": "; ".join(motivos), "nota": k["nota"]})
    return pd.DataFrame(linhas)


def elegibilidade_presets() -> pd.DataFrame:
    """Matriz preset × padrão (Lin et al. 2025)."""
    linhas = []
    for nome, p in PRESETS_BIOCARVAO.items():
        linha = {"biocarvao": nome}
        for pad in PADROES:
            if pad == "personalizado":
                continue
            linha[pad] = checar_padrao(p["c_org_frac"], p["h_c_org"], p["o_c_org"], pad)[0]
        linhas.append(linha)
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------------- framework GCB (artigo base)
PRECOS_VIAVEIS_ETS = [  # Tabela 3 do artigo GCB Bioenergy
    {"desafio": "Alto custo da biomassa; exige subsídio", "ets": "EU ETS", "preco": 88, "moeda": "EUR", "pais": "Finlândia"},
    {"desafio": "Custo e estratégias de implantação", "ets": "CFETS", "preco": 90, "moeda": "USD", "pais": "China"},
    {"desafio": "Falta de transparência na cadeia de biomassa", "ets": "RGGI", "preco": 100, "moeda": "USD", "pais": "EUA"},
    {"desafio": "Barreiras regulatórias e difusão de mercado", "ets": "EU ETS", "preco": 72, "moeda": "EUR", "pais": "Alemanha"},
    {"desafio": "Custos operacionais e flutuação do preço de energia", "ets": "SBCE", "preco": 120, "moeda": "USD", "pais": "Brasil"},
]

FIGURA1_CRITERIOS = [  # Figura 1 do artigo GCB Bioenergy
    {"criterio": "H/Corg < 0,7", "padroes": "EBC, CNAIS, SGS, BQM, ANZBI", "no_app": "filtro de elegibilidade por padrão"},
    {"criterio": "O/Corg < 0,4", "padroes": "EBC, CNAIS", "no_app": "filtro de elegibilidade por padrão"},
    {"criterio": "Rastreabilidade da matéria-prima", "padroes": "EBC", "no_app": "pacote de originação + marco lote_certificado"},
    {"criterio": "Ausência de contaminantes", "padroes": "EBC, CNAIS", "no_app": "laudo do lote no marco lote_certificado"},
    {"criterio": "Processo energeticamente eficiente > 70%", "padroes": "SGS", "no_app": "declarado pelo fornecedor (não modelado)"},
    {"criterio": "Umidade > 70% aceita na matéria-prima", "padroes": "BQM", "no_app": "não modelado"},
    {"criterio": "Pirólise aceita; carbonização hidrotérmica e torrefação não", "padroes": "ANZBI", "no_app": "presets só de pirólise"},
]

FIGURA2_FERRAMENTAS = [  # Figura 2 do artigo GCB Bioenergy -> onde está no app
    {"ramo": "Incentivos econômicos", "ferramenta": "Incentivos a tecnologias de captura de carbono", "no_app": "cenários de preço por ETS (Tabela 3)"},
    {"ramo": "Incentivos econômicos", "ferramenta": "Redução de impostos com transparência em blockchain", "no_app": "hash do pacote e marcos na API"},
    {"ramo": "Associação com fintechs", "ferramenta": "P2P lending", "no_app": "empréstimo SEP e cota sênior P2P do fundo"},
    {"ramo": "Associação com fintechs", "ferramenta": "Opções flexíveis de financiamento", "no_app": "carência, prazo, crédito embutido, fundo com cotas"},
    {"ramo": "Eficiência de custos", "ferramenta": "Aditivos/catalisadores para melhorar propriedades e preço", "no_app": "presets por matéria-prima e temperatura"},
    {"ramo": "Cadeias de valor", "ferramenta": "Plataforma de benefícios do solo por concentração e processo", "no_app": "simulador, BDsolos, Saúde do Solo, ranking PR/SC"},
    {"ramo": "Cadeias de valor", "ferramenta": "Conectar fornecedores e produtores por contratos inteligentes", "no_app": "API: originação, aceite, marcos, pagamento ao fornecedor"},
]

SBCE_FIGURA3 = ("Figura 3 do artigo: o SBCE avança por setores até alcançar todos em 2031 (transportes por último), "
                "com meta de redução de 59% a 67%; instalações que emitem mais de 25 mil tCO2e/ano ficam sujeitas a "
                "relato e verificação, cerca de 2.188 operadores.")
