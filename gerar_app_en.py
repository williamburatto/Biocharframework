"""
Gera app_en.py (versão em inglês) a partir de app.py.

Uso:  python gerar_app_en.py
Rode de novo sempre que app.py mudar e confira as mensagens: o script falha se um
trecho de código esperado não for encontrado. A lógica de cálculo é a mesma; só os
textos de interface mudam (os módulos de cálculo continuam com chaves em português,
traduzidas na exibição por i18n_en.py).
"""

import ast
import re
import sys
from pathlib import Path

AQUI = Path(__file__).parent


def extrair_segmentos(src: str) -> list[str]:
    b = src.encode("utf-8")
    tree = ast.parse(src)
    linhas = b.splitlines(keepends=True)
    offs = [0]
    for l in linhas:
        offs.append(offs[-1] + len(l))

    def seg(n):
        return b[offs[n.lineno - 1] + n.col_offset: offs[n.end_lineno - 1] + n.end_col_offset].decode("utf-8")

    dentro = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            for v in ast.walk(n):
                if v is not n:
                    dentro.add(id(v))
    nos = [n for n in ast.walk(tree) if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                                         and id(n) not in dentro) or isinstance(n, ast.JoinedStr)]
    nos.sort(key=lambda n: (n.lineno, n.col_offset))
    out, vistos = [], set()
    for n in nos:
        if n.lineno < 9:
            continue
        s = seg(n)
        val = n.value if isinstance(n, ast.Constant) else s
        if not (re.search(r"[ À-ÿ]", val) or re.search(r"[A-Z]", val)):
            continue
        if s in vistos:
            continue
        vistos.add(s)
        out.append(s)
    return out


# ----------------------------------------------------------------------------- 1. blocos de código
BLOCOS = [
    ("from aba_inicio import ROTULO_INICIO, render_inicio\n",
     "from aba_inicio import ROTULO_INICIO_EN as ROTULO_INICIO, render_inicio_en as render_inicio\n"),
    ("from aba_brasil import ROTULO_BRASIL, render_brasil\n",
     "from aba_brasil import ROTULO_BRASIL_EN as ROTULO_BRASIL, render_brasil_en as render_brasil\n"),
    ("from aba_mercados import ROTULO_MERCADOS, render_mercados\n",
     "from aba_mercados import ROTULO_MERCADOS_EN as ROTULO_MERCADOS, render_mercados_en as render_mercados\n"),
    ('''"""
BioCrédito Agro — interface Streamlit do simulador.

Rodar localmente:   streamlit run app.py
Para embutir em outro app multipágina: copie este arquivo para pages/ e mantenha
simulador.py importável (mesma pasta ou pacote).
"""''', '''"""
BioCrédito Agro — Streamlit interface (English version, generated from app.py by gerar_app_en.py).

Run locally:   streamlit run app_en.py
"""'''),
    ('''                       FIGURA1_CRITERIOS, FIGURA2_FERRAMENTAS, SBCE_FIGURA3)
''', '''                       FIGURA1_CRITERIOS, FIGURA2_FERRAMENTAS, SBCE_FIGURA3)
from i18n_en import *  # noqa: F401,F403  (English display labels)
'''),
    ('''def num(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")''',
     '''def num(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}"'''),
    ('''def sacas(t_ha: float) -> str:
    return f"{num(t_ha * 1000 / 60, 1)} sc/ha"''', '''def sacas(t_ha: float) -> str:
    return f"{num(t_ha * 1000 / 60, 1)} bags of 60 kg/ha"'''),
    ('''    return f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")''',
     '''    return f"R$ {x:,.0f}"'''),
    ('''st.selectbox("Cultura", list(CULTURAS))''', '''st.selectbox("Crop", list(CULTURAS), format_func=lambda k: CROP_EN.get(k, k))'''),
    ('''st.selectbox("Classe predominante no município", CLASSES_SAUDE, index=2)''',
     '''st.selectbox("Predominant class in the municipality", CLASSES_SAUDE, index=2, format_func=lambda k: SAUDE_EN.get(k, k))'''),
    ('''st.selectbox("Condição do solo no laudo", CLASSES_SAUDE, index=2)''',
     '''st.selectbox("Soil condition in the report", CLASSES_SAUDE, index=2, format_func=lambda k: SAUDE_EN.get(k, k))'''),
    ('''st.selectbox("Biocarvão de referência (literatura)", ["personalizado"] + list(PRESETS_BIOCARVAO),''',
     '''st.selectbox("Reference biochar (literature)", ["personalizado"] + list(PRESETS_BIOCARVAO),
                               format_func=lambda k: PRESET_EN.get(k, k),'''),
    ('''        st.caption(pr_bc["nota"])''', '''        st.caption(PRESET_NOTE_EN.get(preset_nome, pr_bc["nota"]))'''),
    ('''index=["estrutural", "nutriente"].index(pr_bc["tipo"]),''',
     '''index=["estrutural", "nutriente"].index(pr_bc["tipo"]), format_func=lambda k: TIPO_EN.get(k, k),'''),
    ('''st.selectbox("Padrão de certificação", list(PADROES),''',
     '''st.selectbox("Certification standard", list(PADROES), format_func=lambda k: PADRAO_EN.get(k, k),'''),
    ('''    st.caption(PADROES[padrao]["nota"])''', '''    st.caption(PADRAO_NOTE_EN.get(padrao, PADROES[padrao]["nota"]))'''),
    ('''f"{e['ets']} {e['pais']}: {e['preco']} {e['moeda']}/t"''',
     '''f"{e['ets']} {PAIS_EN.get(e['pais'], e['pais'])}: {e['preco']} {e['moeda']}/t"'''),
    ('''st.multiselect("Finalidades autorizadas pelo produtor", FINALIDADES,''',
     '''st.multiselect("Purposes authorised by the farmer", FINALIDADES, format_func=lambda k: FINALIDADE_EN.get(k, k),'''),
    ('''        d = detalhar_municipio_app(cenario.to_dict(), uf_m, mun_m)''',
     '''        d = municipio_en(detalhar_municipio_app(cenario.to_dict(), uf_m, mun_m))'''),
    ('''        cult = cenario.cultura.cultura''', '''        cult = cenario.cultura.cultura
        cult_en = CROP_EN.get(cult, cult)'''),
    ('''    st.bar_chart(cls.rename("Fração das simulações"), horizontal=True)''',
     '''    st.bar_chart(cls.rename(index=CLASSES_EN).rename("Share of simulations"), horizontal=True)'''),
    ('''        ranking = avaliar_municipios_app(cenario.to_dict(), tuple(ufs_r), min_p)''',
     '''        ranking = ranking_en(avaliar_municipios_app(cenario.to_dict(), tuple(ufs_r), min_p))'''),
    ('''        tab = analise_sensibilidade(cen_sens, caminho, valores, perfis_sel)''',
     '''        tab = analise_sensibilidade(cen_sens, caminho, valores, perfis_sel).rename(columns=SENS_EN)'''),
]

BLOCO_VALIDACAO_INI = "with aba_val:\n"
BLOCO_VALIDACAO_FIM = "with aba_f:\n"
BLOCO_VALIDACAO_EN = '''with aba_val:
    st.subheader("Validation of yield and carbon against five papers")
    st.markdown(
        "The yield-response model was tested against field trials in Brazil. The previous model (no dose and no "
        "fertilisation effect) had large errors: it underestimated the gain without fertiliser and overestimated it "
        "with NPK. Three changes were made: a **dose factor** (saturating, 1.0 at 15 t/ha), a **fertilisation × "
        "biochar-type factor** and a **10% annual decay** of the effect.")
    vp = validar_produtividade()
    mae_a, mae_d = vp["erro_anterior_pp"].abs().mean(), vp["erro_calibrado_pp"].abs().mean()
    m1, m2, m3 = st.columns(3)
    m1.metric("Mean absolute error — previous model", f"{num(mae_a, 1)} p.p.")
    m2.metric("Mean absolute error — calibrated", f"{num(mae_d, 1)} p.p.")
    m3.metric("Field trials used", f"{len(vp)}")
    st.caption("Note: the factors were fitted to these same trials, so the calibrated error measures fit, not "
               "independent validation. New cooperative trials (the 'Observed trials' field) provide the validation.")
    vp_en = validacao_prod_en(vp)
    graf = vp_en.set_index("case")[["observed", "previous_model", "calibrated"]]
    st.bar_chart(graf, horizontal=True, stack=False)
    st.dataframe(vp_en, width="stretch", hide_index=True, column_config={
        "observed": st.column_config.NumberColumn("Observed", format="%.3f"),
        "previous_model": st.column_config.NumberColumn("Previous model", format="%.3f"),
        "calibrated": st.column_config.NumberColumn("Calibrated", format="%.3f"),
        "previous_error_pp": st.column_config.NumberColumn("Previous error (p.p.)", format="%.1f"),
        "calibrated_error_pp": st.column_config.NumberColumn("Calibrated error (p.p.)", format="%.1f")})
    st.markdown("**Calibrated fertilisation factors** (geometric mean of observed/predicted)")
    st.dataframe(fatores_en(calibrar_fatores_adubacao()), hide_index=True)
    st.markdown("**Order of magnitude in the literature** (Rani & Garg, 2025)")
    st.dataframe(pd.DataFrame(FAIXAS_EN), hide_index=True, width="stretch")

    st.markdown("**Carbon retained in soil: predicted vs. measured**")
    vc = validar_carbono(cenario.carbono.perm_intercepto, cenario.carbono.perm_inclinacao, cenario.carbono.padrao)
    st.dataframe(validacao_carbono_en(vc), width="stretch", hide_index=True)
    st.markdown(
        "- **Chagas et al. (2024):** the permanence factor predicts 3.6 t C/ha retained versus about 3.0 measured "
        "over 7 seasons (ratio 1.17). The sewage sludge biochar, however, fails every standard "
        "(C < 30% and H/C > 0.75): it raises soil carbon but generates no credit.\\n"
        "- **Latawiec et al. (2019):** 13 tCO₂e/ha measured by pot mass balance, versus about 2.8 times that from "
        "the permanence factor. The paper does not report the biochar C or H/C, so the comparison uses assumed "
        "values. It supports keeping a prudence discount on carbon in the decision rule.\\n"
        "- **Al-Gaashani et al. (2026)** and **Lin et al. (2025):** pyrolysis temperature decides eligibility. "
        "Green-waste biochar at 300 °C (H/C 0.79–0.99) fails every standard; at ≥ 500 °C (H/C 0.30–0.42) it passes.")
    st.markdown("**Eligibility of the reference biochars by standard** (limits from Lin et al., 2025)")
    st.dataframe(elegibilidade_en(elegibilidade_presets()), hide_index=True, width="stretch")
    st.markdown("**Not validated by the papers:** lime and fertiliser savings, the dose half-saturation, and the "
                "response of soybean, wheat and common bean to biochar under full fertilisation.")

with aba_gcb:
    st.subheader("Framework of the base paper and where each part is in the app")
    st.markdown(f"*{REFERENCIAS_EN_GCB}*")
    st.markdown(
        "The paper built the framework in three steps: (a) comparison of biochar quality standards (Figure 1); "
        "(b) mapping of technological and financial tools that reduce barriers (Figure 2); (c) integration into a "
        "framework linking certification, traceability and market outcomes (Figure 4). This app implements step (c) "
        "for Brazilian agriculture and adds agronomic validation.")
    st.markdown("**Figure 1 — quality parameters by standard**")
    st.dataframe(pd.DataFrame(FIGURA1_EN), hide_index=True, width="stretch")
    st.markdown("**Figure 2 — tools to reduce barriers and increase profitability**")
    st.dataframe(pd.DataFrame(FIGURA2_EN), hide_index=True, width="stretch")
    st.markdown("**Table 3 — challenges and feasible prices by emissions trading system** "
                "(selectable in the sidebar, under Carbon)")
    st.dataframe(ets_en(PRECOS_VIAVEIS_ETS), hide_index=True, width="stretch")
    st.markdown("**Figure 3 — Brazilian ETS (SBCE)**")
    st.write(SBCE_EN)

    st.subheader("References")
    st.markdown(f"- {REFERENCIAS_EN_GCB}")
    for chave in ["Chagas2024", "Latawiec2019", "Rani2025", "AlGaashani2026", "Lin2025", "Jeffery2017"]:
        st.markdown(f"- {REFERENCIAS[chave]}")

'''

# ----------------------------------------------------------------------------- 2. textos (índice -> fonte em inglês)
# Índices da lista extraída de app.py (a ordem é a do arquivo). None = manter.
TRAD = {
    0: '"BioCrédito Agro — Simulator"',
    1: '"BioCrédito Agro — simulator of P2P-financed biochar"',
    2: '"Monte Carlo simulation of the agronomic, carbon and financial modules. "\n    "Default values are illustrative: calibrate with soil reports, field trials and the chosen certification methodology."',
    3: '"Loading BDsolos profiles..."',
    4: '"Evaluating municipalities..."',
    5: '"Evaluating the municipality..."',
    9: '"Field and crop"',
    10: None,  # "Cultura" já tratado no bloco
    11: '"Approximate reference values: replace with the cooperative\'s, CONAB or CEPEA data."',
    12: '"Area (ha)"',
    13: '"Baseline yield Y₀ (t/ha)"',
    14: '"Crop price (R$/t)"',
    15: '"Price volatility (CV)"',
    16: '"Baseline margin without biochar (R$/ha/yr)"',
    17: '"Crop response factor to biochar"',
    18: '"Multiplies the relative yield increase. Keep it at 1.0 until field trials of this crop indicate another value."',
    19: '"Share of margin available for debt service"',
    20: '"Annual probability of a climate-driven crop loss (ZARC)"',
    21: '"Loss when it occurs"',
    22: '"Soil profiles (Embrapa BDsolos)"',
    23: '"Sample real BDsolos profiles"',
    24: '"Each simulation draws one profile (0–20 cm layer) from the filtered region."',
    25: '"File perfis_bdsolos_0_20.csv not found. Generate it with: "\n                       "python bdsolos.py bd_solos_para_redape.csv perfis_bdsolos_0_20.csv"',
    26: '"State"',
    28: '"Municipality"',
    29: '"Filter by radius around coordinates"',
    30: '"Latitude (decimal degrees)"',
    31: '"Longitude (decimal degrees)"',
    32: '"Radius (km)"',
    33: '"Soil classes (level 1, Brazilian system)"',
    34: '"Only profiles with recorded agricultural use"',
    35: 'f"{len(perfis_sel)} profiles selected"',
    36: '"Few profiles: widen the filter (whole state or larger radius)."',
    37: '"Soil"',
    38: '"With BDsolos on, the pH and base saturation below only fill gaps in the profiles."',
    39: '"pH (water)"',
    40: '"Base saturation, V (%)"',
    41: '"Mean soil temperature (°C)"',
    42: '"Limed cropland (apply minimum pH and base saturation)"',
    43: '"BDsolos profiles mostly come from old surveys under native vegetation or pasture. In limed cropland, "\n                                "current pH and base saturation are higher, and the response to biochar tends to be smaller."',
    44: '"Minimum pH in cropland"',
    45: '"Minimum base saturation in cropland (%)"',
    46: '"Soil health (Embrapa)"',
    47: '"Soil Health BR platform / BioAS: saudedosolo.embrapa.gov.br/plataforma-publica"',
    48: '"Source"',
    49: '"Do not use"',
    50: '"Municipality class"',
    51: '"BioAS report of the field"',
    52: '"Municipality CSV (uf, municipio, classe_saude, n_amostras)"',
    53: 'f"Class: {SAUDE_EN.get(linha[\'classe_saude\'], linha[\'classe_saude\'])} · {int(linha[\'n_amostras\'])} samples"',
    54: None, 62: None,
    55: '"Number of samples in the municipality"',
    56: '"The municipal class is the mode of the samples; with few samples, uncertainty increases."',
    57: '"I have the F1, F2 and F3 scores (0–1)"',
    58: '"F1 – nutrient cycling"',
    59: '"F2 – nutrient storage"',
    60: '"F3 – nutrient supply"',
    61: '"IQS FertBio (soil quality index)"',
    63: '"Biochar"',
    64: None,
    65: '"Fills C, H/C, O/C and type with values reported in the papers."',
    66: '"Type"',
    67: '"Structural: wood, straw, husk. Nutrient-rich: manure, sludge — larger response in poor soils."',
    68: '"Dose (t/ha, dry basis)"',
    69: '"The field trials used for calibration applied 15–30 t/ha."',
    70: '"Supplier price (R$/t)"',
    71: '"Freight (R$/t)"',
    72: '"Application cost (R$/ha)"',
    73: '"Organic carbon (fraction)"',
    76: '"Life-cycle emissions (tCO₂e/t biochar)"',
    77: '"Lime savings (R$/ha/yr)"',
    78: '"Fertiliser savings (R$/ha/yr)"',
    79: '"Yield response"',
    80: '"Fertilisation management of the field"',
    81: '"Cropland with NPK fertilisation"',
    82: '"No fertilisation / degraded pasture"',
    83: '"Calibrated with Chagas et al. (2024) and Latawiec et al. (2019): with NPK, the biochar gain is much smaller."',
    84: '"Dose response (calibration)"',
    85: '"Reference dose of the trials (t/ha)"',
    86: '"Half-saturation dose (t/ha) — assumption"',
    87: 'f"Dose factor at {dose:g} t/ha: {fator_dose(dose, dose_ref, dose_meia):.2f} · "\n                   f"fertilisation factor: {fator_adubacao(adub, tipo):.1f}"',
    88: 'f"Use the soil-based suggested mean ({sugerida:.1%})"',
    89: '"Mean response (fraction)"',
    90: '"Between-field uncertainty (SD)"',
    91: '"Year-to-year variation"',
    92: '"Annual decay of the effect"',
    93: '"Chagas et al. (2024): without NPK, the gain fell from the 4th season and returned to control by the 7th."',
    94: '"Observed trials (fractions separated by commas)"',
    95: '"E.g. 0.05, 0.08, 0.03 — updates the prior by Bayesian inference."',
    96: '"Carbon"',
    97: None,
    98: '"Limits from Lin et al. (2025), Table 2."',
    99: '"Maximum H/Corg"',
    100: '"Maximum O/Corg"',
    101: '"custom range"',
    103: '"Price scenario (Table 3 of the GCB paper)"',
    104: '"Credit price (US$/tCO₂e)"',
    105: '"US$ per €"',
    106: '"Adjust to the current exchange rate."',
    108: '"Variation around the feasible price"',
    109: 'f"Simulated range: US$ {pc_min}–{pc_max}/tCO₂e"',
    110: '"Exchange rate (R$/US$)"',
    111: '"Certification and platform fees"',
    112: '"Probability that the credit is issued"',
    113: '"Year carbon revenue is received"',
    114: '"Permanence factor (check the methodology)"',
    115: '"Intercept a  (F = a − b·H/Corg)"',
    116: '"Slope b"',
    117: '"Adjustment per °C above 15 °C"',
    118: '"P2P loan (SEP)"',
    119: '"Financed share"',
    120: '"Annual effective cost"',
    121: '"Grace period (years, interest only)"',
    122: '"Total term (years)"',
    123: '"LGD (loss given default)"',
    124: '"Platform fee"',
    125: '"Simulation"',
    126: '"Horizon (years)"',
    127: '"Farmer discount rate"',
    128: '"Number of simulations"',
    129: '"Decision rule"',
    130: '"Yield gain alone must pay (carbon = bonus)"',
    131: '"Yield + discounted carbon"',
    132: '"Prudence discount on carbon"',
    133: '"Under the combined rule, carbon revenue is reduced by this factor."',
    134: '"Approval threshold for P(NPV>0)"',
    135: 'f"Ignored: \'{parte}\'"',
    136: '"Running Monte Carlo..."',
    137: '"How to use this app"',
    138: '"1. **My municipality:** choose a municipality in Paraná (PR) or Santa Catarina (SC) and see, in plain terms, how "\n        "much yield increases, how much carbon stays in the soil and whether the investment pays off.\\n"\n        "2. **PR and SC ranking:** compare all municipalities with Embrapa soil profiles.\\n"\n        "3. **Sidebar:** change crop, dose, biochar type, fertilisation, carbon price and loan terms. "\n        "All tabs update.\\n"\n        "4. The other tabs detail the financial analysis, the fund, the validation against the literature and the base paper."',
    139: '"My municipality"',
    140: '"PR and SC ranking"',
    141: '"Two benefits"',
    142: '"Operation summary"',
    143: '"Embedded credit and fund"',
    144: '"Validation (literature)"',
    145: '"Framework (GCB paper)"',
    146: '"NPV distribution"',
    147: '"Loan cash flow"',
    148: '"Sensitivity"',
    149: '"Soils (BDsolos)"',
    150: '"Data"',
    151: 'f"Operation APPROVED: P(viable under the rule) = {res[\'prob_decisao\']:.0%} ≥ {limiar:.0%} "\n                   f"({\'yield only\' if regra == \'produtividade\' else f\'yield + carbon with a {desconto_c:.0%} discount\'})."',
    153: 'f"Operation NOT approved: P(viable under the rule) = {res[\'prob_decisao\']:.0%} < {limiar:.0%} "\n                 f"({\'yield only\' if regra == \'produtividade\' else f\'yield + carbon with a {desconto_c:.0%} discount\'})."',
    154: 'f"Biochar not eligible under the {PADRAO_EN.get(res[\'padrao_carbono\'], res[\'padrao_carbono\'])} standard ({\'; \'.join(res[\'motivos_inelegivel\'])}): "\n                   f"carbon revenue set to zero. The carbon still stays in the soil: about "\n                   f"{res[\'incremento_c_solo_tha\']:.1f} t C/ha estimated, without generating credits."',
    155: '"P(NPV>0) without carbon"',
    156: '"P(NPV>0) with carbon"',
    157: '"Default probability"',
    158: '"Expected loss (% of principal)"',
    159: '"Upfront cost"',
    160: '"Net removal"',
    163: '"Mean response used"',
    164: 'f"± {res[\'resposta_desvio_usado\']:.1%} · soil health ×{res[\'fator_saude_solo\']:.2f}"',
    165: '"Mean investor multiple"',
    167: 'f"{res[\'n_perfis_solo\']} BDsolos profiles sampled · median pH used {res[\'ph_mediano_simulado\']:.2f} · "\n                f"biochar C {res[\'c_biocarvao_tha\']:.1f} t/ha vs. median native stock 0–20 cm "\n                f"{res[\'estoque_c_nativo_mediano_tha\']:.1f} t C/ha"',
    168: '"Assessment by municipality"',
    169: '"File perfis_bdsolos_0_20.csv not found."',
    170: '"State"',
    172: 'f"{m} ({contagem[m]} soil profile{\'s\' if contagem[m] > 1 else \'\'})"',
    173: 'f"Scenario: {cult_en}, {num(cenario.biocarvao.dose_t_ha, 1)} t/ha of biochar "\n                   f"({\'NPK-fertilised cropland\' if cenario.resposta.manejo_adubacao == \'completa\' else \'no fertilisation\'}), "\n                   f"carbon between US$ {num(cenario.carbono.preco_min_usd_t, 0)} and {num(cenario.carbono.preco_max_usd_t, 0)}/t. "\n                   "Change it in the sidebar."',
    174: '"Viable with the yield gain alone"',
    175: '"Viable"',
    176: '"#### Yield"',
    177: '"Increase in year 1"',
    182: '"In tonnes"',
    184: '"Mean gain per year"',
    185: 'f"over {cenario.simulacao.horizonte_anos} years, with a "\n                      f"{pctbr(cenario.resposta.decaimento_anual, 0)} annual decay"',
    186: '"#### Carbon in the soil"',
    187: '"Carbon that stays in the soil"',
    190: '"Increase of the soil C stock (0–20 cm)"',
    192: 'f"current stock {num(d[\'estoque_c_nativo_tha\'], 0)} t C/ha"',
    193: '"Carbon credit"',
    195: 'f"{PADRAO_EN.get(cenario.carbono.padrao, cenario.carbono.padrao)} standard, net of emissions"',
    196: '"none"',
    197: 'f"biochar outside the {PADRAO_EN.get(cenario.carbono.padrao, cenario.carbono.padrao)} standard"',
    198: '"#### Financial viability"',
    199: '"Chance of paying off with the yield gain alone"',
    201: '"Chance of paying off with yield + carbon"',
    203: '"Risk of not repaying the loan"',
    205: '"#### What this means"',
    206: 'f"In **{mun_m} ({uf_m})**, with {num(cenario.biocarvao.dose_t_ha, 1)} t/ha of biochar, "\n                 f"{cult_en} yield should rise by about **{num(d[\'aumento_pct_ano1\'], 1)}%** in the first year "\n                 f"(+{num(d[\'aumento_t_ha_ano1\'], 3)} t/ha), worth on average **{brl(d[\'ganho_r_ha_ano_medio\'])} per "\n                 f"hectare per year**. The biochar leaves about **{num(d[\'c_retido_tc_ha\'], 2)} t of carbon per hectare** "\n                 f"in the soil, {num(d[\'incremento_c_pct\'], 0)}% more than the current stock of the 0–20 cm layer. "',
    207: '"The yield gain alone already pays for the investment in most scenarios."',
    208: '"The yield gain alone does not pay for the investment, but together with the sale of carbon credits it does."',
    209: 'f"Under current conditions, the investment pays off in only {pctbr(d[\'prob_vpl_com_carbono\'], 0)} of "\n                      f"scenarios, below the {pctbr(cenario.simulacao.limiar_prob_vpl, 0)} threshold."',
    210: '"#### What would need to change"',
    211: 'f"- To pay off **without carbon**, the yield increase would need to be about "\n                     f"**{pctbr(d[\'resposta_necessaria_sem_carbono\'], 1)}**; the expected value here is {num(d[\'aumento_pct_ano1\'], 1)}%."',
    212: 'f"- With the expected yield gain, carbon would need to be worth about "\n                             f"**US$ {num(d[\'preco_carbono_equilibrio_usd\'], 0)}/tCO₂e** (median of the scenarios)."',
    213: '"- Try in the sidebar: unfertilised or degraded pasture areas, another reference biochar, "\n                         "biochar price, loan term and interest rate."',
    214: '"**Yield increase year by year**"',
    215: '"Year"',
    216: '"Yield increase (t/ha)"',
    217: 'f"**Municipality soil compared with {uf_m}**"',
    220: 'f"Soil classes in the profiles (Brazilian system): {classes_txt}. Sandy, carbon-poor soils tend to "\n                       "respond more to biochar."',
    221: 'f"Based on {d[\'n_perfis\']} BDsolos (Embrapa) profile(s), mostly from old soil surveys. "\n                   "The retained carbon depends on the biochar and the dose; what changes between "\n                   "municipalities is how much it adds to the soil stock. Yield response calibrated with "\n                   "Chagas et al. (2024) and Latawiec et al. (2019); see the Validation tab."',
    257: '"Tranched fund: investors and P2P in the senior quota, cooperative in the subordinated quota"',
    258: '"Portfolio of operations identical to the one simulated in the sidebar, with defaults correlated "\n               "through a common regional shock (climate and price)."',
    259: '"Operations in the portfolio"',
    260: '"Subordination (cooperative quota)"',
    261: '"Senior target return (p.a.)"',
    262: '"Fund costs (p.a. on net assets)"',
    263: '"Default correlation"',
    264: '"Carbon revenue assigned to the fund"',
    265: '"Share of the operations\' carbon credits assigned to the fund as credit enhancement."',
    266: '"Share of the senior quota raised via P2P/retail"',
    267: '"The operation has no financed amount: increase the financed share in the sidebar."',
    268: '"Fund net assets"',
    269: '"Senior quota"',
    270: 'f"P2P/retail: {brl(fr[\'senior_p2p_r\'])}"',
    271: '"Subordinated quota (cooperative)"',
    272: '"Portfolio default rate"',
    275: '"P(senior loss)"',
    277: '"Senior expected loss"',
    279: '"Median subordinated multiple"',
    282: '"P(subordinated loses capital)"',
    284: '"**How much the cooperative must subordinate to protect the senior quota**"',
    285: '"Not even 50% subordination brings the senior loss probability below 1%. "\n                     "Reduce operation risk (dose, term, target area) or assign carbon revenue to the fund."',
    286: 'f"Minimum subordination for at most a 1% senior loss probability: {pctbr(sub_min, 0)}."',
    287: '"In Brazil, retail investors may only buy senior FIDC quotas (CVM Resolution 175, "\n                   "Annex II, art. 13). The subordinated quota stays with the cooperative or qualified investors."',
    288: '"Origination package and embedded credit via agfintech"',
    289: '"Cooperative"',
    290: '"Cooperative tax ID (CNPJ)"',
    291: '"Pseudonymised farmer ID"',
    292: '"Rural Environmental Registry code (CAR)"',
    293: '"Biochar supplier"',
    294: '"Supplier tax ID (CNPJ)"',
    295: '"Municipality of the farm"',
    296: '"State of the farm"',
    303: '"Funding channel"',
    304: '"Embedded credit (agfintech)"',
    305: '"P2P via SEP"',
    306: '"Tranched fund"',
    307: None,
    308: '"The farmer gave explicit consent for these purposes (Brazilian data protection law, LGPD)"',
    309: '"Tick the farmer\'s consent to generate the package."',
    310: '"Package with issues: "',
    312: 'f"Valid package · SHA-256 hash {pacote[\'integridade\'][\'hash\'][:16]}…"',
    313: '"Download origination package (JSON)"',
    314: '"View package"',
    315: '"**Request embedded credit**"',
    316: '"Agfintech API URL"',
    317: '"Empty = simulated mode with a local policy."',
    318: '"Access token"',
    319: '"Credit policy of the simulated mode"',
    320: '"Maximum accepted default probability"',
    321: '"Minimum viability under the rule"',
    322: '"Base rate (p.a.)"',
    323: '"Spread per unit of default probability"',
    324: '"Limit per hectare (R$)"',
    325: '"Send to agfintech"',
    326: 'f"Decision: {decisao.get(\'status\')} ({decisao.get(\'modo\', \'api\')})"',
    327: 'f"API call failed: {erro}"',
    328: '"Download API specification (OpenAPI 3.1)"',
    329: '"How much of the cost each benefit pays"',
    330: '"Total cost (present value)"',
    331: '"Yield + input savings"',
    332: 'f"covers {pctbr(res[\'cobertura_agro_mediana\'], 0)} of the cost"',
    333: 'f"covers {pctbr(res[\'cobertura_carbono_mediana\'], 0)} of the cost"',
    334: '"Both combined"',
    335: 'f"{pctbr(res[\'cobertura_agro_mediana\'] + res[\'cobertura_carbono_mediana\'], 0)} of the cost"',
    336: '"Component"',
    337: '"1. Cost"',
    338: '"2. Yield increase"',
    339: '"3. Input savings"',
    340: '"4. Carbon"',
    341: '"5. NPV"',
    342: '"R$ (median)"',
    343: '"Median present values. The median NPV is not the exact sum of the medians of the components."',
    344: '"When the project pays off"',
    349: 'f"- The **yield gain alone** pays for the project in **{pctbr(so_prod, 0)}** of simulations.\\n"\n        f"- **Carbon alone** pays in **{pctbr(so_c, 0)}**.\\n"\n        f"- **Only both together** make it viable in **{pctbr(cls[\'Só as duas juntas pagam\'], 0)}**: this is where carbon "\n        f"turns an unviable case into a viable one.\\n"\n        f"- Not viable even with both: **{pctbr(cls[\'Inviável\'], 0)}**."',
    350: '"Break-even points"',
    351: '"Break-even carbon price"',
    353: '"with the expected yield gain"',
    354: '"Carbon price with no yield gain"',
    356: '"input savings only"',
    357: '"Yield increase needed without carbon"',
    359: 'f"expected: {pctbr(res[\'resposta_media_usada\'], 1)}"',
    360: '"Yield increase needed with carbon"',
    362: '"Viability map: carbon price × yield increase"',
    364: '"Carbon price (US$/tCO₂e)"',
    366: '"Mean yield increase"',
    368: '"P(NPV>0)"',
    370: '"Increase"',
    371: 'f"Each cell uses the same simulations (climate, crop prices, credit issuance and between-field "\n               f"variation), changing only the carbon price and the expected mean increase. "\n               f"Current point: increase of {pctbr(res[\'resposta_media_usada\'], 1)} and carbon between US$ {pc_min} and {pc_max}/t."',
    372: '"Where biochar performs best in Paraná and Santa Catarina"',
    373: '"States"',
    374: '"Minimum profiles per municipality"',
    375: '"Sort by"',
    376: '"Combined index (yield + carbon)"',
    377: '"Increase of the soil C stock (%)"',
    378: '"Chance of paying off with carbon"',
    379: '"Chance of paying off without carbon"',
    380: '"No municipality has enough profiles for the selected filters."',
    381: 'f"**{top[\'municipio\']} ({top[\'uf\']})** leads on this criterion: yield "\n                f"+{top[\'aumento_pct_ano1\']:.1f}% (+{top[\'aumento_t_ha_ano1\']:.3f} t/ha in year 1), soil C stock "\n                f"+{top[\'incremento_c_pct\']:.1f}% and a {top[\'prob_vpl_com_carbono\']:.0%} chance of paying off with carbon. "\n                f"{len(ranking)} municipalities evaluated. To see one municipality in detail, use the **My municipality** tab."',
    384: 'f"Colour: position on the chosen criterion (green = best). Size: number of profiles. "\n                           f"{len(geo)} of {len(ranking)} municipalities have coordinates in the profiles."',
    385: '"Verdict"',
    386: '"Yield (+% year 1)"',
    387: '"Yield (+t/ha year 1)"',
    388: '"Mean gain (R$/ha/yr)"',
    389: '"C retained in soil (t C/ha)"',
    390: '"Soil C stock (+%)"',
    391: '"Credit (tCO₂e/ha)"',
    392: '"Pays off without carbon"',
    393: '"Pays off with carbon"',
    394: '"Soil profiles"',
    395: '"Predominant soil"',
    396: '"Clay (%)"',
    397: '"Soil organic C (g/kg)"',
    398: '"Download ranking (CSV)"',
    399: '"Uses the sidebar parameters (biochar, crop, loan, carbon, liming correction). "\n                       "C increase = C applied by the biochar ÷ native 0–20 cm stock. BDsolos profiles are old and "\n                       "few in several municipalities: use the ranking to prioritise where to sample and run "\n                       "trials, not as a final result."',
    400: '"NPV (R$ thousand)"',
    401: '"Without carbon"',
    402: '"With carbon"',
    403: 'f"NPV without carbon — P10 {brl(p[\'vpl_sem_carbono_p10_p50_p90\'][0])}, "\n        f"P50 {brl(p[\'vpl_sem_carbono_p10_p50_p90\'][1])}, P90 {brl(p[\'vpl_sem_carbono_p10_p50_p90\'][2])}  \\n"\n        f"NPV with carbon — P10 {brl(p[\'vpl_com_carbono_p10_p50_p90\'][0])}, "\n        f"P50 {brl(p[\'vpl_com_carbono_p10_p50_p90\'][1])}, P90 {brl(p[\'vpl_com_carbono_p10_p50_p90\'][2])}"',
    404: '"Instalment (R$)"',
    405: 'f"Principal financed via P2P: **{brl(res[\'principal_p2p_r\'])}** · "\n             f"median minimum DSCR: **{res[\'dscr_min_mediano\']:.2f}**"',
    406: '"Max. carbon price (US$/t)"',
    407: '"Dose (t/ha)"',
    408: '"P2P annual effective cost"',
    409: '"Biochar price (R$/t)"',
    410: '"Term (years)"',
    411: '"Parameter"',
    412: '"Run sensitivity"',
    413: '"**0–20 cm layer of the selected profiles** (P10, median, P90)"',
    414: 'f"{len(geo)} of {len(perfis_sel)} profiles have coordinates. Bulk density measured in "\n                   f"{perfis_sel[\'ds_medida\'].mean():.0%} of profiles; the rest estimated by pedotransfer."',
    415: '"Description (PDF)"',
    416: '"Turn on BDsolos in the sidebar to see the profiles."',
    417: '"Download simulations (CSV)"',
}
# Segmentos que pertencem aos blocos reescritos (validação e framework) ou que são chaves internas:
IGNORAR = set(range(222, 257)) | {6, 7, 8, 27, 74, 75, 102, 107, 152, 161, 162, 166, 171, 178, 179, 180, 181, 183,
                                   188, 189, 191, 194, 200, 202, 204, 218, 219, 225, 227, 230, 231, 232, 233, 234,
                                   273, 274, 276, 278, 280, 281, 283, 297, 298, 299, 300, 301, 302, 311, 345, 346,
                                   347, 348, 352, 355, 358, 361, 363, 365, 367, 369, 382, 383}


def gerar():
    src = (AQUI / "app.py").read_text(encoding="utf-8")
    segs = extrair_segmentos(src)
    if len(segs) != 418:
        sys.exit(f"app.py mudou ({len(segs)} textos em vez de 418): revise os índices de TRAD antes de gerar.")
    out = src
    for velho, novo in BLOCOS:
        n = out.count(velho)
        if n != 1:
            sys.exit(f"Bloco encontrado {n} vezes (esperado 1): {velho[:70]!r}")
        out = out.replace(velho, novo)
    ini = out.index(BLOCO_VALIDACAO_INI)
    fim = out.index(BLOCO_VALIDACAO_FIM)
    out = out[:ini] + BLOCO_VALIDACAO_EN + out[fim:]

    pares = [(segs[i], en) for i, en in TRAD.items() if en is not None]
    pares.sort(key=lambda p: -len(p[0]))
    faltando = []
    for pt, en in pares:
        if pt not in out:
            faltando.append(pt[:60])
            continue
        out = out.replace(pt, en)
    if faltando:
        sys.exit("Textos não encontrados:\n  " + "\n  ".join(faltando))
    sem_traducao = [i for i in range(len(segs)) if i not in TRAD and i not in IGNORAR]
    if sem_traducao:
        sys.exit(f"Textos sem tradução definida: {sem_traducao}")
    (AQUI / "app_en.py").write_text(out, encoding="utf-8")
    compile(out, "app_en.py", "exec")
    print("app_en.py gerado.")


if __name__ == "__main__":
    gerar()
