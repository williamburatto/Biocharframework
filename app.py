"""
BioCrédito Agro — interface Streamlit do simulador.

Rodar localmente:   streamlit run app.py
Para embutir em outro app multipágina: copie este arquivo para pages/ e mantenha
simulador.py importável (mesma pasta ou pacote).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from bdsolos import carregar_perfis, filtrar, resumo as resumo_perfis
from regioes import avaliar_municipios, cor_por_valor, detalhar_municipio
from fundo import ParametrosFundo, simular_fundo, curva_subordinacao, subordinacao_minima
from validacao import (PRESETS_BIOCARVAO, REFERENCIAS, validar_produtividade, validar_carbono,
                       calibrar_fatores_adubacao, elegibilidade_presets, FAIXAS_LITERATURA, PRECOS_VIAVEIS_ETS,
                       FIGURA1_CRITERIOS, FIGURA2_FERRAMENTAS, SBCE_FIGURA3)
from originacao import (MetadadosOriginacao, ClienteAgfintech, PoliticaCreditoSimulada, gerar_pacote,
                        validar_pacote, FINALIDADES, CANAIS)

from simulador import (
    Cenario, ParametrosSolo, ParametrosBiocarvao, ParametrosCultura, ParametrosResposta,
    ParametrosCarbono, ParametrosEmprestimo, ParametrosSimulacao,
    ParametrosSaudeSolo, CLASSES_SAUDE, carregar_municipios,
    simular, analise_sensibilidade, sugerir_resposta_media,
    mapa_viabilidade, CLASSES_VIABILIDADE, CULTURAS, PADROES, fator_dose, fator_adubacao,
)

st.set_page_config(page_title="BioCrédito Agro — Simulador", layout="wide")
st.title("BioCrédito Agro — simulador de biocarvão financiado por P2P")
st.caption(
    "Monte Carlo dos módulos agronômico, de carbono e financeiro. "
    "Valores padrão são ilustrativos: calibre com laudos, ensaios e a metodologia de certificação escolhida."
)


@st.cache_data(show_spinner="Carregando perfis do BDsolos...")
def carregar_perfis_app():
    caminho = Path(__file__).parent / "perfis_bdsolos_0_20.csv"
    return carregar_perfis(str(caminho)) if caminho.exists() else None


@st.cache_data(show_spinner="Avaliando municípios...")
def avaliar_municipios_app(cen_dict: dict, ufs: tuple, min_perfis: int):
    return avaliar_municipios(cenario, carregar_perfis_app(), ufs=ufs, min_perfis=min_perfis)


@st.cache_data(show_spinner="Avaliando o município...")
def detalhar_municipio_app(cen_dict: dict, uf: str, municipio: str):
    d = detalhar_municipio(cenario, carregar_perfis_app(), uf, municipio)
    d.pop("resultado", None)
    return d


def num(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pctbr(x: float, casas: int = 0) -> str:
    return num(100 * x, casas) + "%"


def sacas(t_ha: float) -> str:
    return f"{num(t_ha * 1000 / 60, 1)} sc/ha"


def brl(x: float) -> str:
    return f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- entradas
with st.sidebar:
    st.header("Talhão e cultura")
    cultura = st.selectbox("Cultura", list(CULTURAS))
    ref = CULTURAS[cultura]
    st.caption("Valores de referência aproximados: substitua pelos da cooperativa, CONAB ou CEPEA.")
    area = st.number_input("Área (ha)", 1.0, 10_000.0, 50.0, step=5.0)
    y0 = st.number_input("Produtividade base Y₀ (t/ha)", 0.1, 200.0, ref["produtividade_t_ha"], step=0.1,
                         key=f"y0_{cultura}")
    p_cult = st.number_input("Preço da cultura (R$/t)", 10.0, 50_000.0, ref["preco_r_t"], step=50.0,
                             key=f"preco_{cultura}")
    p_cv = st.slider("Volatilidade do preço (CV)", 0.0, 0.5, ref["cv_preco"], 0.01, key=f"cv_{cultura}")
    margem = st.number_input("Margem base sem biocarvão (R$/ha/ano)", 0.0, 20_000.0, ref["margem_r_ha"],
                             step=100.0, key=f"margem_{cultura}")
    fator_cult = st.slider("Fator de resposta da cultura ao biocarvão", 0.0, 2.0, ref["fator_resposta"], 0.05,
                           key=f"fator_{cultura}",
                           help="Multiplica o aumento relativo de produtividade. Fica em 1,0 até haver "
                                "ensaios desta cultura que indiquem outro valor.")
    frac_margem = st.slider("Fração da margem comprometível com dívida", 0.1, 1.0, 0.6, 0.05)
    p_quebra = st.slider("Prob. anual de quebra climática (ZARC)", 0.0, 0.6, 0.15, 0.01)
    perda_quebra = st.slider("Perda na quebra", 0.0, 1.0, 0.35, 0.05)

    st.header("Perfis de solo (BDsolos Embrapa)")
    usar_bdsolos = st.checkbox("Sortear perfis reais do BDsolos", value=True,
                               help="Cada simulação sorteia um perfil (camada 0–20 cm) da região filtrada.")
    perfis_sel = None
    if usar_bdsolos:
        perfis_todos = carregar_perfis_app()
        if perfis_todos is None:
            st.warning("Arquivo perfis_bdsolos_0_20.csv não encontrado. Gere com: "
                       "python bdsolos.py bd_solos_para_redape.csv perfis_bdsolos_0_20.csv")
        else:
            ufs = sorted(perfis_todos["uf"].unique())
            uf_b = st.selectbox("UF", ufs, index=ufs.index("PR") if "PR" in ufs else 0)
            muns = ["(todos)"] + sorted(perfis_todos.loc[perfis_todos["uf"] == uf_b, "municipio"].unique())
            mun_b = st.selectbox("Município", muns)
            usar_raio = st.checkbox("Filtrar por raio a partir de coordenadas", value=False)
            lat_b = lon_b = raio_b = None
            if usar_raio:
                lat_b = st.number_input("Latitude (graus decimais)", -34.0, 6.0, -25.0, step=0.01)
                lon_b = st.number_input("Longitude (graus decimais)", -74.0, -28.0, -50.2, step=0.01)
                raio_b = st.slider("Raio (km)", 5, 300, 50, 5)
            classes = sorted(perfis_todos["classe_n1"].dropna().unique())
            classes_b = st.multiselect("Classes de solo (nível 1)", classes)
            so_agri = st.checkbox("Só perfis com uso agrícola registrado", value=False)
            perfis_sel = filtrar(perfis_todos, uf=None if usar_raio else uf_b,
                                 municipio=None if (mun_b == "(todos)" or usar_raio) else mun_b,
                                 lat=lat_b, lon=lon_b, raio_km=raio_b,
                                 classes_n1=classes_b or None, so_uso_agricola=so_agri)
            st.caption(f"{len(perfis_sel)} perfis selecionados")
            if len(perfis_sel) < 5:
                st.warning("Poucos perfis: amplie o filtro (UF inteira ou raio maior).")

    st.header("Solo")
    st.caption("Com BDsolos ativo, pH e V% abaixo só preenchem lacunas dos perfis.")
    ph = st.slider("pH em água", 4.0, 7.5, 5.4, 0.1)
    v = st.slider("V% (saturação por bases)", 10.0, 90.0, 50.0, 1.0)
    t_solo = st.slider("Temperatura média do solo (°C)", 10.0, 30.0, 21.0, 0.5)
    corrigir = st.checkbox("Lavoura corrigida (aplicar pH e V% mínimos)", value=True,
                           help="Os perfis do BDsolos são, em geral, de levantamentos antigos sob vegetação nativa "
                                "ou pastagem. Em lavoura com calagem, pH e V% atuais são maiores, e a resposta ao "
                                "biocarvão tende a ser menor.")
    ph_min = st.slider("pH mínimo na lavoura", 4.5, 6.5, 5.5, 0.1) if corrigir else None
    v_min = st.slider("V% mínimo na lavoura", 30.0, 80.0, 60.0, 1.0) if corrigir else None

    st.header("Saúde do solo (Embrapa)")
    st.caption("Plataforma Saúde do Solo BR / BioAS: saudedosolo.embrapa.gov.br/plataforma-publica")
    fonte_saude = st.radio("Fonte", ["nenhuma", "municipio", "laudo"],
                           format_func={"nenhuma": "Não usar", "municipio": "Classe do município",
                                        "laudo": "Laudo BioAS do talhão"}.get)
    saude_kw = {"fonte": fonte_saude}
    if fonte_saude == "municipio":
        arq = st.file_uploader("CSV de municípios (uf, municipio, classe_saude, n_amostras)", type="csv")
        if arq is not None:
            try:
                mun = carregar_municipios(arq)
                uf_sel = st.selectbox("UF", sorted(mun["uf"].unique()))
                sub = mun[mun["uf"] == uf_sel]
                mun_sel = st.selectbox("Município", sorted(sub["municipio"].unique()))
                linha = sub[sub["municipio"] == mun_sel].iloc[0]
                saude_kw.update(classe_saude=linha["classe_saude"], n_amostras_municipio=int(linha["n_amostras"]))
                st.caption(f"Classe: {linha['classe_saude']} · {int(linha['n_amostras'])} amostras")
            except ValueError as erro:
                st.error(str(erro))
        else:
            saude_kw["classe_saude"] = st.selectbox("Classe predominante no município", CLASSES_SAUDE, index=2)
            saude_kw["n_amostras_municipio"] = st.number_input("Nº de amostras no município", 0, 100_000, 10)
        st.caption("A classe municipal é a moda das amostras; com poucas amostras a incerteza aumenta.")
    elif fonte_saude == "laudo":
        usar_funcoes = st.checkbox("Tenho os escores F1, F2 e F3 (0–1)", value=True)
        if usar_funcoes:
            saude_kw["f1_ciclar"] = st.slider("F1 – ciclar nutrientes", 0.0, 1.0, 0.6, 0.01)
            saude_kw["f2_armazenar"] = st.slider("F2 – armazenar nutrientes", 0.0, 1.0, 0.5, 0.01)
            saude_kw["f3_suprir"] = st.slider("F3 – suprir nutrientes", 0.0, 1.0, 0.6, 0.01)
            saude_kw["iqs_fertbio"] = st.slider("IQS FertBio", 0.0, 1.0, 0.6, 0.01)
        else:
            saude_kw["classe_saude"] = st.selectbox("Condição do solo no laudo", CLASSES_SAUDE, index=2)

    st.header("Biocarvão")
    preset_nome = st.selectbox("Biocarvão de referência (literatura)", ["personalizado"] + list(PRESETS_BIOCARVAO),
                               help="Preenche C, H/C, O/C e tipo com valores relatados nos artigos.")
    pr_bc = PRESETS_BIOCARVAO.get(preset_nome, {"c_org_frac": 0.70, "h_c_org": 0.40, "o_c_org": 0.15,
                                                "tipo": "estrutural", "nota": ""})
    if pr_bc.get("nota"):
        st.caption(pr_bc["nota"])
    tipo = st.selectbox("Tipo", ["estrutural", "nutriente"], index=["estrutural", "nutriente"].index(pr_bc["tipo"]),
                        key=f"tipo_{preset_nome}",
                        help="Estrutural: madeira, palha, casca. Nutriente: esterco, lodo — maior resposta em solos pobres.")
    dose = st.number_input("Dose (t/ha, base seca)", 0.1, 50.0, 2.0, step=0.5,
                           help="Os ensaios de campo usados na calibração aplicaram 15–30 t/ha.")
    preco_bc = st.number_input("Preço do fornecedor (R$/t)", 0.0, 10_000.0, 1200.0, step=50.0)
    frete = st.number_input("Frete (R$/t)", 0.0, 2_000.0, 150.0, step=10.0)
    aplic = st.number_input("Custo de aplicação (R$/ha)", 0.0, 2_000.0, 120.0, step=10.0)
    c_org = st.slider("Carbono orgânico (fração)", 0.05, 0.95, float(pr_bc["c_org_frac"]), 0.01, key=f"corg_{preset_nome}")
    hc = st.slider("H/Corg (molar)", 0.05, 2.0, float(pr_bc["h_c_org"]), 0.01, key=f"hc_{preset_nome}")
    oc = st.slider("O/Corg (molar)", 0.0, 3.5, float(pr_bc["o_c_org"]), 0.01, key=f"oc_{preset_nome}")
    e_acv = st.number_input("Emissões de ciclo de vida (tCO₂e/t biocarvão)", 0.0, 2.0, 0.25, step=0.05)
    s_cal = st.number_input("Economia de calcário (R$/ha/ano)", 0.0, 2_000.0, 80.0, step=10.0)
    s_fert = st.number_input("Economia de fertilizante (R$/ha/ano)", 0.0, 2_000.0, 60.0, step=10.0)

    st.header("Resposta de produtividade")
    adub = st.radio("Manejo de adubação do talhão", ["completa", "sem_adubacao"],
                    format_func={"completa": "Lavoura com adubação NPK", "sem_adubacao": "Sem adubação / pastagem degradada"}.get,
                    help="Calibrado com Chagas et al. (2024) e Latawiec et al. (2019): com NPK o ganho do "
                         "biocarvão é bem menor.")
    with st.expander("Dose-resposta (calibração)"):
        dose_ref = st.number_input("Dose de referência dos ensaios (t/ha)", 1.0, 50.0, 15.0, step=1.0)
        dose_meia = st.number_input("Meia-saturação (t/ha) — hipótese", 0.5, 50.0, 5.0, step=0.5)
        st.caption(f"Fator de dose em {dose:g} t/ha: {fator_dose(dose, dose_ref, dose_meia):.2f} · "
                   f"fator de adubação: {fator_adubacao(adub, tipo):.1f}")
    solo_tmp = ParametrosSolo(ph_agua=ph, v_pct=v)
    sugerida = (sugerir_resposta_media(solo_tmp, ParametrosBiocarvao(tipo=tipo)) * fator_dose(dose, dose_ref, dose_meia)
                * fator_adubacao(adub, tipo))
    usar_sugerida = st.checkbox(f"Usar média sugerida pelo solo ({sugerida:.1%})", value=True)
    r_media = None if usar_sugerida else st.slider("Resposta média (fração)", -0.2, 0.8, 0.10, 0.01)
    r_desvio = st.slider("Incerteza entre talhões (desvio)", 0.0, 0.4, 0.10, 0.01)
    r_ruido = st.slider("Variação ano a ano", 0.0, 0.3, 0.05, 0.01)
    r_decai = st.slider("Decaimento anual do efeito", 0.0, 0.5, 0.10, 0.01,
                        help="Chagas et al. (2024): sem NPK, o ganho caiu a partir do 4º ano e voltou ao controle no 7º.")
    ensaios_txt = st.text_input("Ensaios observados (frações separadas por vírgula)", "",
                                help="Ex.: 0.05, 0.08, 0.03 — atualiza a priori por inferência bayesiana.")

    st.header("Carbono")
    padrao = st.selectbox("Padrão de certificação", list(PADROES), help="Limites de Lin et al. (2025), Tabela 2.")
    st.caption(PADROES[padrao]["nota"])
    hc_max_p, oc_max_p = 0.7, 0.4
    if padrao == "personalizado":
        hc_max_p = st.number_input("H/Corg máximo", 0.1, 2.0, 0.7, step=0.01)
        oc_max_p = st.number_input("O/Corg máximo", 0.05, 3.5, 0.4, step=0.01)
    opcoes_ets = ["faixa personalizada"] + [f"{e['ets']} {e['pais']}: {e['preco']} {e['moeda']}/t" for e in PRECOS_VIAVEIS_ETS]
    cen_ets = st.selectbox("Cenário de preço (Tabela 3 do artigo GCB)", opcoes_ets)
    if cen_ets == "faixa personalizada":
        pc_min, pc_max = st.slider("Preço do crédito (US$/tCO₂e)", 0, 500, (100, 200), 5)
    else:
        e_sel = PRECOS_VIAVEIS_ETS[opcoes_ets.index(cen_ets) - 1]
        usd_eur = st.number_input("US$ por €", 0.5, 2.0, 1.10, step=0.01, help="Ajuste ao câmbio do dia.") \
            if e_sel["moeda"] == "EUR" else 1.0
        p_usd = e_sel["preco"] * usd_eur
        var = st.slider("Variação em torno do preço viável", 0.0, 0.5, 0.2, 0.05)
        pc_min, pc_max = round(p_usd * (1 - var)), round(p_usd * (1 + var))
        st.caption(f"Faixa simulada: US$ {pc_min}–{pc_max}/tCO₂e")
    cambio = st.number_input("Câmbio (R$/US$)", 1.0, 15.0, 5.40, step=0.05)
    taxas = st.slider("Taxas de certificação e plataforma", 0.0, 0.6, 0.25, 0.01)
    p_emissao = st.slider("Prob. de emissão do crédito", 0.0, 1.0, 0.85, 0.05)
    ano_c = st.number_input("Ano de recebimento do carbono", 0, 15, 1)
    with st.expander("Fator de permanência (verifique na metodologia)"):
        a_perm = st.number_input("Intercepto a  (F = a − b·H/Corg)", 0.0, 2.0, 1.13, step=0.01)
        b_perm = st.number_input("Inclinação b", 0.0, 2.0, 0.46, step=0.01)
        aj_temp = st.number_input("Ajuste por °C acima de 15 °C", -0.05, 0.05, 0.0, step=0.005, format="%.3f")

    st.header("Empréstimo P2P (SEP)")
    frac_fin = st.slider("Fração financiada", 0.0, 1.0, 1.0, 0.05)
    taxa = st.slider("Custo efetivo anual", 0.0, 0.6, 0.18, 0.01)
    carencia = st.number_input("Carência (anos, só juros)", 0, 5, 1)
    prazo = st.number_input("Prazo total (anos)", 1, 15, 6)
    lgd = st.slider("LGD (perda dada inadimplência)", 0.0, 1.0, 0.45, 0.05)
    tarifa = st.slider("Tarifa da plataforma", 0.0, 0.1, 0.03, 0.005)

    st.header("Simulação")
    horizonte = st.number_input("Horizonte (anos)", 1, 20, 8)
    desconto = st.slider("Taxa de desconto do produtor", 0.0, 0.4, 0.12, 0.01)
    n_sim = st.select_slider("Nº de simulações", [1_000, 5_000, 10_000, 20_000, 50_000], 10_000)
    regra = st.radio("Regra de decisão", ["produtividade", "combinada"],
                     format_func={"produtividade": "Só produtividade paga (carbono = bônus)",
                                  "combinada": "Produtividade + carbono com desconto"}.get)
    desconto_c = st.slider("Desconto de prudência sobre o carbono", 0.0, 0.9, 0.30, 0.05,
                           help="Na regra combinada, a receita de carbono entra reduzida por este fator.") \
        if regra == "combinada" else 0.30
    limiar = st.slider("Limiar P(VPL>0) para aprovar", 0.5, 0.95, 0.70, 0.05)


def parse_ensaios(txt: str) -> list[float]:
    out = []
    for parte in txt.replace(";", ",").split(","):
        parte = parte.strip()
        if parte:
            try:
                out.append(float(parte))
            except ValueError:
                st.sidebar.warning(f"Ignorado: '{parte}'")
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


@st.cache_data(show_spinner="Rodando Monte Carlo...")
def rodar(cen_dict: dict, perfis: pd.DataFrame | None):
    # cache por dicionário de parâmetros + perfis filtrados
    return simular(cenario, perfis)


resultado = rodar(cenario.to_dict(), perfis_sel)
res, df = resultado["resumo"], resultado["simulacoes"]

with st.expander("Como usar este app", expanded=False):
    st.markdown(
        "1. **Meu município:** escolha um município do PR ou de SC e veja, em linguagem direta, quanto a "
        "produtividade aumenta, quanto carbono fica no solo e se o investimento se paga.\n"
        "2. **Ranking PR e SC:** compare todos os municípios com perfis de solo da Embrapa.\n"
        "3. **Barra lateral:** mude cultura, dose, tipo de biocarvão, adubação, preço do carbono e condições "
        "do empréstimo. Todas as abas se atualizam.\n"
        "4. As demais abas detalham a análise financeira, o fundo, a validação com a literatura e o artigo base.")

aba_mun, aba_r, aba_v, aba_res, aba_f, aba_val, aba_gcb, aba1, aba2, aba3, aba4, aba5 = st.tabs(
    ["Meu município", "Ranking PR e SC", "Duas vantagens", "Resumo da operação", "Crédito embutido e fundo",
     "Validação (literatura)", "Framework (artigo GCB)", "Distribuição do VPL", "Fluxo do empréstimo",
     "Sensibilidade", "Solos (BDsolos)", "Dados"])

with aba_res:
    # --------------------------------------------------------------------------- resultado
    if res["aprovado"]:
        st.success(f"Operação APROVADA: P(viável pela regra) = {res['prob_decisao']:.0%} ≥ {limiar:.0%} "
                   f"({'só produtividade' if regra == 'produtividade' else f'produtividade + carbono com desconto de {desconto_c:.0%}'}).")
    else:
        st.error(f"Operação NÃO aprovada: P(viável pela regra) = {res['prob_decisao']:.0%} < {limiar:.0%} "
                 f"({'só produtividade' if regra == 'produtividade' else f'produtividade + carbono com desconto de {desconto_c:.0%}'}).")

    if not res["biocarvao_elegivel"]:
        st.warning(f"Biocarvão inelegível no padrão {res['padrao_carbono']} ({'; '.join(res['motivos_inelegivel'])}): "
                   f"receita de carbono zerada. O carbono ainda fica no solo: cerca de "
                   f"{res['incremento_c_solo_tha']:.1f} t C/ha estimadas, sem gerar crédito.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P(VPL>0) sem carbono", f"{res['prob_vpl_pos_sem_carbono']:.0%}")
    c2.metric("P(VPL>0) com carbono", f"{res['prob_vpl_pos_com_carbono']:.0%}")
    c3.metric("Prob. inadimplência", f"{res['prob_inadimplencia']:.0%}")
    c4.metric("Perda esperada (% principal)", f"{res['perda_esperada_pct_principal']:.1%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Custo inicial", brl(res["custo_inicial_r"]))
    c6.metric("Remoção líquida", f"{res['remocao_liquida_tco2e']:,.0f} tCO₂e",
              f"{res['remocao_tco2e_por_ha']:.2f} t/ha", delta_color="off")
    c7.metric("Resposta média usada", f"{res['resposta_media_usada']:.1%}",
              f"± {res['resposta_desvio_usado']:.1%} · saúde do solo ×{res['fator_saude_solo']:.2f}",
              delta_color="off")
    c8.metric("Múltiplo médio do investidor", f"{res['multiplo_investidor_medio']:.2f}×")

    if res["n_perfis_solo"]:
        st.info(f"{res['n_perfis_solo']} perfis BDsolos sorteados · pH mediano usado {res['ph_mediano_simulado']:.2f} · "
                f"C do biocarvão {res['c_biocarvao_tha']:.1f} t/ha vs. estoque nativo mediano 0–20 cm "
                f"{res['estoque_c_nativo_mediano_tha']:.1f} t C/ha")


with aba_mun:
    st.subheader("Avaliação por município")
    perfis_m = carregar_perfis_app()
    if perfis_m is None:
        st.warning("Arquivo perfis_bdsolos_0_20.csv não encontrado.")
    else:
        mc1, mc2 = st.columns([1, 3])
        uf_m = mc1.selectbox("Estado", ["PR", "SC"], key="uf_mun")
        contagem = perfis_m[perfis_m["uf"] == uf_m].groupby("municipio").size().sort_index()
        mun_m = mc2.selectbox("Município", list(contagem.index),
                              format_func=lambda m: f"{m} ({contagem[m]} perfil{'is' if contagem[m] > 1 else ''} de solo)",
                              key="mun_mun")
        d = detalhar_municipio_app(cenario.to_dict(), uf_m, mun_m)
        cult = cenario.cultura.cultura
        st.caption(f"Cenário: {cult}, {num(cenario.biocarvao.dose_t_ha, 1)} t/ha de biocarvão "
                   f"({'lavoura adubada' if cenario.resposta.manejo_adubacao == 'completa' else 'sem adubação'}), "
                   f"carbono entre US$ {num(cenario.carbono.preco_min_usd_t, 0)} e {num(cenario.carbono.preco_max_usd_t, 0)}/t. "
                   "Mude na barra lateral.")

        if d["veredito"].startswith("Viável só"):
            st.success(f"**{d['veredito']}**")
        elif d["veredito"].startswith("Viável"):
            st.info(f"**{d['veredito']}**")
        else:
            st.error(f"**{d['veredito']}**")

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown("#### Produtividade")
            st.metric("Aumento no 1º ano", f"+{num(d['aumento_pct_ano1'], 1)}%")
            graos = cult in ("soja", "milho", "milho safrinha", "trigo", "feijão", "arroz irrigado")
            st.metric("Em toneladas", f"+{num(d['aumento_t_ha_ano1'], 3)} t/ha",
                      sacas(d["aumento_t_ha_ano1"]) if graos else None, delta_color="off")
            st.metric("Ganho médio por ano", brl(d["ganho_r_ha_ano_medio"]) + "/ha",
                      f"em {cenario.simulacao.horizonte_anos} anos, com perda de "
                      f"{pctbr(cenario.resposta.decaimento_anual, 0)} ao ano", delta_color="off")
        with k2:
            st.markdown("#### Carbono no solo")
            st.metric("Carbono que fica no solo", f"{num(d['c_retido_tc_ha'], 2)} t C/ha",
                      f"{num(d['c_retido_tco2e_ha'], 1)} tCO₂e/ha", delta_color="off")
            st.metric("Aumento do estoque de C (0–20 cm)", f"+{num(d['incremento_c_pct'], 1)}%",
                      f"estoque atual {num(d['estoque_c_nativo_tha'], 0)} t C/ha", delta_color="off")
            if d["gera_credito"]:
                st.metric("Crédito de carbono", f"{num(d['credito_tco2e_ha'], 2)} tCO₂e/ha",
                          f"padrão {cenario.carbono.padrao}, já descontadas as emissões", delta_color="off")
            else:
                st.metric("Crédito de carbono", "não gera",
                          f"biocarvão fora do padrão {cenario.carbono.padrao}", delta_color="off")
        with k3:
            st.markdown("#### Viabilidade financeira")
            st.metric("Custo inicial", brl(d["custo_inicial_r_ha"]) + "/ha")
            st.metric("Chance de se pagar só com produtividade", f"{pctbr(d['prob_vpl_sem_carbono'], 0)}")
            st.metric("Chance de se pagar com produtividade + carbono", f"{pctbr(d['prob_vpl_com_carbono'], 0)}")
            st.metric("Risco de não pagar o empréstimo", f"{pctbr(d['prob_inadimplencia'], 0)}")

        st.markdown("#### O que isso significa")
        texto = (f"Em **{mun_m} ({uf_m})**, com {num(cenario.biocarvao.dose_t_ha, 1)} t/ha de biocarvão, a "
                 f"produtividade de {cult} deve subir cerca de **{num(d['aumento_pct_ano1'], 1)}%** no primeiro ano "
                 f"(+{num(d['aumento_t_ha_ano1'], 3)} t/ha), o que rende em média **{brl(d['ganho_r_ha_ano_medio'])} por "
                 f"hectare por ano**. O biocarvão deixa cerca de **{num(d['c_retido_tc_ha'], 2)} t de carbono por hectare** "
                 f"no solo, {num(d['incremento_c_pct'], 0)}% a mais que o estoque atual da camada de 0–20 cm. ")
        if d["prob_vpl_sem_carbono"] >= cenario.simulacao.limiar_prob_vpl:
            texto += "Só o ganho de produtividade já paga o investimento na maioria dos cenários."
        elif d["prob_vpl_com_carbono"] >= cenario.simulacao.limiar_prob_vpl:
            texto += ("O ganho de produtividade sozinho não paga o investimento, mas somado à venda do crédito "
                      "de carbono, sim.")
        else:
            texto += (f"Com as condições atuais, o investimento se paga em só {pctbr(d['prob_vpl_com_carbono'], 0)} dos "
                      f"cenários, abaixo do mínimo de {pctbr(cenario.simulacao.limiar_prob_vpl, 0)}.")
        st.markdown(texto)

        if not d["veredito"].startswith("Viável só"):
            st.markdown("#### O que precisaria mudar")
            itens = [f"- Para se pagar **sem carbono**, o aumento de produtividade teria de ser de cerca de "
                     f"**{pctbr(d['resposta_necessaria_sem_carbono'], 1)}**; o esperado aqui é {num(d['aumento_pct_ano1'], 1)}%."]
            if d["gera_credito"] and np.isfinite(d["preco_carbono_equilibrio_usd"]):
                itens.append(f"- Com o ganho de produtividade esperado, o carbono precisaria valer cerca de "
                             f"**US$ {num(d['preco_carbono_equilibrio_usd'], 0)}/tCO₂e** (mediana dos cenários).")
            itens.append("- Teste na barra lateral: área sem adubação ou pastagem degradada, outro biocarvão de "
                         "referência, preço do biocarvão, prazo e taxa do empréstimo.")
            st.markdown("\n".join(itens))

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Aumento de produtividade ano a ano**")
            st.bar_chart(d["anual"].set_index("Ano")[["Aumento de produtividade (t/ha)"]])
        with g2:
            st.markdown(f"**Solo do município comparado ao {uf_m}**")
            st.dataframe(d["solo"].round(1), hide_index=True, use_container_width=True)
            classes_txt = ", ".join(f"{k.title()} ({v})" for k, v in d["classes_solo"].items())
            st.caption(f"Classes de solo nos perfis: {classes_txt}. Solos arenosos e pobres em carbono tendem a "
                       "responder mais ao biocarvão.")
        st.caption(f"Baseado em {d['n_perfis']} perfil(is) do BDsolos (Embrapa), coletados em sua maioria em "
                   "levantamentos antigos. O carbono retido depende do biocarvão e da dose; o que muda entre "
                   "municípios é quanto ele representa do estoque do solo. Resposta de produtividade calibrada com "
                   "Chagas et al. (2024) e Latawiec et al. (2019); veja a aba Validação.")

with aba_val:
    st.subheader("Validação da produtividade e do carbono com cinco artigos")
    st.markdown(
        "O modelo de resposta foi confrontado com ensaios de campo no Brasil. Com o modelo anterior "
        "(sem dose e sem manejo de adubação), o erro era grande: subestimava o ganho sem adubação e "
        "superestimava com NPK. Foram incluídos **fator de dose** (saturante, 1,0 a 15 t/ha), "
        "**fator de adubação × tipo de biocarvão** e **decaimento anual de 10%**.")
    vp = validar_produtividade()
    mae_a, mae_d = vp["erro_anterior_pp"].abs().mean(), vp["erro_calibrado_pp"].abs().mean()
    m1, m2, m3 = st.columns(3)
    m1.metric("Erro médio absoluto — modelo anterior", f"{num(mae_a, 1)} p.p.")
    m2.metric("Erro médio absoluto — calibrado", f"{num(mae_d, 1)} p.p.")
    m3.metric("Ensaios de campo usados", f"{len(vp)}")
    st.caption("Atenção: os fatores foram ajustados nesses mesmos ensaios. O erro calibrado mede ajuste, não "
               "validação independente. Novos ensaios das cooperativas (campo 'Ensaios observados') são a validação.")
    graf = vp.set_index("caso")[["observado", "previsto_modelo_anterior", "previsto_calibrado"]]
    st.bar_chart(graf, horizontal=True, stack=False)
    st.dataframe(vp, use_container_width=True, hide_index=True, column_config={
        "observado": st.column_config.NumberColumn("Observado", format="%.3f"),
        "previsto_modelo_anterior": st.column_config.NumberColumn("Modelo anterior", format="%.3f"),
        "previsto_calibrado": st.column_config.NumberColumn("Calibrado", format="%.3f"),
        "erro_anterior_pp": st.column_config.NumberColumn("Erro anterior (p.p.)", format="%.1f"),
        "erro_calibrado_pp": st.column_config.NumberColumn("Erro calibrado (p.p.)", format="%.1f")})
    cal = calibrar_fatores_adubacao()
    st.markdown("**Fatores de adubação calibrados** (média geométrica observado/previsto)")
    st.dataframe(pd.DataFrame([{"manejo/tipo": k, "fator": v["fator"], "ensaios": v["n_ensaios"]} for k, v in cal.items()]),
                 hide_index=True)
    st.markdown("**Ordem de grandeza na literatura** (Rani & Garg, 2025)")
    st.dataframe(pd.DataFrame(FAIXAS_LITERATURA), hide_index=True, use_container_width=True)

    st.markdown("**Carbono retido no solo: previsto × medido**")
    vc = validar_carbono(cenario.carbono.perm_intercepto, cenario.carbono.perm_inclinacao, cenario.carbono.padrao)
    st.dataframe(vc, use_container_width=True, hide_index=True)
    st.markdown(
        "- **Chagas et al. (2024):** o fator de permanência prevê 3,6 t C/ha retidas contra cerca de 3,0 medidas "
        "em 7 safras (razão 1,17). O biocarvão de lodo, porém, não passa em nenhum padrão "
        "(C < 30% e H/C > 0,75): aumenta o carbono do solo, mas não gera crédito.\n"
        "- **Latawiec et al. (2019):** 13 tCO₂e/ha medidas por balanço de massa em vaso, contra cerca de 2,8 vezes "
        "isso pelo fator de permanência. O artigo não informa C nem H/C do biocarvão, então a comparação "
        "usa valores assumidos. É um sinal para manter o desconto de prudência sobre o carbono na regra de decisão.\n"
        "- **Al-Gaashani et al. (2026)** e **Lin et al. (2025):** a temperatura de pirólise decide a elegibilidade. "
        "Biocarvão verde a 300 °C (H/C 0,79–0,99) reprova em todos os padrões; a ≥ 500 °C (H/C 0,30–0,42) passa.")
    st.markdown("**Elegibilidade dos biocarvões de referência por padrão** (limites de Lin et al., 2025)")
    st.dataframe(elegibilidade_presets(), hide_index=True, use_container_width=True)
    st.markdown("**Não validado pelos artigos:** economia de calcário e de fertilizante, meia-saturação da dose, "
                "resposta de soja, trigo e feijão com biocarvão em lavoura adubada.")

with aba_gcb:
    st.subheader("Framework do artigo base e onde cada parte está no app")
    st.markdown(f"*{REFERENCIAS['GCB']}*")
    st.markdown(
        "O artigo construiu o framework em três passos: (a) comparação dos padrões de qualidade do biocarvão "
        "(Figura 1); (b) mapeamento das ferramentas tecnológicas e financeiras que reduzem barreiras (Figura 2); "
        "(c) integração em um framework que liga certificação, rastreabilidade e mercado (Figura 4). "
        "O app implementa o passo (c) para a agricultura brasileira e acrescenta a validação agronômica.")
    st.markdown("**Figura 1 — parâmetros de qualidade por padrão**")
    st.dataframe(pd.DataFrame(FIGURA1_CRITERIOS), hide_index=True, use_container_width=True)
    st.markdown("**Figura 2 — ferramentas para reduzir barreiras e aumentar a rentabilidade**")
    st.dataframe(pd.DataFrame(FIGURA2_FERRAMENTAS), hide_index=True, use_container_width=True)
    st.markdown("**Tabela 3 — desafios e preços viáveis por sistema de comércio de emissões** "
                "(selecionáveis na barra lateral, em Carbono)")
    st.dataframe(pd.DataFrame(PRECOS_VIAVEIS_ETS), hide_index=True, use_container_width=True)
    st.markdown("**Figura 3 — SBCE**")
    st.write(SBCE_FIGURA3)

    st.subheader("Referências")
    for chave in ["GCB", "Chagas2024", "Latawiec2019", "Rani2025", "AlGaashani2026", "Lin2025", "Jeffery2017"]:
        st.markdown(f"- {REFERENCIAS[chave]}")

with aba_f:
    st.subheader("Fundo com cotas: investidores e P2P na sênior, cooperativa na subordinada")
    st.caption("Carteira de operações iguais à simulada na barra lateral, com inadimplência correlacionada "
               "por um choque regional comum (clima e preço).")
    f1, f2, f3, f4 = st.columns(4)
    n_ops = f1.number_input("Operações na carteira", 10, 5000, 100, step=10)
    sub_pct = f2.slider("Subordinação (cota da cooperativa)", 0.0, 0.6, 0.20, 0.05)
    taxa_sen = f3.slider("Remuneração-alvo da sênior (a.a.)", 0.05, 0.30, 0.14, 0.005)
    custo_f = f4.slider("Custos do fundo (a.a. sobre o PL)", 0.0, 0.05, 0.015, 0.0025)
    f5, f6, f7 = st.columns(3)
    rho = f5.slider("Correlação de inadimplência", 0.0, 0.8, 0.25, 0.05)
    cessao_c = f6.slider("Receita de carbono cedida ao fundo", 0.0, 1.0, 0.0, 0.05,
                         help="Fração dos créditos de carbono das operações cedida ao fundo como reforço de crédito.")
    frac_p2p = f7.slider("Parte da sênior captada via P2P/varejo", 0.0, 1.0, 0.40, 0.05)
    pf = ParametrosFundo(n_operacoes=int(n_ops), subordinacao=sub_pct, taxa_senior_aa=taxa_sen,
                         custo_fundo_aa=custo_f, correlacao=rho, frac_carbono_cedida=cessao_c,
                         frac_p2p_senior=frac_p2p)
    if res["principal_p2p_r"] <= 0:
        st.warning("A operação não tem valor financiado: aumente a fração financiada na barra lateral.")
        fundo_res = None
    else:
        fundo_res = simular_fundo(resultado, cenario.emprestimo, cenario.simulacao.horizonte_anos, pf)
        fr = fundo_res["resumo"]
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Patrimônio do fundo", brl(fr["pl_r"]))
        g2.metric("Cota sênior", brl(fr["senior_r"]), f"P2P/varejo: {brl(fr['senior_p2p_r'])}", delta_color="off")
        g3.metric("Cota subordinada (cooperativa)", brl(fr["subordinada_r"]))
        g4.metric("Inadimplência da carteira", f"{pctbr(fr['inadimplencia_media_carteira'], 0)}",
                  f"P99: {pctbr(fr['inadimplencia_p99_carteira'], 0)}", delta_color="off")
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("P(sênior perde)", f"{pctbr(fr['prob_perda_senior'], 1)}")
        h2.metric("Perda esperada da sênior", f"{pctbr(fr['perda_esperada_senior'], 2)}")
        h3.metric("Múltiplo mediano da subordinada", f"{num(fr['multiplo_sub_p10_p50_p90'][1], 2)}×",
                  f"P10 {num(fr['multiplo_sub_p10_p50_p90'][0], 2)}× · P90 {num(fr['multiplo_sub_p10_p50_p90'][2], 2)}×",
                  delta_color="off")
        h4.metric("P(subordinada perde capital)", f"{pctbr(fr['prob_sub_perde_capital'], 0)}")

        curva = curva_subordinacao(resultado, cenario.emprestimo, cenario.simulacao.horizonte_anos, pf)
        sub_min = subordinacao_minima(curva, 0.01)
        st.markdown("**Quanto a cooperativa precisa subordinar para proteger a sênior**")
        st.line_chart(curva.set_index("subordinacao")[["prob_perda_senior", "perda_esperada_senior"]])
        if sub_min is None:
            st.error("Nem 50% de subordinação deixa a chance de perda da sênior abaixo de 1%. "
                     "Reduza o risco da operação (dose, prazo, área-alvo) ou ceda receita de carbono ao fundo.")
        else:
            st.success(f"Subordinação mínima para a sênior ter no máximo 1% de chance de perda: {pctbr(sub_min, 0)}.")
        st.caption("No Brasil, o público em geral só pode comprar cotas seniores de FIDC (Res. CVM 175, "
                   "Anexo II, art. 13). A subordinada fica com a cooperativa ou com investidores qualificados.")

    st.divider()
    st.subheader("Pacote de originação e crédito embutido via agfintech")
    o1, o2 = st.columns(2)
    coop_nome = o1.text_input("Cooperativa", "")
    coop_cnpj = o2.text_input("CNPJ da cooperativa", "")
    prod_id = o1.text_input("ID pseudonimizado do produtor", "")
    car = o2.text_input("Código do CAR", "")
    forn_nome = o1.text_input("Fornecedor de biocarvão", "")
    forn_cnpj = o2.text_input("CNPJ do fornecedor", "")
    mun_o = o1.text_input("Município do imóvel", "")
    uf_o = o2.selectbox("UF do imóvel", ["PR", "SC", "RS", "SP", "MS", "MT", "GO", "MG", "outra"])
    canal = st.radio("Canal de funding", CANAIS, horizontal=True,
                     format_func={"credito_embutido_agfintech": "Crédito embutido (agfintech)",
                                  "p2p_sep": "P2P via SEP", "fundo_cotas": "Fundo com cotas"}.get)
    finalidades = st.multiselect("Finalidades autorizadas pelo produtor", FINALIDADES,
                                 default=["analise_credito", "registro_garantias", "certificacao_carbono"])
    consent = st.checkbox("O produtor deu consentimento expresso para essas finalidades (LGPD)")
    meta = MetadadosOriginacao(cooperativa_nome=coop_nome, cooperativa_cnpj=coop_cnpj, produtor_id=prod_id,
                               codigo_car=car, municipio=mun_o, uf=uf_o, fornecedor_nome=forn_nome,
                               fornecedor_cnpj=forn_cnpj, consentimento=consent,
                               finalidades=tuple(finalidades), canal=canal)
    if not consent:
        st.info("Marque o consentimento do produtor para gerar o pacote.")
    else:
        fundo_info = None
        if canal == "fundo_cotas" and fundo_res is not None:
            fundo_info = {"parametros": vars(pf), "resultado": fundo_res["resumo"]}
        pacote = gerar_pacote(cenario, resultado, meta, perfis_sel, fundo_info)
        erros = validar_pacote(pacote)
        if erros:
            st.error("Pacote com pendências: " + "; ".join(erros))
        else:
            st.success(f"Pacote válido · hash SHA-256 {pacote['integridade']['hash'][:16]}…")
        import json as _json
        st.download_button("Baixar pacote de originação (JSON)",
                           _json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8"),
                           f"pacote_originacao_{pacote['id_pacote'][:8]}.json", "application/json")
        with st.expander("Ver pacote"):
            st.json(pacote, expanded=False)

        st.markdown("**Solicitar crédito embutido**")
        a1, a2 = st.columns(2)
        url_api = a1.text_input("URL da API da agfintech", "", help="Vazio = modo simulado com política local.")
        token_api = a2.text_input("Token de acesso", "", type="password")
        with st.expander("Política de crédito do modo simulado"):
            pol = PoliticaCreditoSimulada(
                pd_maxima=st.slider("Inadimplência máxima aceita", 0.05, 0.8, 0.35, 0.05),
                prob_viavel_minima=st.slider("Viabilidade mínima pela regra", 0.3, 0.95, 0.60, 0.05),
                taxa_base_aa=st.slider("Taxa base (a.a.)", 0.05, 0.30, 0.14, 0.005),
                spread_por_pd=st.slider("Spread por unidade de inadimplência", 0.0, 0.5, 0.20, 0.01),
                limite_por_ha_r=st.number_input("Limite por hectare (R$)", 0.0, 100_000.0, 6000.0, step=500.0))
        if st.button("Enviar à agfintech", disabled=bool(erros)):
            try:
                decisao = ClienteAgfintech(url_api, token_api, politica=pol).solicitar_credito(pacote)
                (st.success if decisao.get("status") == "aprovado" else st.warning)(
                    f"Decisão: {decisao.get('status')} ({decisao.get('modo', 'api')})")
                st.json(decisao)
            except Exception as erro:
                st.error(f"Falha na chamada à API: {erro}")

    spec = Path(__file__).parent / "openapi.yaml"
    if spec.exists():
        st.download_button("Baixar especificação da API (OpenAPI 3.1)", spec.read_bytes(), "openapi.yaml",
                           "application/yaml")

with aba_v:
    st.subheader("Quanto do custo cada vantagem paga")
    custo = res["vp_custos_r"]
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Custo total (valor presente)", brl(custo))
    v2.metric("Produtividade + economia de insumos", brl(res["vp_produtividade_mediano_r"] + res["vp_economia_insumos_r"]),
              f"cobre {pctbr(res['cobertura_agro_mediana'], 0)} do custo", delta_color="off")
    v3.metric("Crédito de carbono", brl(res["vp_carbono_mediano_r"]),
              f"cobre {pctbr(res['cobertura_carbono_mediana'], 0)} do custo", delta_color="off")
    v4.metric("Soma das duas", f"{pctbr(res['cobertura_agro_mediana'] + res['cobertura_carbono_mediana'], 0)} do custo")

    ponte = pd.DataFrame({
        "Componente": ["1. Custo", "2. Aumento de produtividade", "3. Economia de insumos", "4. Carbono", "5. VPL"],
        "R$ (mediana)": [-custo, res["vp_produtividade_mediano_r"], res["vp_economia_insumos_r"],
                         res["vp_carbono_mediano_r"], res["vpl_com_carbono_p10_p50_p90"][1]],
    }).set_index("Componente")
    st.bar_chart(ponte, horizontal=True)
    st.caption("Valores presentes medianos. O VPL mediano não é a soma exata das medianas das parcelas.")

    st.subheader("Quando o projeto se paga")
    cls = pd.Series(res["classes_viabilidade"]).reindex(CLASSES_VIABILIDADE)
    st.bar_chart(cls.rename("Fração das simulações"), horizontal=True)
    so_prod = cls["Só a produtividade paga"] + cls["Cada vantagem sozinha paga"]
    so_c = cls["Só o carbono paga"] + cls["Cada vantagem sozinha paga"]
    st.markdown(
        f"- A **produtividade sozinha** paga o projeto em **{pctbr(so_prod, 0)}** das simulações.\n"
        f"- O **carbono sozinho** paga em **{pctbr(so_c, 0)}**.\n"
        f"- **Só a soma das duas** viabiliza em **{pctbr(cls['Só as duas juntas pagam'], 0)}**: é aí que o carbono "
        f"transforma um caso inviável em viável.\n"
        f"- Inviável mesmo com as duas: **{pctbr(cls['Inviável'], 0)}**.")

    st.subheader("Pontos de equilíbrio")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Preço de carbono de equilíbrio", f"US$ {num(res['preco_carbono_equilibrio_usd_mediano'], 0)}/t",
              "com o ganho de produtividade esperado", delta_color="off")
    e2.metric("Preço de carbono sem ganho de produtividade", f"US$ {num(res['preco_carbono_equilibrio_sem_ganho_prod_usd'], 0)}/t",
              "só economia de insumos", delta_color="off")
    e3.metric("Aumento de produtividade necessário sem carbono", f"{pctbr(res['resposta_equilibrio_sem_carbono_mediana'], 1)}",
              f"esperado: {pctbr(res['resposta_media_usada'], 1)}", delta_color="off")
    e4.metric("Aumento de produtividade necessário com carbono", f"{pctbr(res['resposta_equilibrio_com_carbono_mediana'], 1)}",
              f"esperado: {pctbr(res['resposta_media_usada'], 1)}", delta_color="off")

    st.subheader("Mapa de viabilidade: preço do carbono × aumento de produtividade")
    precos_grade = np.arange(0, 401, 25)
    respostas_grade = np.round(np.arange(-0.05, 0.301, 0.025), 3)
    grade = mapa_viabilidade(resultado, precos_grade, respostas_grade)
    try:
        import altair as alt
        base_g = alt.Chart(grade).encode(
            x=alt.X("preco_carbono_usd:O", title="Preço do carbono (US$/tCO₂e)"),
            y=alt.Y("resposta_media:O", title="Aumento médio de produtividade", sort="descending",
                    axis=alt.Axis(format=".1%")))
        calor = base_g.mark_rect().encode(
            color=alt.Color("prob_viavel:Q", title="P(VPL>0)", scale=alt.Scale(scheme="redyellowgreen", domain=[0, 1])),
            tooltip=[alt.Tooltip("preco_carbono_usd", title="US$/t"),
                     alt.Tooltip("resposta_media", title="Aumento", format=".1%"),
                     alt.Tooltip("prob_viavel", title="P(VPL>0)", format=".0%")])
        rotulos = base_g.mark_text(fontSize=10).encode(text=alt.Text("prob_viavel:Q", format=".0%"))
        st.altair_chart(calor + rotulos, use_container_width=True)
    except ImportError:
        st.dataframe(grade.pivot(index="resposta_media", columns="preco_carbono_usd", values="prob_viavel")
                     .sort_index(ascending=False), use_container_width=True)
    st.caption(f"Cada célula usa as mesmas simulações (clima, preços da cultura, emissão do crédito e variação entre "
               f"talhões), trocando só o preço do carbono e o aumento médio esperado. "
               f"Ponto atual: aumento de {pctbr(res['resposta_media_usada'], 1)} e carbono entre US$ {pc_min} e {pc_max}/t.")

with aba_r:
    st.subheader("Onde o biocarvão rende mais no Paraná e em Santa Catarina")
    perfis_all = carregar_perfis_app()
    if perfis_all is None:
        st.warning("Arquivo perfis_bdsolos_0_20.csv não encontrado.")
    else:
        r1, r2, r3 = st.columns(3)
        ufs_r = r1.multiselect("Estados", ["PR", "SC"], default=["PR", "SC"])
        min_p = r2.slider("Mínimo de perfis por município", 1, 20, 3)
        criterio = r3.selectbox("Ordenar por", ["indice_combinado", "aumento_t_ha_ano1", "incremento_c_pct",
                                                "prob_vpl_com_carbono", "prob_vpl_sem_carbono"],
                                format_func={"indice_combinado": "Índice combinado (produtividade + carbono)",
                                             "aumento_t_ha_ano1": "Aumento de produtividade (t/ha)",
                                             "incremento_c_pct": "Aumento do estoque de C no solo (%)",
                                             "prob_vpl_com_carbono": "Chance de se pagar com carbono",
                                             "prob_vpl_sem_carbono": "Chance de se pagar sem carbono"}.get)
        ranking = avaliar_municipios_app(cenario.to_dict(), tuple(ufs_r), min_p)
        if ranking.empty:
            st.info("Nenhum município com perfis suficientes para os filtros escolhidos.")
        else:
            ranking = ranking.sort_values(criterio, ascending=False).reset_index(drop=True)
            top = ranking.iloc[0]
            st.markdown(
                f"**{top['municipio']} ({top['uf']})** lidera por esse critério: produtividade "
                f"+{top['aumento_pct_ano1']:.1f}% (+{top['aumento_t_ha_ano1']:.3f} t/ha no 1º ano), estoque de C do solo "
                f"+{top['incremento_c_pct']:.1f}% e chance de se pagar com carbono de {top['prob_vpl_com_carbono']:.0%}. "
                f"Avaliados {len(ranking)} municípios. Para ver um município em detalhe, use a aba **Meu município**.")
            vc = ranking["veredito"].value_counts()
            st.caption(" · ".join(f"{k}: {v}" for k, v in vc.items()))
            geo = ranking.dropna(subset=["lat", "lon"]).copy()
            if len(geo):
                geo["cor"] = cor_por_valor(geo[criterio].rank(pct=True))
                geo["tamanho"] = 2000 + 600 * geo["n_perfis"].clip(upper=30)
                st.map(geo, latitude="lat", longitude="lon", color="cor", size="tamanho")
                st.caption(f"Cor: posição no critério escolhido (verde = melhor). Tamanho: nº de perfis. "
                           f"{len(geo)} de {len(ranking)} municípios têm coordenadas nos perfis.")
            st.dataframe(
                ranking.assign(prob_vpl_sem_carbono=100 * ranking["prob_vpl_sem_carbono"],
                               prob_vpl_com_carbono=100 * ranking["prob_vpl_com_carbono"])[["municipio", "uf", "veredito", "aumento_pct_ano1", "aumento_t_ha_ano1", "ganho_r_ha_ano_medio",
                         "c_retido_tc_ha", "incremento_c_pct", "credito_tco2e_ha", "prob_vpl_sem_carbono",
                         "prob_vpl_com_carbono", "n_perfis", "classe_solo_predominante", "argila_mediana_pct",
                         "c_org_mediano_gkg"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "municipio": "Município", "uf": "UF", "veredito": "Veredito",
                    "aumento_pct_ano1": st.column_config.NumberColumn("Produtividade (+% 1º ano)", format="%.1f"),
                    "aumento_t_ha_ano1": st.column_config.NumberColumn("Produtividade (+t/ha 1º ano)", format="%.3f"),
                    "ganho_r_ha_ano_medio": st.column_config.NumberColumn("Ganho médio (R$/ha/ano)", format="%.0f"),
                    "c_retido_tc_ha": st.column_config.NumberColumn("C retido no solo (t C/ha)", format="%.2f"),
                    "incremento_c_pct": st.column_config.NumberColumn("Estoque de C do solo (+%)", format="%.1f"),
                    "credito_tco2e_ha": st.column_config.NumberColumn("Crédito (tCO₂e/ha)", format="%.2f"),
                    "prob_vpl_sem_carbono": st.column_config.ProgressColumn("Se paga sem carbono", min_value=0, max_value=100, format="%.0f%%"),
                    "prob_vpl_com_carbono": st.column_config.ProgressColumn("Se paga com carbono", min_value=0, max_value=100, format="%.0f%%"),
                    "n_perfis": "Perfis de solo", "classe_solo_predominante": "Solo predominante",
                    "argila_mediana_pct": st.column_config.NumberColumn("Argila (%)", format="%.0f"),
                    "c_org_mediano_gkg": st.column_config.NumberColumn("C org. do solo (g/kg)", format="%.1f"),
                })
            st.download_button("Baixar ranking (CSV)", ranking.to_csv(index=False).encode("utf-8"),
                               "ranking_municipios_pr_sc.csv", "text/csv")
            st.caption("Usa os parâmetros da barra lateral (biocarvão, cultura, empréstimo, carbono, correção de manejo). "
                       "Incremento de C = C aplicado pelo biocarvão ÷ estoque nativo 0–20 cm. Perfis do BDsolos são "
                       "antigos e poucos em vários municípios: use o ranking para priorizar onde amostrar e fazer "
                       "ensaios, não como resultado final.")

with aba1:
    lo = min(df["vpl_sem_carbono"].quantile(0.01), df["vpl_com_carbono"].quantile(0.01))
    hi = max(df["vpl_sem_carbono"].quantile(0.99), df["vpl_com_carbono"].quantile(0.99))
    bordas = np.linspace(lo, hi, 41)
    centros = (bordas[:-1] + bordas[1:]) / 2
    hist = pd.DataFrame({
        "VPL (R$ mil)": np.round(centros / 1000, 1),
        "Sem carbono": np.histogram(df["vpl_sem_carbono"], bordas)[0],
        "Com carbono": np.histogram(df["vpl_com_carbono"], bordas)[0],
    }).set_index("VPL (R$ mil)")
    st.bar_chart(hist, stack=False)
    p = res
    st.markdown(
        f"VPL sem carbono — P10 {brl(p['vpl_sem_carbono_p10_p50_p90'][0])}, "
        f"P50 {brl(p['vpl_sem_carbono_p10_p50_p90'][1])}, P90 {brl(p['vpl_sem_carbono_p10_p50_p90'][2])}  \n"
        f"VPL com carbono — P10 {brl(p['vpl_com_carbono_p10_p50_p90'][0])}, "
        f"P50 {brl(p['vpl_com_carbono_p10_p50_p90'][1])}, P90 {brl(p['vpl_com_carbono_p10_p50_p90'][2])}"
    )

with aba2:
    parcelas = pd.DataFrame({"Ano": range(len(res["parcelas_r"])), "Parcela (R$)": res["parcelas_r"]})
    st.bar_chart(parcelas.set_index("Ano"))
    st.write(f"Principal financiado via P2P: **{brl(res['principal_p2p_r'])}** · "
             f"DSCR mínimo mediano: **{res['dscr_min_mediano']:.2f}**")

with aba3:
    opcoes = {
        "Preço máx. do carbono (US$/t)": ("carbono.preco_max_usd_t", np.linspace(pc_min + 10, 500, 8)),
        "Dose (t/ha)": ("biocarvao.dose_t_ha", np.linspace(0.5, 10, 8)),
        "Custo efetivo anual P2P": ("emprestimo.taxa_anual", np.linspace(0.08, 0.40, 8)),
        "Preço do biocarvão (R$/t)": ("biocarvao.preco_r_t", np.linspace(400, 3000, 8)),
        "Prazo (anos)": ("emprestimo.prazo_anos", np.arange(2, 11)),
    }
    escolha = st.selectbox("Parâmetro", list(opcoes))
    if st.button("Rodar sensibilidade"):
        caminho, valores = opcoes[escolha]
        cen_sens = Cenario(**{k: v for k, v in vars(cenario).items()})
        cen_sens.simulacao = ParametrosSimulacao(**{**vars(cenario.simulacao), "n_simulacoes": 3_000})
        valores = [int(x) for x in valores] if caminho.endswith("prazo_anos") else [float(x) for x in valores]
        tab = analise_sensibilidade(cen_sens, caminho, valores, perfis_sel)
        st.line_chart(tab.set_index(caminho)[["P(VPL>0) sem carbono", "P(VPL>0) com carbono", "Prob. inadimplência"]])
        st.dataframe(tab, use_container_width=True)

with aba4:
    if perfis_sel is not None and len(perfis_sel):
        st.markdown("**Camada 0–20 cm dos perfis selecionados** (P10, mediana, P90)")
        st.dataframe(resumo_perfis(perfis_sel).round(2), use_container_width=True)
        geo = perfis_sel.dropna(subset=["lat", "lon"])
        if len(geo):
            st.map(geo[["lat", "lon"]])
        st.caption(f"{len(geo)} de {len(perfis_sel)} perfis com coordenadas. Densidade medida em "
                   f"{perfis_sel['ds_medida'].mean():.0%} dos perfis; demais estimadas por pedotransferência.")
        cols_v = ["municipio", "classe_n1", "uso", "ano_coleta", "ph", "v_pct", "argila_pct",
                  "c_org_gkg", "estoque_c_0_20_tha", "link"]
        st.dataframe(perfis_sel[cols_v], use_container_width=True,
                     column_config={"link": st.column_config.LinkColumn("Descrição (PDF)")})
    else:
        st.write("Ative o BDsolos na barra lateral para ver os perfis.")

with aba5:
    st.dataframe(df.describe().T, use_container_width=True)
    st.download_button("Baixar simulações (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "simulacoes_biocredito.csv", "text/csv")
    st.json(cenario.to_dict(), expanded=False)
