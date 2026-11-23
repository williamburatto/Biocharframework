"""
English labels for texts produced by the calculation modules (used by app_en.py).

The calculation modules keep Portuguese keys (they are part of the data model and the API);
this module translates them only for display.
"""

from __future__ import annotations

import pandas as pd

CROP_EN = {
    "soja": "soybean", "milho": "maize", "milho safrinha": "second-season maize", "trigo": "wheat",
    "feijão": "common bean", "arroz irrigado": "irrigated rice", "cana-de-açúcar": "sugarcane",
    "personalizada": "custom",
}

TIPO_EN = {"estrutural": "structural (wood, straw, husk)", "nutriente": "nutrient-rich (manure, sludge)"}

PRESET_EN = {
    "personalizado": "custom",
    "Madeira/lenhoso ≥ 500 °C (Al-Gaashani 2026)": "Woody biomass ≥ 500 °C (Al-Gaashani 2026)",
    "Resíduo agrícola verde ≥ 500 °C (Al-Gaashani 2026)": "Green agricultural waste ≥ 500 °C (Al-Gaashani 2026)",
    "Resíduo agrícola verde 300 °C (Al-Gaashani 2026)": "Green agricultural waste 300 °C (Al-Gaashani 2026)",
    "Lodo de esgoto 500 °C (Chagas 2024)": "Sewage sludge 500 °C (Chagas 2024)",
    "Lodo de esgoto 300 °C (Chagas 2024)": "Sewage sludge 300 °C (Chagas 2024)",
}

PRESET_NOTE_EN = {
    "Madeira/lenhoso ≥ 500 °C (Al-Gaashani 2026)": "Mean C 66.1% (all conditions); H/C 0.30 at 600 °C; O/C < 0.24 at ≥ 500 °C",
    "Resíduo agrícola verde ≥ 500 °C (Al-Gaashani 2026)": "Mean C 54.8%; H/C 0.35; rich in K and Ca",
    "Resíduo agrícola verde 300 °C (Al-Gaashani 2026)": "H/C 0.79–0.99 at 300 °C (mean used); O/C assumed",
    "Lodo de esgoto 500 °C (Chagas 2024)": "C 19.0%; H/C 1.1; O/C 3.0; ash 62.7% (Table 1)",
    "Lodo de esgoto 300 °C (Chagas 2024)": "C 23.4%; H/C 1.8; O/C 2.2; ash 53.1% (Table 1)",
}

PADRAO_NOTE_EN = {
    "EBC": "Total C ≥ 50%; H/Corg < 0.71; O/Corg < 0.42",
    "IBI": "Organic C ≥ 10%; H/Corg ≤ 0.71",
    "BQM": "Organic C ≥ 10%; H/Corg ≤ 0.71",
    "ANZBI": "Total C > 50% and organic C > 30%; H/Corg ≤ 0.71",
    "CNAIS I": "Total C ≥ 60%; fixed C ≥ 50%; H/C ≤ 0.4; O/C ≤ 0.2",
    "CNAIS II": "Total C ≥ 30%; fixed C ≥ 25%; H/C ≤ 0.75; O/C ≤ 0.4",
    "SGS": "Organic C 30–95% (pyrolysis); H/Corg ≤ 0.71",
    "personalizado": "user-defined limits",
}
PADRAO_EN = {"personalizado": "custom"}

PAIS_EN = {"Finlândia": "Finland", "China": "China", "EUA": "USA", "Alemanha": "Germany", "Brasil": "Brazil"}

SAUDE_EN = {"saudavel": "healthy", "recuperando": "recovering", "intermediario": "intermediate",
            "adoecendo": "deteriorating", "doente": "unhealthy"}

FINALIDADE_EN = {"analise_credito": "credit analysis", "registro_garantias": "collateral registration",
                 "certificacao_carbono": "carbon certification", "pesquisa_anonimizada": "anonymised research"}

CLASSES_EN = {
    "Cada vantagem sozinha paga": "Each benefit pays on its own",
    "Só a produtividade paga": "Only the yield gain pays",
    "Só o carbono paga": "Only carbon pays",
    "Só as duas juntas pagam": "Only both together pay",
    "Inviável": "Not viable",
}

VEREDITO_EN = {
    "Viável só com o aumento de produtividade": "Viable with the yield gain alone",
    "Viável somando produtividade e carbono": "Viable combining yield and carbon",
    "Não viável nas condições atuais": "Not viable under current conditions",
}

SENS_EN = {
    "P(VPL>0) sem carbono": "P(NPV>0) without carbon",
    "P(VPL>0) com carbono": "P(NPV>0) with carbon",
    "Prob. inadimplência": "Default probability",
    "VPL mediano com carbono (R$)": "Median NPV with carbon (R$)",
}

ADUB_EN = {"completa": "NPK-fertilised", "sem_adubacao": "unfertilised / degraded pasture"}

FAIXAS_EN = [
    {"evidence": "Meta-analysis of > 100 studies (Liu et al., 2019, cited in Rani & Garg 2025)", "mean_effect": 0.13},
    {"evidence": "Meta-analysis of 114 publications (Chen et al., 2023, cited in Rani & Garg 2025)", "mean_effect": 0.20},
    {"evidence": "Soybean, 20 t/ha of agricultural residue biochar (Liu et al., 2017, in Rani & Garg 2025)", "mean_effect": 0.07},
    {"evidence": "Maize, eucalyptus biochar (Puga et al., 2020, in Rani & Garg 2025)", "mean_effect": 0.26},
]

FIGURA1_EN = [
    {"criterion": "H/Corg < 0.7", "standards": "EBC, CNAIS, SGS, BQM, ANZBI", "in_app": "eligibility filter by standard"},
    {"criterion": "O/Corg < 0.4", "standards": "EBC, CNAIS", "in_app": "eligibility filter by standard"},
    {"criterion": "Feedstock traceability", "standards": "EBC", "in_app": "origination package + lot_certified milestone"},
    {"criterion": "Absence of harmful contaminants", "standards": "EBC, CNAIS", "in_app": "lot report at the lot_certified milestone"},
    {"criterion": "Energy-efficient process > 70%", "standards": "SGS", "in_app": "declared by the supplier (not modelled)"},
    {"criterion": "Feedstock moisture content > 70% accepted", "standards": "BQM", "in_app": "not modelled"},
    {"criterion": "Pyrolysis accepted; hydrothermal carbonisation and torrefaction are not", "standards": "ANZBI", "in_app": "pyrolysis-only presets"},
]

FIGURA2_EN = [
    {"branch": "Economic incentives", "tool": "Incentives for carbon capture scale-up technologies", "in_app": "price scenarios by ETS (Table 3)"},
    {"branch": "Economic incentives", "tool": "Tax reduction with blockchain transparency", "in_app": "package hash and API milestones"},
    {"branch": "Fintechs association", "tool": "P2P lending", "in_app": "SEP loan and P2P senior quota of the fund"},
    {"branch": "Fintechs association", "tool": "Flexible financing options", "in_app": "grace period, term, embedded credit, tranched fund"},
    {"branch": "Cost efficiency", "tool": "Additives/catalysts to improve properties and selling price", "in_app": "presets by feedstock and temperature"},
    {"branch": "Value chains", "tool": "Platform with soil-benefit information by concentration and process", "in_app": "simulator, BDsolos, Soil Health, PR/SC ranking"},
    {"branch": "Value chains", "tool": "Connect suppliers and land managers via smart contracts", "in_app": "API: origination, acceptance, milestones, supplier payment"},
]

ETS_DESAFIO_EN = {
    "Alto custo da biomassa; exige subsídio": "High biomass cost; requires subsidy",
    "Custo e estratégias de implantação": "Cost and deployment strategies",
    "Falta de transparência na cadeia de biomassa": "Lack of transparent biomass supply chains",
    "Barreiras regulatórias e difusão de mercado": "Regulatory barriers and broader market diffusion",
    "Custos operacionais e flutuação do preço de energia": "Operational costs and energy price fluctuation",
}

SBCE_EN = ("Figure 3 of the paper: the Brazilian ETS (SBCE) phases in sector by sector until all sectors are covered "
           "in 2031 (transport last), with a 59% to 67% reduction target; installations emitting more than 25 thousand "
           "tCO2e/year must report and verify, about 2,188 operators.")

REFERENCIAS_EN_GCB = ("Buratto, W. G.; Muniz, R. N.; Villarubia González, G.; Barros, C. F. O.; Costa, V. J.; Nied, A. "
                      "Biochar framework for carbon capture and credit certification across regulatory standards. "
                      "GCB Bioenergy (manuscript).")

CASO_EN = {
    "Chagas 2024 · SSB300 + NPK vs. NPK (milho, 7 safras)": "Chagas 2024 · SSB300 + NPK vs. NPK (maize, 7 seasons)",
    "Chagas 2024 · SSB500 + NPK vs. NPK": "Chagas 2024 · SSB500 + NPK vs. NPK",
    "Chagas 2024 · SSB300 sem NPK vs. controle": "Chagas 2024 · SSB300 without NPK vs. control",
    "Chagas 2024 · SSB500 sem NPK vs. controle": "Chagas 2024 · SSB500 without NPK vs. control",
    "Latawiec 2019 · Brachiaria, biocarvão vs. controle (2 anos)": "Latawiec 2019 · Brachiaria, biochar vs. control (2 years)",
    "Chagas 2024 · SSB500 (+NPK), 30 t/ha, 7 safras, 0–20 cm": "Chagas 2024 · SSB500 (+NPK), 30 t/ha, 7 seasons, 0–20 cm",
    "Latawiec 2019 · biocarvão de gliricídia, 15 t/ha (balanço de massa em vaso)":
        "Latawiec 2019 · Gliricidia biochar, 15 t/ha (pot mass balance)",
}

PREMISSA_EN = {
    "V% 55 (calagem relatada); C do solo 26,4 g/kg (controle); pH 5,6 e argila 50% assumidos (Latossolo argiloso)":
        "Base saturation 55% (liming reported); soil C 26.4 g/kg (control); pH 5.6 and clay 50% assumed (clayey Oxisol)",
    "idem": "same as above",
    "Planossolo de pastagem degradada; pH 5,0, V% 35, argila 15% e C 10 g/kg assumidos":
        "Planosol under degraded pasture; pH 5.0, base saturation 35%, clay 15% and C 10 g/kg assumed",
}

NOTA_C_EN = {
    "estoque 49,47 Mg/ha, +6,53% sobre controle/NPK; SSB300 sem aumento significativo":
        "stock 49.47 Mg/ha, +6.53% over control/NPK; SSB300 with no significant increase",
    "13 tCO2e/ha relatados; C, H/C e O/C do biocarvão não informados (usado preset lenhoso, assumido)":
        "13 tCO2e/ha reported; biochar C, H/C and O/C not reported (woody preset assumed)",
}

SOLO_ATTR_EN = {"pH em água": "pH (water)", "V% (saturação por bases)": "Base saturation (%)",
                "Argila (%)": "Clay (%)", "C orgânico (g/kg)": "Organic C (g/kg)", "Estoque de C (t/ha)": "C stock (t/ha)"}


def municipio_en(d: dict) -> dict:
    d = dict(d)
    d["veredito"] = VEREDITO_EN.get(d["veredito"], d["veredito"])
    anual = d["anual"].rename(columns={"Ano": "Year", "Aumento de produtividade (t/ha)": "Yield increase (t/ha)",
                                       "Ganho (R$/ha)": "Gain (R$/ha)"})
    solo = d["solo"].copy()
    solo.iloc[:, 0] = solo.iloc[:, 0].map(lambda x: SOLO_ATTR_EN.get(x, x))
    solo.columns = ["Attribute (0–20 cm)", "Municipality (median)", solo.columns[2].replace("(mediana)", "(median)")]
    d["anual"], d["solo"] = anual, solo
    return d


def ranking_en(r: pd.DataFrame) -> pd.DataFrame:
    if r.empty:
        return r
    r = r.copy()
    r["veredito"] = r["veredito"].map(lambda v: VEREDITO_EN.get(v, v))
    return r


def validacao_prod_en(v: pd.DataFrame) -> pd.DataFrame:
    v = v.copy()
    v["caso"] = v["caso"].map(lambda x: CASO_EN.get(x, x))
    v["premissas"] = v["premissas"].map(lambda x: PREMISSA_EN.get(x, x))
    v["adubacao"] = v["adubacao"].map(lambda x: ADUB_EN.get(x, x))
    return v.rename(columns={"caso": "case", "fonte": "source", "dose_t_ha": "dose_t_ha", "adubacao": "fertilisation",
                             "observado": "observed", "previsto_modelo_anterior": "previous_model",
                             "previsto_calibrado": "calibrated", "erro_anterior_pp": "previous_error_pp",
                             "erro_calibrado_pp": "calibrated_error_pp", "premissas": "assumptions"})


def validacao_carbono_en(v: pd.DataFrame) -> pd.DataFrame:
    v = v.copy()
    v["caso"] = v["caso"].map(lambda x: CASO_EN.get(x, x))
    v["nota"] = v["nota"].map(lambda x: NOTA_C_EN.get(x, x))
    ren = {"caso": "case", "fonte": "source", "c_aplicado_tc_ha": "C_applied_tC_ha",
           "fator_permanencia": "permanence_factor", "previsto_tc_ha": "predicted_tC_ha",
           "observado_tc_ha": "measured_tC_ha", "razao_prev_obs": "predicted_to_measured",
           "motivos": "failed_criteria", "nota": "note"}
    ren.update({c: c.replace("elegivel_", "eligible_") for c in v.columns if c.startswith("elegivel_")})
    return v.rename(columns=ren)


def fatores_en(cal: dict) -> pd.DataFrame:
    linhas = []
    for k, val in cal.items():
        manejo, tipo = k.split("/")
        linhas.append({"fertilisation / biochar type": f"{ADUB_EN.get(manejo, manejo)} / {tipo}",
                       "factor": val["fator"], "field trials": val["n_ensaios"]})
    return pd.DataFrame(linhas)


def elegibilidade_en(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    e["biocarvao"] = e["biocarvao"].map(lambda x: PRESET_EN.get(x, x))
    return e.rename(columns={"biocarvao": "biochar"})


def ets_en(precos: list) -> pd.DataFrame:
    return pd.DataFrame([{"challenge": ETS_DESAFIO_EN.get(p["desafio"], p["desafio"]), "ETS": p["ets"],
                          "feasible price": p["preco"], "currency": p["moeda"],
                          "country": PAIS_EN.get(p["pais"], p["pais"])} for p in precos])
