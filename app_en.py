"""
BioCrédito Agro — Streamlit interface (English version, generated from app.py by gerar_app_en.py).

Run locally:   streamlit run app_en.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from bdsolos import carregar_perfis, filtrar, resumo as resumo_perfis
from regioes import avaliar_municipios, cor_por_valor, detalhar_municipio
from aba_mercados import ROTULO_MERCADOS_EN as ROTULO_MERCADOS, render_mercados_en as render_mercados
from aba_brasil import ROTULO_BRASIL_EN as ROTULO_BRASIL, render_brasil_en as render_brasil
from aba_inicio import ROTULO_INICIO_EN as ROTULO_INICIO, render_inicio_en as render_inicio
from abas import ROTULO_TECNICO_EN as ROTULO_TECNICO, criar_abas
from fundo import ParametrosFundo, simular_fundo, curva_subordinacao, subordinacao_minima
from validacao import (PRESETS_BIOCARVAO, REFERENCIAS, validar_produtividade, validar_carbono,
                       calibrar_fatores_adubacao, elegibilidade_presets, FAIXAS_LITERATURA, PRECOS_VIAVEIS_ETS,
                       FIGURA1_CRITERIOS, FIGURA2_FERRAMENTAS, SBCE_FIGURA3)
from i18n_en import *  # noqa: F401,F403  (English display labels)
from originacao import (MetadadosOriginacao, ClienteAgfintech, PoliticaCreditoSimulada, gerar_pacote,
                        validar_pacote, FINALIDADES, CANAIS)

from simulador import (
    Cenario, ParametrosSolo, ParametrosBiocarvao, ParametrosCultura, ParametrosResposta,
    ParametrosCarbono, ParametrosEmprestimo, ParametrosSimulacao,
    ParametrosSaudeSolo, CLASSES_SAUDE, carregar_municipios,
    simular, analise_sensibilidade, sugerir_resposta_media,
    mapa_viabilidade, CLASSES_VIABILIDADE, CULTURAS, PADROES, fator_dose, fator_adubacao,
)

st.set_page_config(page_title="BioCrédito Agro — Simulator", layout="wide")
st.title("BioCrédito Agro — simulator of P2P-financed biochar")
st.caption(
    "Monte Carlo simulation of the agronomic, carbon and financial modules. "
    "Default values are illustrative: calibrate with soil reports, field trials and the chosen certification methodology."
)


@st.cache_data(show_spinner="Loading BDsolos profiles...")
def carregar_perfis_app():
    caminho = Path(__file__).parent / "perfis_bdsolos_0_20.csv"
    return carregar_perfis(str(caminho)) if caminho.exists() else None


@st.cache_data(show_spinner="Evaluating municipalities...")
def avaliar_municipios_app(cen_dict: dict, ufs: tuple, min_perfis: int):
    return avaliar_municipios(cenario, carregar_perfis_app(), ufs=ufs, min_perfis=min_perfis)


@st.cache_data(show_spinner="Evaluating the municipality...")
def detalhar_municipio_app(cen_dict: dict, uf: str, municipio: str):
    d = detalhar_municipio(cenario, carregar_perfis_app(), uf, municipio)
    d.pop("resultado", None)
    return d


def num(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}"


def pctbr(x: float, casas: int = 0) -> str:
    return num(100 * x, casas) + "%"


def sacas(t_ha: float) -> str:
    return f"{num(t_ha * 1000 / 60, 1)} bags of 60 kg/ha"


def brl(x: float) -> str:
    return f"R$ {x:,.0f}"


# --------------------------------------------------------------------------- entradas
with st.sidebar:
    st.header("Field and crop")
    cultura = st.selectbox("Crop", list(CULTURAS), format_func=lambda k: CROP_EN.get(k, k))
    ref = CULTURAS[cultura]
    st.caption("Approximate reference values: replace with the cooperative's, CONAB or CEPEA data.")
    area = st.number_input("Area (ha)", 1.0, 10_000.0, 50.0, step=5.0)
    y0 = st.number_input("Baseline yield Y₀ (t/ha)", 0.1, 200.0, ref["produtividade_t_ha"], step=0.1,
                         key=f"y0_{cultura}")
    p_cult = st.number_input("Crop price (R$/t)", 10.0, 50_000.0, ref["preco_r_t"], step=50.0,
                             key=f"preco_{cultura}")
    p_cv = st.slider("Price volatility (CV)", 0.0, 0.5, ref["cv_preco"], 0.01, key=f"cv_{cultura}")
    margem = st.number_input("Baseline margin without biochar (R$/ha/yr)", 0.0, 20_000.0, ref["margem_r_ha"],
                             step=100.0, key=f"margem_{cultura}")
    fator_cult = st.slider("Crop response factor to biochar", 0.0, 2.0, ref["fator_resposta"], 0.05,
                           key=f"fator_{cultura}",
                           help="Multiplies the relative yield increase. Keep it at 1.0 until field trials of this crop indicate another value.")
    frac_margem = st.slider("Share of margin available for debt service", 0.1, 1.0, 0.6, 0.05)
    p_quebra = st.slider("Annual probability of a climate-driven crop loss (ZARC)", 0.0, 0.6, 0.15, 0.01)
    perda_quebra = st.slider("Loss when it occurs", 0.0, 1.0, 0.35, 0.05)

    st.header("Soil profiles (Embrapa BDsolos)")
    usar_bdsolos = st.checkbox("Sample real BDsolos profiles", value=True,
                               help="Each simulation draws one profile (0–20 cm layer) from the filtered region.")
    perfis_sel = None
    if usar_bdsolos:
        perfis_todos = carregar_perfis_app()
        if perfis_todos is None:
            st.warning("File perfis_bdsolos_0_20.csv not found. Generate it with: "
                       "python bdsolos.py bd_solos_para_redape.csv perfis_bdsolos_0_20.csv")
        else:
            ufs = sorted(perfis_todos["uf"].unique())
            uf_b = st.selectbox("State", ufs, index=ufs.index("PR") if "PR" in ufs else 0)
            muns = ["(todos)"] + sorted(perfis_todos.loc[perfis_todos["uf"] == uf_b, "municipio"].unique())
            mun_b = st.selectbox("Municipality", muns)
            usar_raio = st.checkbox("Filter by radius around coordinates", value=False)
            lat_b = lon_b = raio_b = None
            if usar_raio:
                lat_b = st.number_input("Latitude (decimal degrees)", -34.0, 6.0, -25.0, step=0.01)
                lon_b = st.number_input("Longitude (decimal degrees)", -74.0, -28.0, -50.2, step=0.01)
                raio_b = st.slider("Radius (km)", 5, 300, 50, 5)
            classes = sorted(perfis_todos["classe_n1"].dropna().unique())
            classes_b = st.multiselect("Soil classes (level 1, Brazilian system)", classes)
            so_agri = st.checkbox("Only profiles with recorded agricultural use", value=False)
            perfis_sel = filtrar(perfis_todos, uf=None if usar_raio else uf_b,
                                 municipio=None if (mun_b == "(todos)" or usar_raio) else mun_b,
                                 lat=lat_b, lon=lon_b, raio_km=raio_b,
                                 classes_n1=classes_b or None, so_uso_agricola=so_agri)
            st.caption(f"{len(perfis_sel)} profiles selected")
            if len(perfis_sel) < 5:
                st.warning("Few profiles: widen the filter (whole state or larger radius).")

    st.header("Soil")
    st.caption("With BDsolos on, the pH and base saturation below only fill gaps in the profiles.")
    ph = st.slider("pH (water)", 4.0, 7.5, 5.4, 0.1)
    v = st.slider("Base saturation, V (%)", 10.0, 90.0, 50.0, 1.0)
    t_solo = st.slider("Mean soil temperature (°C)", 10.0, 30.0, 21.0, 0.5)
    corrigir = st.checkbox("Limed cropland (apply minimum pH and base saturation)", value=True,
                           help="BDsolos profiles mostly come from old surveys under native vegetation or pasture. In limed cropland, "
                                "current pH and base saturation are higher, and the response to biochar tends to be smaller.")
    ph_min = st.slider("Minimum pH in cropland", 4.5, 6.5, 5.5, 0.1) if corrigir else None
    v_min = st.slider("Minimum base saturation in cropland (%)", 30.0, 80.0, 60.0, 1.0) if corrigir else None

    st.header("Soil health (Embrapa)")
    st.caption("Soil Health BR platform / BioAS: saudedosolo.embrapa.gov.br/plataforma-publica")
    fonte_saude = st.radio("Source", ["nenhuma", "municipio", "laudo"],
                           format_func={"nenhuma": "Do not use", "municipio": "Municipality class",
                                        "laudo": "BioAS report of the field"}.get)
    saude_kw = {"fonte": fonte_saude}
    if fonte_saude == "municipio":
        arq = st.file_uploader("Municipality CSV (uf, municipio, classe_saude, n_amostras)", type="csv")
        if arq is not None:
            try:
                mun = carregar_municipios(arq)
                uf_sel = st.selectbox("State", sorted(mun["uf"].unique()))
                sub = mun[mun["uf"] == uf_sel]
                mun_sel = st.selectbox("Municipality", sorted(sub["municipio"].unique()))
                linha = sub[sub["municipio"] == mun_sel].iloc[0]
                saude_kw.update(classe_saude=linha["classe_saude"], n_amostras_municipio=int(linha["n_amostras"]))
                st.caption(f"Class: {SAUDE_EN.get(linha['classe_saude'], linha['classe_saude'])} · {int(linha['n_amostras'])} samples")
            except ValueError as erro:
                st.error(str(erro))
        else:
            saude_kw["classe_saude"] = st.selectbox("Predominant class in the municipality", CLASSES_SAUDE, index=2, format_func=lambda k: SAUDE_EN.get(k, k))
            saude_kw["n_amostras_municipio"] = st.number_input("Number of samples in the municipality", 0, 100_000, 10)
        st.caption("The municipal class is the mode of the samples; with few samples, uncertainty increases.")
    elif fonte_saude == "laudo":
        usar_funcoes = st.checkbox("I have the F1, F2 and F3 scores (0–1)", value=True)
        if usar_funcoes:
            saude_kw["f1_ciclar"] = st.slider("F1 – nutrient cycling", 0.0, 1.0, 0.6, 0.01)
            saude_kw["f2_armazenar"] = st.slider("F2 – nutrient storage", 0.0, 1.0, 0.5, 0.01)
            saude_kw["f3_suprir"] = st.slider("F3 – nutrient supply", 0.0, 1.0, 0.6, 0.01)
            saude_kw["iqs_fertbio"] = st.slider("IQS FertBio (soil quality index)", 0.0, 1.0, 0.6, 0.01)
        else:
            saude_kw["classe_saude"] = st.selectbox("Soil condition in the report", CLASSES_SAUDE, index=2, format_func=lambda k: SAUDE_EN.get(k, k))

    st.header("Biochar")
    preset_nome = st.selectbox("Reference biochar (literature)", ["personalizado"] + list(PRESETS_BIOCARVAO),
                               format_func=lambda k: PRESET_EN.get(k, k),
                               help="Fills C, H/C, O/C and type with values reported in the papers.")
    pr_bc = PRESETS_BIOCARVAO.get(preset_nome, {"c_org_frac": 0.70, "h_c_org": 0.40, "o_c_org": 0.15,
                                                "tipo": "estrutural", "nota": ""})
    if pr_bc.get("nota"):
        st.caption(PRESET_NOTE_EN.get(preset_nome, pr_bc["nota"]))
    tipo = st.selectbox("Type", ["estrutural", "nutriente"], index=["estrutural", "nutriente"].index(pr_bc["tipo"]), format_func=lambda k: TIPO_EN.get(k, k),
                        key=f"tipo_{preset_nome}",
                        help="Structural: wood, straw, husk. Nutrient-rich: manure, sludge — larger response in poor soils.")
    dose = st.number_input("Dose (t/ha, dry basis)", 0.1, 50.0, 2.0, step=0.5,
                           help="The field trials used for calibration applied 15–30 t/ha.")
    preco_bc = st.number_input("Supplier price (R$/t)", 0.0, 10_000.0, 1200.0, step=50.0)
    frete = st.number_input("Freight (R$/t)", 0.0, 2_000.0, 150.0, step=10.0)
    aplic = st.number_input("Application cost (R$/ha)", 0.0, 2_000.0, 120.0, step=10.0)
    c_org = st.slider("Organic carbon (fraction)", 0.05, 0.95, float(pr_bc["c_org_frac"]), 0.01, key=f"corg_{preset_nome}")
    hc = st.slider("H/Corg (molar)", 0.05, 2.0, float(pr_bc["h_c_org"]), 0.01, key=f"hc_{preset_nome}")
    oc = st.slider("O/Corg (molar)", 0.0, 3.5, float(pr_bc["o_c_org"]), 0.01, key=f"oc_{preset_nome}")
    e_acv = st.number_input("Life-cycle emissions (tCO₂e/t biochar)", 0.0, 2.0, 0.25, step=0.05)
    s_cal = st.number_input("Lime savings (R$/ha/yr)", 0.0, 2_000.0, 80.0, step=10.0)
    s_fert = st.number_input("Fertiliser savings (R$/ha/yr)", 0.0, 2_000.0, 60.0, step=10.0)

    st.header("Yield response")
    adub = st.radio("Fertilisation management of the field", ["completa", "sem_adubacao"],
                    format_func={"completa": "Cropland with NPK fertilisation", "sem_adubacao": "No fertilisation / degraded pasture"}.get,
                    help="Calibrated with Chagas et al. (2024) and Latawiec et al. (2019): with NPK, the biochar gain is much smaller.")
    with st.expander("Dose response (calibration)"):
        dose_ref = st.number_input("Reference dose of the trials (t/ha)", 1.0, 50.0, 15.0, step=1.0)
        dose_meia = st.number_input("Half-saturation dose (t/ha) — assumption", 0.5, 50.0, 5.0, step=0.5)
        st.caption(f"Dose factor at {dose:g} t/ha: {fator_dose(dose, dose_ref, dose_meia):.2f} · "
                   f"fertilisation factor: {fator_adubacao(adub, tipo):.1f}")
    solo_tmp = ParametrosSolo(ph_agua=ph, v_pct=v)
    sugerida = (sugerir_resposta_media(solo_tmp, ParametrosBiocarvao(tipo=tipo)) * fator_dose(dose, dose_ref, dose_meia)
                * fator_adubacao(adub, tipo))
    usar_sugerida = st.checkbox(f"Use the soil-based suggested mean ({sugerida:.1%})", value=True)
    r_media = None if usar_sugerida else st.slider("Mean response (fraction)", -0.2, 0.8, 0.10, 0.01)
    r_desvio = st.slider("Between-field uncertainty (SD)", 0.0, 0.4, 0.10, 0.01)
    r_ruido = st.slider("Year-to-year variation", 0.0, 0.3, 0.05, 0.01)
    r_decai = st.slider("Annual decay of the effect", 0.0, 0.5, 0.10, 0.01,
                        help="Chagas et al. (2024): without NPK, the gain fell from the 4th season and returned to control by the 7th.")
    ensaios_txt = st.text_input("Observed trials (fractions separated by commas)", "",
                                help="E.g. 0.05, 0.08, 0.03 — updates the prior by Bayesian inference.")

    st.header("Carbon")
    padrao = st.selectbox("Certification standard", list(PADROES), format_func=lambda k: PADRAO_EN.get(k, k), help="Limits from Lin et al. (2025), Table 2.")
    st.caption(PADRAO_NOTE_EN.get(padrao, PADROES[padrao]["nota"]))
    hc_max_p, oc_max_p = 0.7, 0.4
    if padrao == "personalizado":
        hc_max_p = st.number_input("Maximum H/Corg", 0.1, 2.0, 0.7, step=0.01)
        oc_max_p = st.number_input("Maximum O/Corg", 0.05, 3.5, 0.4, step=0.01)
    opcoes_ets = ["custom range"] + [f"{e['ets']} {PAIS_EN.get(e['pais'], e['pais'])}: {e['preco']} {e['moeda']}/t" for e in PRECOS_VIAVEIS_ETS]
    cen_ets = st.selectbox("Price scenario (Table 3 of the GCB paper)", opcoes_ets)
    if cen_ets == "custom range":
        pc_min, pc_max = st.slider("Credit price (US$/tCO₂e)", 0, 500, (100, 200), 5)
    else:
        e_sel = PRECOS_VIAVEIS_ETS[opcoes_ets.index(cen_ets) - 1]
        usd_eur = st.number_input("US$ per €", 0.5, 2.0, 1.10, step=0.01, help="Adjust to the current exchange rate.") \
            if e_sel["moeda"] == "EUR" else 1.0
        p_usd = e_sel["preco"] * usd_eur
        var = st.slider("Variation around the feasible price", 0.0, 0.5, 0.2, 0.05)
        pc_min, pc_max = round(p_usd * (1 - var)), round(p_usd * (1 + var))
        st.caption(f"Simulated range: US$ {pc_min}–{pc_max}/tCO₂e")
    cambio = st.number_input("Exchange rate (R$/US$)", 1.0, 15.0, 5.40, step=0.05)
    taxas = st.slider("Certification and platform fees", 0.0, 0.6, 0.25, 0.01)
    p_emissao = st.slider("Probability that the credit is issued", 0.0, 1.0, 0.85, 0.05)
    ano_c = st.number_input("Year carbon revenue is received", 0, 15, 1)
    with st.expander("Permanence factor (check the methodology)"):
        a_perm = st.number_input("Intercept a  (F = a − b·H/Corg)", 0.0, 2.0, 1.13, step=0.01)
        b_perm = st.number_input("Slope b", 0.0, 2.0, 0.46, step=0.01)
        aj_temp = st.number_input("Adjustment per °C above 15 °C", -0.05, 0.05, 0.0, step=0.005, format="%.3f")

    st.header("P2P loan (SEP)")
    frac_fin = st.slider("Financed share", 0.0, 1.0, 1.0, 0.05)
    taxa = st.slider("Annual effective cost", 0.0, 0.6, 0.18, 0.01)
    carencia = st.number_input("Grace period (years, interest only)", 0, 5, 1)
    prazo = st.number_input("Total term (years)", 1, 15, 6)
    lgd = st.slider("LGD (loss given default)", 0.0, 1.0, 0.45, 0.05)
    tarifa = st.slider("Platform fee", 0.0, 0.1, 0.03, 0.005)

    st.header("Simulation")
    horizonte = st.number_input("Horizon (years)", 1, 20, 8)
    desconto = st.slider("Farmer discount rate", 0.0, 0.4, 0.12, 0.01)
    n_sim = st.select_slider("Number of simulations", [1_000, 5_000, 10_000, 20_000, 50_000], 10_000)
    regra = st.radio("Decision rule", ["produtividade", "combinada"],
                     format_func={"produtividade": "Yield gain alone must pay (carbon = bonus)",
                                  "combinada": "Yield + discounted carbon"}.get)
    desconto_c = st.slider("Prudence discount on carbon", 0.0, 0.9, 0.30, 0.05,
                           help="Under the combined rule, carbon revenue is reduced by this factor.") \
        if regra == "combinada" else 0.30
    limiar = st.slider("Approval threshold for P(NPV>0)", 0.5, 0.95, 0.70, 0.05)


def parse_ensaios(txt: str) -> list[float]:
    out = []
    for parte in txt.replace(";", ",").split(","):
        parte = parte.strip()
        if parte:
            try:
                out.append(float(parte))
            except ValueError:
                st.sidebar.warning(f"Ignored: '{parte}'")
    return out


cenario = Cenario(
    solo=ParametrosSolo(ph_agua=ph, v_pct=v, temperatura_solo_c=t_solo,
                        ph_min_manejo=ph_min, v_min_manejo=v_min),
    saude=ParametrosSaudeSolo(**saude_kw),
    biocarvao=ParametrosBiocarvao(dose_t_ha=dose, preco_r_t=preco_bc, frete_r_t=frete, c_org_frac=c_org,
                                  h_c_org=hc, o_c_org=oc, tipo=tipo, e_acv_tco2e_t=e_acv),
    cultura=ParametrosCultura(cultura=cultura, fator_resposta_cultura=fator_cult,
                              area_ha=area, produtividade_base_t_ha=y0, preco_cultura_r_t=p_cult,
                              preco_cultura_cv=p_cv, margem_base_r_ha=margem,
                              frac_margem_comprometivel=frac_margem, custo_aplicacao_r_ha=aplic,
                              economia_calcario_r_ha_ano=s_cal, economia_fert_r_ha_ano=s_fert,
                              prob_quebra_safra=p_quebra, perda_quebra_frac=perda_quebra),
    resposta=ParametrosResposta(media=r_media, desvio=r_desvio, ruido_anual=r_ruido,
                                decaimento_anual=r_decai, ensaios_observados=parse_ensaios(ensaios_txt),
                                manejo_adubacao=adub, dose_referencia_t_ha=dose_ref, dose_meia_saturacao_t_ha=dose_meia),
    carbono=ParametrosCarbono(preco_min_usd_t=pc_min, preco_max_usd_t=max(pc_max, pc_min + 1e-6),
                              cambio_r_usd=cambio, taxas_frac=taxas, prob_emissao=p_emissao,
                              ano_recebimento=int(ano_c), perm_intercepto=a_perm, perm_inclinacao=b_perm,
                              perm_ajuste_temp_por_c=aj_temp, padrao=padrao, h_c_max=hc_max_p, o_c_max=oc_max_p),
    emprestimo=ParametrosEmprestimo(frac_financiada=frac_fin, taxa_anual=taxa, carencia_anos=int(carencia),
                                    prazo_anos=int(prazo), lgd=lgd, tarifa_plataforma_frac=tarifa),
    simulacao=ParametrosSimulacao(horizonte_anos=int(horizonte), taxa_desconto_produtor=desconto,
                                  n_simulacoes=int(n_sim), regra_decisao=regra,
                                  desconto_carbono_decisao=desconto_c,
                                  limiar_prob_vpl=limiar),
)


@st.cache_data(show_spinner="Running Monte Carlo...")
def rodar(cen_dict: dict, perfis: pd.DataFrame | None):
    # cache por dicionário de parâmetros + perfis filtrados
    return simular(cenario, perfis)


resultado = rodar(cenario.to_dict(), perfis_sel)
res, df = resultado["resumo"], resultado["simulacoes"]

with st.expander("How to use this app", expanded=False):
    st.markdown(
        "1. **My municipality:** choose a municipality in Paraná (PR) or Santa Catarina (SC) and see, in plain terms, how "
        "much yield increases, how much carbon stays in the soil and whether the investment pays off.\n"
        "2. **PR and SC ranking** (under Technical analyses): compare all municipalities with Embrapa soil profiles.\n"
        "3. **Sidebar:** change crop, dose, biochar type, fertilisation, carbon price and loan terms. "
        "All tabs update.\n"
        "4. The **Technical analyses** tab groups the ranking, the validation against the literature, the base paper, the sensitivity analysis and the data.")

aba_ini, aba_mun, aba_r, aba_br, aba_v, aba_mk, aba_res, aba_f, aba_val, aba_gcb, aba1, aba2, aba3, aba4, aba5 = criar_abas(
    st, [ROTULO_INICIO, "My municipality", "PR and SC ranking", ROTULO_BRASIL, "Two benefits", ROTULO_MERCADOS, "Operation summary", "Embedded credit and fund",
     "Validation (literature)", "Framework (GCB paper)", "NPV distribution", "Loan cash flow",
     "Sensitivity", "Soils (BDsolos)", "Data"], ROTULO_TECNICO)

with aba_res:
    # --------------------------------------------------------------------------- resultado
    if res["aprovado"]:
        st.success(f"Operation APPROVED: P(viable under the rule) = {res['prob_decisao']:.0%} ≥ {limiar:.0%} "
                   f"({'yield only' if regra == 'produtividade' else f'yield + carbon with a {desconto_c:.0%} discount'}).")
    else:
        st.error(f"Operation NOT approved: P(viable under the rule) = {res['prob_decisao']:.0%} < {limiar:.0%} "
                 f"({'yield only' if regra == 'produtividade' else f'yield + carbon with a {desconto_c:.0%} discount'}).")

    if not res["biocarvao_elegivel"]:
        st.warning(f"Biochar not eligible under the {PADRAO_EN.get(res['padrao_carbono'], res['padrao_carbono'])} standard ({'; '.join(res['motivos_inelegivel'])}): "
                   f"carbon revenue set to zero. The carbon still stays in the soil: about "
                   f"{res['incremento_c_solo_tha']:.1f} t C/ha estimated, without generating credits.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P(NPV>0) without carbon", f"{res['prob_vpl_pos_sem_carbono']:.0%}")
    c2.metric("P(NPV>0) with carbon", f"{res['prob_vpl_pos_com_carbono']:.0%}")
    c3.metric("Default probability", f"{res['prob_inadimplencia']:.0%}")
    c4.metric("Expected loss (% of principal)", f"{res['perda_esperada_pct_principal']:.1%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Upfront cost", brl(res["custo_inicial_r"]))
    c6.metric("Net removal", f"{res['remocao_liquida_tco2e']:,.0f} tCO₂e",
              f"{res['remocao_tco2e_por_ha']:.2f} t/ha", delta_color="off")
    c7.metric("Mean response used", f"{res['resposta_media_usada']:.1%}",
              f"± {res['resposta_desvio_usado']:.1%} · soil health ×{res['fator_saude_solo']:.2f}",
              delta_color="off")
    c8.metric("Mean investor multiple", f"{res['multiplo_investidor_medio']:.2f}×")

    if res["n_perfis_solo"]:
        st.info(f"{res['n_perfis_solo']} BDsolos profiles sampled · median pH used {res['ph_mediano_simulado']:.2f} · "
                f"biochar C {res['c_biocarvao_tha']:.1f} t/ha vs. median native stock 0–20 cm "
                f"{res['estoque_c_nativo_mediano_tha']:.1f} t C/ha")


with aba_mun:
    st.subheader("Assessment by municipality")
    perfis_m = carregar_perfis_app()
    if perfis_m is None:
        st.warning("File perfis_bdsolos_0_20.csv not found.")
    else:
        mc1, mc2 = st.columns([1, 3])
        uf_m = mc1.selectbox("State", ["PR", "SC"], key="uf_mun")
        contagem = perfis_m[perfis_m["uf"] == uf_m].groupby("municipio").size().sort_index()
        mun_m = mc2.selectbox("Municipality", list(contagem.index),
                              format_func=lambda m: f"{m} ({contagem[m]} soil profile{'s' if contagem[m] > 1 else ''})",
                              key="mun_mun")
        d = municipio_en(detalhar_municipio_app(cenario.to_dict(), uf_m, mun_m))
        cult = cenario.cultura.cultura
        cult_en = CROP_EN.get(cult, cult)
        st.caption(f"Scenario: {cult_en}, {num(cenario.biocarvao.dose_t_ha, 1)} t/ha of biochar "
                   f"({'NPK-fertilised cropland' if cenario.resposta.manejo_adubacao == 'completa' else 'no fertilisation'}), "
                   f"carbon between US$ {num(cenario.carbono.preco_min_usd_t, 0)} and {num(cenario.carbono.preco_max_usd_t, 0)}/t. "
                   "Change it in the sidebar.")

        if d["veredito"].startswith("Viable with the yield gain alone"):
            st.success(f"**{d['veredito']}**")
        elif d["veredito"].startswith("Viable"):
            st.info(f"**{d['veredito']}**")
        else:
            st.error(f"**{d['veredito']}**")

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown("#### Yield")
            st.metric("Increase in year 1", f"+{num(d['aumento_pct_ano1'], 1)}%")
            graos = cult in ("soja", "milho", "milho safrinha", "trigo", "feijão", "arroz irrigado")
            st.metric("In tonnes", f"+{num(d['aumento_t_ha_ano1'], 3)} t/ha",
                      sacas(d["aumento_t_ha_ano1"]) if graos else None, delta_color="off")
            st.metric("Mean gain per year", brl(d["ganho_r_ha_ano_medio"]) + "/ha",
                      f"over {cenario.simulacao.horizonte_anos} years, with a "
                      f"{pctbr(cenario.resposta.decaimento_anual, 0)} annual decay", delta_color="off")
        with k2:
            st.markdown("#### Carbon in the soil")
            st.metric("Carbon that stays in the soil", f"{num(d['c_retido_tc_ha'], 2)} t C/ha",
                      f"{num(d['c_retido_tco2e_ha'], 1)} tCO₂e/ha", delta_color="off")
            st.metric("Increase of the soil C stock (0–20 cm)", f"+{num(d['incremento_c_pct'], 1)}%",
                      f"current stock {num(d['estoque_c_nativo_tha'], 0)} t C/ha", delta_color="off")
            if d["gera_credito"]:
                st.metric("Carbon credit", f"{num(d['credito_tco2e_ha'], 2)} tCO₂e/ha",
                          f"{PADRAO_EN.get(cenario.carbono.padrao, cenario.carbono.padrao)} standard, net of emissions", delta_color="off")
            else:
                st.metric("Carbon credit", "none",
                          f"biochar outside the {PADRAO_EN.get(cenario.carbono.padrao, cenario.carbono.padrao)} standard", delta_color="off")
        with k3:
            st.markdown("#### Financial viability")
            st.metric("Upfront cost", brl(d["custo_inicial_r_ha"]) + "/ha")
            st.metric("Chance of paying off with the yield gain alone", f"{pctbr(d['prob_vpl_sem_carbono'], 0)}")
            st.metric("Chance of paying off with yield + carbon", f"{pctbr(d['prob_vpl_com_carbono'], 0)}")
            st.metric("Risk of not repaying the loan", f"{pctbr(d['prob_inadimplencia'], 0)}")

        st.markdown("#### What this means")
        texto = (f"In **{mun_m} ({uf_m})**, with {num(cenario.biocarvao.dose_t_ha, 1)} t/ha of biochar, "
                 f"{cult_en} yield should rise by about **{num(d['aumento_pct_ano1'], 1)}%** in the first year "
                 f"(+{num(d['aumento_t_ha_ano1'], 3)} t/ha), worth on average **{brl(d['ganho_r_ha_ano_medio'])} per "
                 f"hectare per year**. The biochar leaves about **{num(d['c_retido_tc_ha'], 2)} t of carbon per hectare** "
                 f"in the soil, {num(d['incremento_c_pct'], 0)}% more than the current stock of the 0–20 cm layer. ")
        if d["prob_vpl_sem_carbono"] >= cenario.simulacao.limiar_prob_vpl:
            texto += "The yield gain alone already pays for the investment in most scenarios."
        elif d["prob_vpl_com_carbono"] >= cenario.simulacao.limiar_prob_vpl:
            texto += ("The yield gain alone does not pay for the investment, but together with the sale of carbon credits it does.")
        else:
            texto += (f"Under current conditions, the investment pays off in only {pctbr(d['prob_vpl_com_carbono'], 0)} of "
                      f"scenarios, below the {pctbr(cenario.simulacao.limiar_prob_vpl, 0)} threshold.")
        st.markdown(texto)

        if not d["veredito"].startswith("Viable with the yield gain alone"):
            st.markdown("#### What would need to change")
            itens = [f"- To pay off **without carbon**, the yield increase would need to be about "
                     f"**{pctbr(d['resposta_necessaria_sem_carbono'], 1)}**; the expected value here is {num(d['aumento_pct_ano1'], 1)}%."]
            if d["gera_credito"] and np.isfinite(d["preco_carbono_equilibrio_usd"]):
                itens.append(f"- With the expected yield gain, carbon would need to be worth about "
                             f"**US$ {num(d['preco_carbono_equilibrio_usd'], 0)}/tCO₂e** (median of the scenarios).")
            itens.append("- Try in the sidebar: unfertilised or degraded pasture areas, another reference biochar, "
                         "biochar price, loan term and interest rate.")
            st.markdown("\n".join(itens))

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Yield increase year by year**")
            st.bar_chart(d["anual"].set_index("Year")[["Yield increase (t/ha)"]])
        with g2:
            st.markdown(f"**Municipality soil compared with {uf_m}**")
            st.dataframe(d["solo"].round(1), hide_index=True, width="stretch")
            classes_txt = ", ".join(f"{k.title()} ({v})" for k, v in d["classes_solo"].items())
            st.caption(f"Soil classes in the profiles (Brazilian system): {classes_txt}. Sandy, carbon-poor soils tend to "
                       "respond more to biochar.")
        st.caption(f"Based on {d['n_perfis']} BDsolos (Embrapa) profile(s), mostly from old soil surveys. "
                   "The retained carbon depends on the biochar and the dose; what changes between "
                   "municipalities is how much it adds to the soil stock. Yield response calibrated with "
                   "Chagas et al. (2024) and Latawiec et al. (2019); see the Validation tab.")

with aba_val:
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
        "(C < 30% and H/C > 0.75): it raises soil carbon but generates no credit.\n"
        "- **Latawiec et al. (2019):** 13 tCO₂e/ha measured by pot mass balance, versus about 2.8 times that from "
        "the permanence factor. The paper does not report the biochar C or H/C, so the comparison uses assumed "
        "values. It supports keeping a prudence discount on carbon in the decision rule.\n"
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

with aba_f:
    st.subheader("Tranched fund: investors and P2P in the senior quota, cooperative in the subordinated quota")
    st.caption("Portfolio of operations identical to the one simulated in the sidebar, with defaults correlated "
               "through a common regional shock (climate and price).")
    f1, f2, f3, f4 = st.columns(4)
    n_ops = f1.number_input("Operations in the portfolio", 10, 5000, 100, step=10)
    sub_pct = f2.slider("Subordination (cooperative quota)", 0.0, 0.6, 0.20, 0.05)
    taxa_sen = f3.slider("Senior target return (p.a.)", 0.05, 0.30, 0.14, 0.005)
    custo_f = f4.slider("Fund costs (p.a. on net assets)", 0.0, 0.05, 0.015, 0.0025)
    f5, f6, f7 = st.columns(3)
    rho = f5.slider("Default correlation", 0.0, 0.8, 0.25, 0.05)
    cessao_c = f6.slider("Carbon revenue assigned to the fund", 0.0, 1.0, 0.0, 0.05,
                         help="Share of the operations' carbon credits assigned to the fund as credit enhancement.")
    frac_p2p = f7.slider("Share of the senior quota raised via P2P/retail", 0.0, 1.0, 0.40, 0.05)
    pf = ParametrosFundo(n_operacoes=int(n_ops), subordinacao=sub_pct, taxa_senior_aa=taxa_sen,
                         custo_fundo_aa=custo_f, correlacao=rho, frac_carbono_cedida=cessao_c,
                         frac_p2p_senior=frac_p2p)
    if res["principal_p2p_r"] <= 0:
        st.warning("The operation has no financed amount: increase the financed share in the sidebar.")
        fundo_res = None
    else:
        fundo_res = simular_fundo(resultado, cenario.emprestimo, cenario.simulacao.horizonte_anos, pf)
        fr = fundo_res["resumo"]
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Fund net assets", brl(fr["pl_r"]))
        g2.metric("Senior quota", brl(fr["senior_r"]), f"P2P/retail: {brl(fr['senior_p2p_r'])}", delta_color="off")
        g3.metric("Subordinated quota (cooperative)", brl(fr["subordinada_r"]))
        g4.metric("Portfolio default rate", f"{pctbr(fr['inadimplencia_media_carteira'], 0)}",
                  f"P99: {pctbr(fr['inadimplencia_p99_carteira'], 0)}", delta_color="off")
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("P(senior loss)", f"{pctbr(fr['prob_perda_senior'], 1)}")
        h2.metric("Senior expected loss", f"{pctbr(fr['perda_esperada_senior'], 2)}")
        h3.metric("Median subordinated multiple", f"{num(fr['multiplo_sub_p10_p50_p90'][1], 2)}×",
                  f"P10 {num(fr['multiplo_sub_p10_p50_p90'][0], 2)}× · P90 {num(fr['multiplo_sub_p10_p50_p90'][2], 2)}×",
                  delta_color="off")
        h4.metric("P(subordinated loses capital)", f"{pctbr(fr['prob_sub_perde_capital'], 0)}")

        curva = curva_subordinacao(resultado, cenario.emprestimo, cenario.simulacao.horizonte_anos, pf)
        sub_min = subordinacao_minima(curva, 0.01)
        st.markdown("**How much the cooperative must subordinate to protect the senior quota**")
        st.line_chart(curva.set_index("subordinacao")[["prob_perda_senior", "perda_esperada_senior"]])
        if sub_min is None:
            st.error("Not even 50% subordination brings the senior loss probability below 1%. "
                     "Reduce operation risk (dose, term, target area) or assign carbon revenue to the fund.")
        else:
            st.success(f"Minimum subordination for at most a 1% senior loss probability: {pctbr(sub_min, 0)}.")
        st.caption("In Brazil, retail investors may only buy senior FIDC quotas (CVM Resolution 175, "
                   "Annex II, art. 13). The subordinated quota stays with the cooperative or qualified investors.")

    st.divider()
    st.subheader("Origination package and embedded credit via agfintech")
    o1, o2 = st.columns(2)
    coop_nome = o1.text_input("Cooperative", "")
    coop_cnpj = o2.text_input("Cooperative tax ID (CNPJ)", "")
    prod_id = o1.text_input("Pseudonymised farmer ID", "")
    car = o2.text_input("Rural Environmental Registry code (CAR)", "")
    forn_nome = o1.text_input("Biochar supplier", "")
    forn_cnpj = o2.text_input("Supplier tax ID (CNPJ)", "")
    mun_o = o1.text_input("Municipality of the farm", "")
    uf_o = o2.selectbox("State of the farm", ["PR", "SC", "RS", "SP", "MS", "MT", "GO", "MG", "outra"])
    canal = st.radio("Funding channel", CANAIS, horizontal=True,
                     format_func={"credito_embutido_agfintech": "Embedded credit (agfintech)",
                                  "p2p_sep": "P2P via SEP", "fundo_cotas": "Tranched fund"}.get)
    finalidades = st.multiselect("Purposes authorised by the farmer", FINALIDADES, format_func=lambda k: FINALIDADE_EN.get(k, k),
                                 default=["analise_credito", "registro_garantias", "certificacao_carbono"])
    consent = st.checkbox("The farmer gave explicit consent for these purposes (Brazilian data protection law, LGPD)")
    meta = MetadadosOriginacao(cooperativa_nome=coop_nome, cooperativa_cnpj=coop_cnpj, produtor_id=prod_id,
                               codigo_car=car, municipio=mun_o, uf=uf_o, fornecedor_nome=forn_nome,
                               fornecedor_cnpj=forn_cnpj, consentimento=consent,
                               finalidades=tuple(finalidades), canal=canal)
    if not consent:
        st.info("Tick the farmer's consent to generate the package.")
    else:
        fundo_info = None
        if canal == "fundo_cotas" and fundo_res is not None:
            fundo_info = {"parametros": vars(pf), "resultado": fundo_res["resumo"]}
        pacote = gerar_pacote(cenario, resultado, meta, perfis_sel, fundo_info)
        erros = validar_pacote(pacote)
        if erros:
            st.error("Package with issues: " + "; ".join(erros))
        else:
            st.success(f"Valid package · SHA-256 hash {pacote['integridade']['hash'][:16]}…")
        import json as _json
        st.download_button("Download origination package (JSON)",
                           _json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8"),
                           f"pacote_originacao_{pacote['id_pacote'][:8]}.json", "application/json")
        with st.expander("View package"):
            st.json(pacote, expanded=False)

        st.markdown("**Request embedded credit**")
        a1, a2 = st.columns(2)
        url_api = a1.text_input("Agfintech API URL", "", help="Empty = simulated mode with a local policy.")
        token_api = a2.text_input("Access token", "", type="password")
        with st.expander("Credit policy of the simulated mode"):
            pol = PoliticaCreditoSimulada(
                pd_maxima=st.slider("Maximum accepted default probability", 0.05, 0.8, 0.35, 0.05),
                prob_viavel_minima=st.slider("Minimum viability under the rule", 0.3, 0.95, 0.60, 0.05),
                taxa_base_aa=st.slider("Base rate (p.a.)", 0.05, 0.30, 0.14, 0.005),
                spread_por_pd=st.slider("Spread per unit of default probability", 0.0, 0.5, 0.20, 0.01),
                limite_por_ha_r=st.number_input("Limit per hectare (R$)", 0.0, 100_000.0, 6000.0, step=500.0))
        if st.button("Send to agfintech", disabled=bool(erros)):
            try:
                decisao = ClienteAgfintech(url_api, token_api, politica=pol).solicitar_credito(pacote)
                (st.success if decisao.get("status") == "aprovado" else st.warning)(
                    f"Decision: {decisao.get('status')} ({decisao.get('modo', 'api')})")
                st.json(decisao)
            except Exception as erro:
                st.error(f"API call failed: {erro}")

    spec = Path(__file__).parent / "openapi.yaml"
    if spec.exists():
        st.download_button("Download API specification (OpenAPI 3.1)", spec.read_bytes(), "openapi.yaml",
                           "application/yaml")

with aba_v:
    st.subheader("How much of the cost each benefit pays")
    custo = res["vp_custos_r"]
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Total cost (present value)", brl(custo))
    v2.metric("Yield + input savings", brl(res["vp_produtividade_mediano_r"] + res["vp_economia_insumos_r"]),
              f"covers {pctbr(res['cobertura_agro_mediana'], 0)} of the cost", delta_color="off")
    v3.metric("Carbon credit", brl(res["vp_carbono_mediano_r"]),
              f"covers {pctbr(res['cobertura_carbono_mediana'], 0)} of the cost", delta_color="off")
    v4.metric("Both combined", f"{pctbr(res['cobertura_agro_mediana'] + res['cobertura_carbono_mediana'], 0)} of the cost")

    ponte = pd.DataFrame({
        "Component": ["1. Cost", "2. Yield increase", "3. Input savings", "4. Carbon", "5. NPV"],
        "R$ (median)": [-custo, res["vp_produtividade_mediano_r"], res["vp_economia_insumos_r"],
                         res["vp_carbono_mediano_r"], res["vpl_com_carbono_p10_p50_p90"][1]],
    }).set_index("Component")
    st.bar_chart(ponte, horizontal=True)
    st.caption("Median present values. The median NPV is not the exact sum of the medians of the components.")

    st.subheader("When the project pays off")
    cls = pd.Series(res["classes_viabilidade"]).reindex(CLASSES_VIABILIDADE)
    st.bar_chart(cls.rename(index=CLASSES_EN).rename("Share of simulations"), horizontal=True)
    so_prod = cls["Só a produtividade paga"] + cls["Cada vantagem sozinha paga"]
    so_c = cls["Só o carbono paga"] + cls["Cada vantagem sozinha paga"]
    st.markdown(
        f"- The **yield gain alone** pays for the project in **{pctbr(so_prod, 0)}** of simulations.\n"
        f"- **Carbon alone** pays in **{pctbr(so_c, 0)}**.\n"
        f"- **Only both together** make it viable in **{pctbr(cls['Só as duas juntas pagam'], 0)}**: this is where carbon "
        f"turns an unviable case into a viable one.\n"
        f"- Not viable even with both: **{pctbr(cls['Inviável'], 0)}**.")

    st.subheader("Break-even points")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Break-even carbon price", f"US$ {num(res['preco_carbono_equilibrio_usd_mediano'], 0)}/t",
              "with the expected yield gain", delta_color="off")
    e2.metric("Carbon price with no yield gain", f"US$ {num(res['preco_carbono_equilibrio_sem_ganho_prod_usd'], 0)}/t",
              "input savings only", delta_color="off")
    e3.metric("Yield increase needed without carbon", f"{pctbr(res['resposta_equilibrio_sem_carbono_mediana'], 1)}",
              f"expected: {pctbr(res['resposta_media_usada'], 1)}", delta_color="off")
    e4.metric("Yield increase needed with carbon", f"{pctbr(res['resposta_equilibrio_com_carbono_mediana'], 1)}",
              f"expected: {pctbr(res['resposta_media_usada'], 1)}", delta_color="off")

    st.subheader("Viability map: carbon price × yield increase")
    precos_grade = np.arange(0, 401, 25)
    respostas_grade = np.round(np.arange(-0.05, 0.301, 0.025), 3)
    grade = mapa_viabilidade(resultado, precos_grade, respostas_grade)
    try:
        import altair as alt
        base_g = alt.Chart(grade).encode(
            x=alt.X("preco_carbono_usd:O", title="Carbon price (US$/tCO₂e)"),
            y=alt.Y("resposta_media:O", title="Mean yield increase", sort="descending",
                    axis=alt.Axis(format=".1%")))
        calor = base_g.mark_rect().encode(
            color=alt.Color("prob_viavel:Q", title="P(NPV>0)", scale=alt.Scale(scheme="redyellowgreen", domain=[0, 1])),
            tooltip=[alt.Tooltip("preco_carbono_usd", title="US$/t"),
                     alt.Tooltip("resposta_media", title="Increase", format=".1%"),
                     alt.Tooltip("prob_viavel", title="P(NPV>0)", format=".0%")])
        rotulos = base_g.mark_text(fontSize=10).encode(text=alt.Text("prob_viavel:Q", format=".0%"))
        st.altair_chart(calor + rotulos, width="stretch")
    except ImportError:
        st.dataframe(grade.pivot(index="resposta_media", columns="preco_carbono_usd", values="prob_viavel")
                     .sort_index(ascending=False), width="stretch")
    st.caption(f"Each cell uses the same simulations (climate, crop prices, credit issuance and between-field "
               f"variation), changing only the carbon price and the expected mean increase. "
               f"Current point: increase of {pctbr(res['resposta_media_usada'], 1)} and carbon between US$ {pc_min} and {pc_max}/t.")

with aba_r:
    st.subheader("Where biochar performs best in Paraná and Santa Catarina")
    perfis_all = carregar_perfis_app()
    if perfis_all is None:
        st.warning("File perfis_bdsolos_0_20.csv not found.")
    else:
        r1, r2, r3 = st.columns(3)
        ufs_r = r1.multiselect("States", ["PR", "SC"], default=["PR", "SC"])
        min_p = r2.slider("Minimum profiles per municipality", 1, 20, 3)
        criterio = r3.selectbox("Sort by", ["indice_combinado", "aumento_t_ha_ano1", "incremento_c_pct",
                                                "prob_vpl_com_carbono", "prob_vpl_sem_carbono"],
                                format_func={"indice_combinado": "Combined index (yield + carbon)",
                                             "aumento_t_ha_ano1": "Yield increase (t/ha)",
                                             "incremento_c_pct": "Increase of the soil C stock (%)",
                                             "prob_vpl_com_carbono": "Chance of paying off with carbon",
                                             "prob_vpl_sem_carbono": "Chance of paying off without carbon"}.get)
        ranking = ranking_en(avaliar_municipios_app(cenario.to_dict(), tuple(ufs_r), min_p))
        if ranking.empty:
            st.info("No municipality has enough profiles for the selected filters.")
        else:
            ranking = ranking.sort_values(criterio, ascending=False).reset_index(drop=True)
            top = ranking.iloc[0]
            st.markdown(
                f"**{top['municipio']} ({top['uf']})** leads on this criterion: yield "
                f"+{top['aumento_pct_ano1']:.1f}% (+{top['aumento_t_ha_ano1']:.3f} t/ha in year 1), soil C stock "
                f"+{top['incremento_c_pct']:.1f}% and a {top['prob_vpl_com_carbono']:.0%} chance of paying off with carbon. "
                f"{len(ranking)} municipalities evaluated. To see one municipality in detail, use the **My municipality** tab.")
            vc = ranking["veredito"].value_counts()
            st.caption(" · ".join(f"{k}: {v}" for k, v in vc.items()))
            geo = ranking.dropna(subset=["lat", "lon"]).copy()
            if len(geo):
                geo["cor"] = cor_por_valor(geo[criterio].rank(pct=True))
                geo["tamanho"] = 2000 + 600 * geo["n_perfis"].clip(upper=30)
                st.map(geo, latitude="lat", longitude="lon", color="cor", size="tamanho")
                st.caption(f"Colour: position on the chosen criterion (green = best). Size: number of profiles. "
                           f"{len(geo)} of {len(ranking)} municipalities have coordinates in the profiles.")
            st.dataframe(
                ranking.assign(prob_vpl_sem_carbono=100 * ranking["prob_vpl_sem_carbono"],
                               prob_vpl_com_carbono=100 * ranking["prob_vpl_com_carbono"])[["municipio", "uf", "veredito", "aumento_pct_ano1", "aumento_t_ha_ano1", "ganho_r_ha_ano_medio",
                         "c_retido_tc_ha", "incremento_c_pct", "credito_tco2e_ha", "prob_vpl_sem_carbono",
                         "prob_vpl_com_carbono", "n_perfis", "classe_solo_predominante", "argila_mediana_pct",
                         "c_org_mediano_gkg"]],
                width="stretch", hide_index=True,
                column_config={
                    "municipio": "Municipality", "uf": "State", "veredito": "Verdict",
                    "aumento_pct_ano1": st.column_config.NumberColumn("Yield (+% year 1)", format="%.1f"),
                    "aumento_t_ha_ano1": st.column_config.NumberColumn("Yield (+t/ha year 1)", format="%.3f"),
                    "ganho_r_ha_ano_medio": st.column_config.NumberColumn("Mean gain (R$/ha/yr)", format="%.0f"),
                    "c_retido_tc_ha": st.column_config.NumberColumn("C retained in soil (t C/ha)", format="%.2f"),
                    "incremento_c_pct": st.column_config.NumberColumn("Soil C stock (+%)", format="%.1f"),
                    "credito_tco2e_ha": st.column_config.NumberColumn("Credit (tCO₂e/ha)", format="%.2f"),
                    "prob_vpl_sem_carbono": st.column_config.ProgressColumn("Pays off without carbon", min_value=0, max_value=100, format="%.0f%%"),
                    "prob_vpl_com_carbono": st.column_config.ProgressColumn("Pays off with carbon", min_value=0, max_value=100, format="%.0f%%"),
                    "n_perfis": "Soil profiles", "classe_solo_predominante": "Predominant soil",
                    "argila_mediana_pct": st.column_config.NumberColumn("Clay (%)", format="%.0f"),
                    "c_org_mediano_gkg": st.column_config.NumberColumn("Soil organic C (g/kg)", format="%.1f"),
                })
            st.download_button("Download ranking (CSV)", ranking.to_csv(index=False).encode("utf-8"),
                               "ranking_municipios_pr_sc.csv", "text/csv")
            st.caption("Uses the sidebar parameters (biochar, crop, loan, carbon, liming correction). "
                       "C increase = C applied by the biochar ÷ native 0–20 cm stock. BDsolos profiles are old and "
                       "few in several municipalities: use the ranking to prioritise where to sample and run "
                       "trials, not as a final result.")

with aba1:
    lo = min(df["vpl_sem_carbono"].quantile(0.01), df["vpl_com_carbono"].quantile(0.01))
    hi = max(df["vpl_sem_carbono"].quantile(0.99), df["vpl_com_carbono"].quantile(0.99))
    bordas = np.linspace(lo, hi, 41)
    centros = (bordas[:-1] + bordas[1:]) / 2
    hist = pd.DataFrame({
        "NPV (R$ thousand)": np.round(centros / 1000, 1),
        "Without carbon": np.histogram(df["vpl_sem_carbono"], bordas)[0],
        "With carbon": np.histogram(df["vpl_com_carbono"], bordas)[0],
    }).set_index("NPV (R$ thousand)")
    st.bar_chart(hist, stack=False)
    p = res
    st.markdown(
        f"NPV without carbon — P10 {brl(p['vpl_sem_carbono_p10_p50_p90'][0])}, "
        f"P50 {brl(p['vpl_sem_carbono_p10_p50_p90'][1])}, P90 {brl(p['vpl_sem_carbono_p10_p50_p90'][2])}  \n"
        f"NPV with carbon — P10 {brl(p['vpl_com_carbono_p10_p50_p90'][0])}, "
        f"P50 {brl(p['vpl_com_carbono_p10_p50_p90'][1])}, P90 {brl(p['vpl_com_carbono_p10_p50_p90'][2])}"
    )

with aba2:
    parcelas = pd.DataFrame({"Year": range(len(res["parcelas_r"])), "Instalment (R$)": res["parcelas_r"]})
    st.bar_chart(parcelas.set_index("Year"))
    st.write(f"Principal financed via P2P: **{brl(res['principal_p2p_r'])}** · "
             f"median minimum DSCR: **{res['dscr_min_mediano']:.2f}**")

with aba3:
    opcoes = {
        "Max. carbon price (US$/t)": ("carbono.preco_max_usd_t", np.linspace(pc_min + 10, 500, 8)),
        "Dose (t/ha)": ("biocarvao.dose_t_ha", np.linspace(0.5, 10, 8)),
        "P2P annual effective cost": ("emprestimo.taxa_anual", np.linspace(0.08, 0.40, 8)),
        "Biochar price (R$/t)": ("biocarvao.preco_r_t", np.linspace(400, 3000, 8)),
        "Term (years)": ("emprestimo.prazo_anos", np.arange(2, 11)),
    }
    escolha = st.selectbox("Parameter", list(opcoes))
    if st.button("Run sensitivity"):
        caminho, valores = opcoes[escolha]
        cen_sens = Cenario(**{k: v for k, v in vars(cenario).items()})
        cen_sens.simulacao = ParametrosSimulacao(**{**vars(cenario.simulacao), "n_simulacoes": 3_000})
        valores = [int(x) for x in valores] if caminho.endswith("prazo_anos") else [float(x) for x in valores]
        tab = analise_sensibilidade(cen_sens, caminho, valores, perfis_sel).rename(columns=SENS_EN)
        st.line_chart(tab.set_index(caminho)[["P(NPV>0) without carbon", "P(NPV>0) with carbon", "Default probability"]])
        st.dataframe(tab, width="stretch")

with aba4:
    if perfis_sel is not None and len(perfis_sel):
        st.markdown("**0–20 cm layer of the selected profiles** (P10, median, P90)")
        st.dataframe(resumo_perfis(perfis_sel).round(2), width="stretch")
        geo = perfis_sel.dropna(subset=["lat", "lon"])
        if len(geo):
            st.map(geo[["lat", "lon"]])
        st.caption(f"{len(geo)} of {len(perfis_sel)} profiles have coordinates. Bulk density measured in "
                   f"{perfis_sel['ds_medida'].mean():.0%} of profiles; the rest estimated by pedotransfer.")
        cols_v = ["municipio", "classe_n1", "uso", "ano_coleta", "ph", "v_pct", "argila_pct",
                  "c_org_gkg", "estoque_c_0_20_tha", "link"]
        st.dataframe(perfis_sel[cols_v], width="stretch",
                     column_config={"link": st.column_config.LinkColumn("Description (PDF)")})
    else:
        st.write("Turn on BDsolos in the sidebar to see the profiles.")

with aba5:
    st.dataframe(df.describe().T, width="stretch")
    st.download_button("Download simulations (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "simulacoes_biocredito.csv", "text/csv")
    st.json(cenario.to_dict(), expanded=False)

with aba_mk:
    render_mercados(st, cenario, carregar_perfis_app())

with aba_br:
    render_brasil(st, cenario, carregar_perfis_app())

with aba_ini:
    render_inicio(st, cenario, carregar_perfis_app())
