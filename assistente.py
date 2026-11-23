"""
Assistente de decisão do BioCrédito Agro: lógica sem Streamlit.

- montar_cenario: cenário padrão a partir de 3 respostas (cultura, adubação, biocarvão).
- perfil_talhao: transforma a análise de solo do talhão em um "perfil" no formato do BDsolos.
- avaliar: resultado em linguagem simples (semáforo, explicação, o que mudaria, confiança).
- limiares: preço máximo do biocarvão, juros máximos e preço mínimo de carbono para P(VPL>0) >= limiar.
- gerar_pdf: relatório de uma página.
- precalcular / carregar_precalculado: cenários pré-calculados para resposta instantânea.
"""

from __future__ import annotations

import copy
import io
from datetime import date
from pathlib import Path

import pandas as pd

from regioes import avaliar_municipios, detalhar_municipio
from simulador import CULTURAS, Cenario, simular
from validacao import PRESETS_BIOCARVAO

BIOCARVOES = {
    "verde": "Resíduo agrícola verde ≥ 500 °C (Al-Gaashani 2026)",
    "lenhoso": "Madeira/lenhoso ≥ 500 °C (Al-Gaashani 2026)",
    "lodo": "Lodo de esgoto 500 °C (Chagas 2024)",
}
CULTURAS_ASSIST = ["soja", "milho", "feijão", "milho safrinha", "trigo"]
ADUBACOES = ["completa", "sem_adubacao"]
LIMIAR = 0.70
ARQ_PRE = Path(__file__).with_name("precalculado.csv")

TXT = {
    "pt": {
        "verde": "Rico em nutrientes e certificável (resíduo agrícola verde, ≥ 500 °C)",
        "lenhoso": "Madeira (≥ 500 °C)",
        "lodo": "Lodo de esgoto (não gera crédito de carbono)",
        "completa": "Aduba completo (NPK todo ano)",
        "sem_adubacao": "Pouco ou nada (área degradada ou de baixo insumo)",
        "verde_sem": "Vale a pena", "amarelo_sem": "Depende das condições", "vermelho_sem": "Não vale agora",
        "conf_alta": "Alta", "conf_media": "Média", "conf_baixa": "Baixa",
        "conf_talhao": "Alta: baseada na análise de solo do seu talhão.",
        "conf_n": "{nivel}: baseada em {n} perfil(is) de solo do município (BDsolos).",
        "conf_dica": " Para mais precisão, informe a análise de solo do seu talhão.",
        "e_solo_corrigido": "O solo já tem pH {ph}: há pouca acidez para o biocarvão corrigir.",
        "e_solo_acido": "O solo é ácido (pH {ph}), condição em que o biocarvão mais aumenta a produtividade.",
        "e_solo_medio": "O solo é moderadamente ácido (pH {ph}): o biocarvão ainda ajuda, mas menos do que em solos mais ácidos.",
        "m_sem_carbono": "Continua viável mesmo sem crédito de carbono.",
        "e_adubo": "Como a área já recebe adubação completa, o biocarvão acrescenta pouca produtividade (+{aum}% no 1º ano).",
        "e_sem_adubo": "Sem adubação, o biocarvão aumenta a produtividade em +{aum}% no 1º ano.",
        "e_inelegivel": "Este biocarvão não atende à norma de certificação: não gera crédito de carbono.",
        "e_credito": "Gera {cred} tCO₂e/ha de crédito de carbono.",
        "e_carbono_decide": "O crédito de carbono é o que viabiliza: sem ele, a chance de pagar cai de {pc}% para {ps}%.",
        "e_so_prod": "Só o ganho de produtividade já paga o investimento ({ps}% de chance).",
        "m_preco_folga": "O investimento continua valendo a pena com o biocarvão até R$ {v}/t (hoje R$ {a}/t).",
        "m_preco_precisa": "Ficaria viável com o biocarvão a até R$ {v}/t (hoje R$ {a}/t).",
        "m_juros_folga": "Aguenta juros de até {v}% ao ano (hoje {a}%).",
        "m_juros_precisa": "Ficaria viável com juros de até {v}% ao ano (hoje {a}%).",
        "m_carbono_precisa": "Ficaria viável com carbono a partir de US$ {v}/t (hoje US$ {a1}–{a2}/t).",
        "m_carbono_folga": "Continua viável mesmo com carbono a US$ {v}/t.",
        "m_inalcancavel": "{o} sozinho não torna viável.",
        "o_preco": "Baixar o preço do biocarvão", "o_juros": "Baixar os juros", "o_carbono": "Subir o preço do carbono",
        "frase_prob": "Em {p} de cada 100 cenários simulados, o investimento se paga.",
    },
    "en": {
        "verde": "Nutrient-rich and certifiable (green crop residue, ≥ 500 °C)",
        "lenhoso": "Wood (≥ 500 °C)",
        "lodo": "Sewage sludge (no carbon credit)",
        "completa": "Full fertilisation (NPK every year)",
        "sem_adubacao": "Little or none (degraded or low-input land)",
        "verde_sem": "Worth it", "amarelo_sem": "Depends on conditions", "vermelho_sem": "Not worth it now",
        "conf_alta": "High", "conf_media": "Medium", "conf_baixa": "Low",
        "conf_talhao": "High: based on your field's soil analysis.",
        "conf_n": "{nivel}: based on {n} soil profile(s) of the municipality (BDsolos).",
        "conf_dica": " For more precision, enter your field's soil analysis.",
        "e_solo_corrigido": "The soil already has pH {ph}: there is little acidity for biochar to correct.",
        "e_solo_acido": "The soil is acid (pH {ph}), where biochar raises yield the most.",
        "e_solo_medio": "The soil is moderately acid (pH {ph}): biochar still helps, but less than in more acid soils.",
        "m_sem_carbono": "It stays viable even without carbon credit.",
        "e_adubo": "Because the field already receives full fertilisation, biochar adds little yield (+{aum}% in year 1).",
        "e_sem_adubo": "Without fertilisation, biochar raises yield by +{aum}% in year 1.",
        "e_inelegivel": "This biochar does not meet the certification standard: it generates no carbon credit.",
        "e_credito": "It generates {cred} tCO₂e/ha of carbon credit.",
        "e_carbono_decide": "The carbon credit makes it viable: without it, the chance of paying off falls from {pc}% to {ps}%.",
        "e_so_prod": "The yield gain alone pays for the investment ({ps}% chance).",
        "m_preco_folga": "It stays worthwhile with biochar up to R$ {v}/t (now R$ {a}/t).",
        "m_preco_precisa": "It would be viable with biochar up to R$ {v}/t (now R$ {a}/t).",
        "m_juros_folga": "It withstands interest up to {v}% a year (now {a}%).",
        "m_juros_precisa": "It would be viable with interest up to {v}% a year (now {a}%).",
        "m_carbono_precisa": "It would be viable with carbon from US$ {v}/t (now US$ {a1}–{a2}/t).",
        "m_carbono_folga": "It stays viable even with carbon at US$ {v}/t.",
        "m_inalcancavel": "{o} alone does not make it viable.",
        "o_preco": "Lowering the biochar price", "o_juros": "Lowering interest", "o_carbono": "Raising the carbon price",
        "frase_prob": "In {p} of every 100 simulated scenarios, the investment pays off.",
    },
}


def _n(x: float, dec: int = 0, lang: str = "pt") -> str:
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".") if lang == "pt" else s


def montar_cenario(cultura: str = "soja", adubacao: str = "sem_adubacao", biocarvao: str = "verde",
                   base: Cenario | None = None, n_simulacoes: int = 5000) -> Cenario:
    """Cenário padrão do assistente: dose 2 t/ha, correção com calcário, preço SBCE (Tabela 3)."""
    c = copy.deepcopy(base) if base is not None else Cenario()
    if base is None:
        c.solo.ph_min_manejo, c.solo.v_min_manejo = 5.5, 60
        c.biocarvao.dose_t_ha = 2.0
        c.carbono.preco_min_usd_t, c.carbono.preco_max_usd_t = 96.0, 144.0
    k = CULTURAS[cultura]
    c.cultura.cultura = cultura
    c.cultura.produtividade_base_t_ha = k["produtividade_t_ha"]
    c.cultura.preco_cultura_r_t = k["preco_r_t"]
    c.cultura.preco_cultura_cv = k["cv_preco"]
    c.cultura.margem_base_r_ha = k["margem_r_ha"]
    c.cultura.fator_resposta_cultura = k["fator_resposta"]
    c.resposta.manejo_adubacao = adubacao
    pre = PRESETS_BIOCARVAO[BIOCARVOES[biocarvao]]
    for a in ("c_org_frac", "h_c_org", "o_c_org", "tipo"):
        setattr(c.biocarvao, a, pre[a])
    c.simulacao.n_simulacoes = n_simulacoes
    return c


def perfil_talhao(ph: float, v_pct: float, argila_pct: float, c_org_gkg: float, ds_gcm3: float = 1.3,
                  uf: str = "XX", municipio: str = "Meu talhão") -> pd.DataFrame:
    """Converte a análise de solo do talhão (0–20 cm) em um perfil no formato do BDsolos."""
    estoque = c_org_gkg * ds_gcm3 * 20 / 10  # g/kg × g/cm³ × 20 cm → t C/ha
    return pd.DataFrame([{
        "id_perfil": "talhao", "uf": uf, "municipio": municipio, "municipio_chave": municipio.upper(),
        "lat": float("nan"), "lon": float("nan"), "ano_coleta": date.today().year, "classe_n1": "TALHÃO",
        "classe_n2": "", "classe_atual": "", "uso": "", "uso_agricola": True, "link": "",
        "ph": ph, "v_pct": v_pct, "argila_pct": argila_pct, "c_org_gkg": c_org_gkg, "ctc_cmolc": float("nan"),
        "m_al_pct": float("nan"), "p_mgkg": float("nan"), "ds_gcm3": ds_gcm3, "ds_medida": False,
        "estoque_c_0_20_tha": estoque, "prof_coberta_cm": 20.0}])


def _p(c: Cenario, perfis_g: pd.DataFrame) -> float:
    return float(simular(c, perfis_g)["resumo"]["prob_vpl_pos_com_carbono"])


def _bissecao(c0, perfis_g, aplicar, lo, hi, crescente: bool, limiar=LIMIAR, it=10):
    """Acha o valor-limite em [lo, hi]. crescente=True: P sobe com o valor (busca o mínimo viável)."""
    def ok(v):
        c = copy.deepcopy(c0)
        aplicar(c, v)
        return _p(c, perfis_g) >= limiar
    if crescente:
        if not ok(hi):
            return None
        for _ in range(it):
            m = (lo + hi) / 2
            lo, hi = (lo, m) if ok(m) else (m, hi)
        return hi
    if not ok(lo):
        return None
    for _ in range(it):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if ok(m) else (lo, m)
    return lo


def limiares(c: Cenario, perfis_g: pd.DataFrame, n_simulacoes: int = 2000) -> dict:
    c0 = copy.deepcopy(c)
    c0.simulacao.n_simulacoes = n_simulacoes

    def set_preco(cc, v):
        cc.biocarvao.preco_r_t = v

    def set_juros(cc, v):
        cc.emprestimo.taxa_anual = v

    def set_carb(cc, v):
        cc.carbono.preco_min_usd_t = cc.carbono.preco_max_usd_t = v

    return {
        "preco_biocarvao_max": _bissecao(c0, perfis_g, set_preco, 0.0, 6000.0, crescente=False),
        "juros_max": _bissecao(c0, perfis_g, set_juros, 0.0, 0.80, crescente=False),
        "carbono_min": _bissecao(c0, perfis_g, set_carb, 0.0, 1000.0, crescente=True),
    }


def semaforo(p_com: float, limiar: float = LIMIAR) -> str:
    if p_com >= limiar:
        return "verde"
    if p_com >= limiar - 0.20:
        return "amarelo"
    return "vermelho"


def confianca(n_perfis: int, talhao: bool) -> str:
    if talhao:
        return "alta"
    if n_perfis >= 10:
        return "alta"
    if n_perfis >= 3:
        return "media"
    return "baixa"


def avaliar(c: Cenario, perfis: pd.DataFrame, uf: str, municipio: str, talhao: pd.DataFrame | None = None,
            lang: str = "pt", com_limiares: bool = True) -> dict:
    """Resultado completo em linguagem simples para um município (ou para o talhão informado)."""
    t = TXT[lang]
    base_perfis = perfis
    if talhao is not None:
        talhao = talhao.copy()
        talhao["uf"], talhao["municipio"] = uf, municipio
        base_perfis = pd.concat([perfis[perfis.uf == uf], talhao], ignore_index=True)
        base_perfis = base_perfis[(base_perfis.municipio != municipio) | (base_perfis.id_perfil == "talhao")]
    d = detalhar_municipio(c, base_perfis, uf, municipio)
    r = d["resumo"]
    ps, pc = 100 * d["prob_vpl_sem_carbono"], 100 * d["prob_vpl_com_carbono"]
    N = lambda x, dec=0: _n(x, dec, lang)  # noqa: E731
    g = base_perfis[(base_perfis.uf == uf) & (base_perfis.municipio == municipio)]
    ph = float(g["ph"].median())
    expl = []
    chave_solo = "e_solo_corrigido" if ph >= 6.0 else ("e_solo_acido" if ph < 5.5 else "e_solo_medio")
    expl.append(t[chave_solo].format(ph=N(ph, 1)))
    expl.append(t["e_adubo" if c.resposta.manejo_adubacao == "completa" else "e_sem_adubo"].format(aum=N(d["aumento_pct_ano1"], 1)))
    expl.append(t["e_credito"].format(cred=N(d["credito_tco2e_ha"], 1)) if d["gera_credito"] else t["e_inelegivel"])
    if ps / 100 >= LIMIAR:
        expl.append(t["e_so_prod"].format(ps=N(ps)))
    elif pc / 100 >= LIMIAR:
        expl.append(t["e_carbono_decide"].format(pc=N(pc), ps=N(ps)))

    mudaria = []
    lim = {}
    if com_limiares:
        lim = limiares(c, g)
        viavel = pc / 100 >= LIMIAR
        a_preco, a_juros = c.biocarvao.preco_r_t, c.emprestimo.taxa_anual
        if lim["preco_biocarvao_max"] is None:
            mudaria.append(t["m_inalcancavel"].format(o=t["o_preco"]))
        else:
            mudaria.append(t["m_preco_folga" if viavel else "m_preco_precisa"].format(v=N(lim["preco_biocarvao_max"]), a=N(a_preco)))
        if lim["juros_max"] is None:
            mudaria.append(t["m_inalcancavel"].format(o=t["o_juros"]))
        else:
            mudaria.append(t["m_juros_folga" if viavel else "m_juros_precisa"].format(v=N(100 * lim["juros_max"]), a=N(100 * a_juros)))
        if d["gera_credito"]:
            if lim["carbono_min"] is None:
                mudaria.append(t["m_inalcancavel"].format(o=t["o_carbono"]))
            elif lim["carbono_min"] < 5:
                mudaria.append(t["m_sem_carbono"])
            elif viavel:
                mudaria.append(t["m_carbono_folga"].format(v=N(lim["carbono_min"])))
            else:
                mudaria.append(t["m_carbono_precisa"].format(v=N(lim["carbono_min"]), a1=N(c.carbono.preco_min_usd_t),
                                                             a2=N(c.carbono.preco_max_usd_t)))
    nivel = confianca(d["n_perfis"], talhao is not None)
    if talhao is not None:
        conf_txt = t["conf_talhao"]
    else:
        conf_txt = t["conf_n"].format(nivel=t["conf_" + nivel], n=d["n_perfis"]) + (t["conf_dica"] if nivel != "alta" else "")
    sem = semaforo(d["prob_vpl_com_carbono"])
    return {
        "uf": uf, "municipio": municipio, "cultura": c.cultura.cultura, "adubacao": c.resposta.manejo_adubacao,
        "semaforo": sem, "rotulo": t[sem + "_sem"], "frase_prob": t["frase_prob"].format(p=N(pc)),
        "p_com": d["prob_vpl_com_carbono"], "p_sem": d["prob_vpl_sem_carbono"],
        "aumento_pct": d["aumento_pct_ano1"], "aumento_t_ha": d["aumento_t_ha_ano1"],
        "credito_tco2e_ha": d["credito_tco2e_ha"], "gera_credito": d["gera_credito"],
        "custo_r_ha": d["custo_inicial_r_ha"],
        "retorno_liquido_r_ha": (r["vp_produtividade_mediano_r"] + r["vp_economia_insumos_r"]
                                 + r["vp_carbono_mediano_r"] - r["vp_custos_r"]) / c.cultura.area_ha,
        "ph": ph, "n_perfis": d["n_perfis"], "talhao": talhao is not None,
        "explicacao": expl, "mudaria": mudaria, "limiares": lim,
        "confianca": nivel, "confianca_txt": conf_txt, "anual": d["anual"],
    }


# ------------------------------------------------------------------ relatório PDF
def gerar_pdf(res: dict, lang: str = "pt") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    L = {
        "pt": {"tit": "BioCrédito Agro — relatório de viabilidade do biocarvão", "loc": "Local", "cult": "Cultura",
               "adub": "Adubação", "res": "Resultado", "num": "Números principais", "aum": "Aumento de produtividade (1º ano)",
               "cred": "Crédito de carbono", "custo": "Custo inicial", "ret": "Retorno líquido em 8 anos (mediana)",
               "pq": "Por que", "mud": "O que mudaria o resultado", "conf": "Confiança", "data": "Gerado em",
               "aviso": "Simulação baseada em dados públicos (BDsolos/Embrapa) e na literatura; não substitui ensaio de campo, "
                        "análise de crédito nem certificação. Preço de carbono: cenário SBCE do artigo (US$ 96–144/t)."},
        "en": {"tit": "BioCrédito Agro — biochar viability report", "loc": "Location", "cult": "Crop",
               "adub": "Fertilisation", "res": "Result", "num": "Key numbers", "aum": "Yield increase (year 1)",
               "cred": "Carbon credit", "custo": "Upfront cost", "ret": "Net return over 8 years (median)",
               "pq": "Why", "mud": "What would change the result", "conf": "Confidence", "data": "Generated on",
               "aviso": "Simulation based on public data (BDsolos/Embrapa) and the literature; it does not replace field trials, "
                        "credit analysis or certification. Carbon price: the paper's SBCE scenario (US$ 96–144/t)."},
    }[lang]
    t = TXT[lang]
    cor = {"verde": "#2f855a", "amarelo": "#b45309", "vermelho": "#b91c1c"}[res["semaforo"]]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=44, bottomMargin=40)
    h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=8)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=3)
    b = ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13)
    sm = ParagraphStyle("s", fontName="Helvetica-Oblique", fontSize=7.8, leading=10, textColor=colors.HexColor("#555555"))
    big = ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor(cor))

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("₂", "2")

    cult = res["cultura"] if lang == "pt" else {"soja": "soybean", "milho": "maize", "feijão": "common bean",
                                                 "milho safrinha": "second-crop maize", "trigo": "wheat"}.get(res["cultura"], res["cultura"])
    story = [Paragraph(esc(L["tit"]), h),
             Paragraph(f"<b>{L['loc']}:</b> {esc(res['municipio'])} ({esc(res['uf'])}) &nbsp; <b>{L['cult']}:</b> {esc(cult)} "
                       f"&nbsp; <b>{L['adub']}:</b> {esc(t[res['adubacao']])}", b),
             Spacer(1, 8), Paragraph(esc(res["rotulo"]), big), Paragraph(esc(res["frase_prob"]), b),
             Paragraph(L["num"], h2)]
    fmt = (lambda x: f"{x:,.0f}".replace(",", ".")) if lang == "pt" else (lambda x: f"{x:,.0f}")
    linhas = [[L["aum"], f"+{_n(res['aumento_pct'], 1, lang)}% (+{_n(res['aumento_t_ha'], 2, lang)} t/ha)"],
              [L["cred"], f"{_n(res['credito_tco2e_ha'], 2, lang)} tCO2e/ha" if res["gera_credito"] else "—"],
              [L["custo"], f"R$ {fmt(res['custo_r_ha'])}/ha"],
              [L["ret"], f"R$ {fmt(res['retorno_liquido_r_ha'])}/ha"]]
    tb = Table(linhas, colWidths=[230, 260])
    tb.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9.5), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [tb, Paragraph(L["pq"], h2)] + [Paragraph("• " + esc(x), b) for x in res["explicacao"]]
    if res["mudaria"]:
        story += [Paragraph(L["mud"], h2)] + [Paragraph("• " + esc(x), b) for x in res["mudaria"]]
    story += [Paragraph(L["conf"], h2), Paragraph(esc(res["confianca_txt"]), b), Spacer(1, 14),
              Paragraph(esc(L["aviso"]), sm), Paragraph(f"{L['data']} {date.today().isoformat()}", sm)]
    doc.build(story)
    return buf.getvalue()


# ------------------------------------------------------------------ cenários pré-calculados
def precalcular(perfis: pd.DataFrame, n_simulacoes: int = 5000, min_perfis: int = 3, arquivo: Path = ARQ_PRE) -> pd.DataFrame:
    ufs = tuple(sorted(perfis.uf.dropna().unique()))
    partes = []
    for cult in ["soja", "milho", "feijão"]:
        for adub in ADUBACOES:
            for bio in BIOCARVOES:
                c = montar_cenario(cult, adub, bio)
                r = avaliar_municipios(c, perfis, ufs=ufs, min_perfis=min_perfis, n_simulacoes=n_simulacoes)
                r = r[["uf", "municipio", "lat", "lon", "n_perfis", "ph_mediano", "aumento_pct_ano1",
                       "credito_tco2e_ha", "prob_vpl_sem_carbono", "prob_vpl_com_carbono"]].copy()
                r["cultura"], r["adubacao"], r["biocarvao"] = cult, adub, bio
                partes.append(r)
    df = pd.concat(partes, ignore_index=True).round(3)
    df.to_csv(arquivo, index=False)
    return df


def carregar_precalculado(arquivo: Path = ARQ_PRE) -> pd.DataFrame | None:
    return pd.read_csv(arquivo) if arquivo.exists() else None


def consulta_rapida(pre: pd.DataFrame | None, uf, municipio, cultura, adubacao, biocarvao):
    if pre is None:
        return None
    x = pre[(pre.uf == uf) & (pre.municipio == municipio) & (pre.cultura == cultura)
            & (pre.adubacao == adubacao) & (pre.biocarvao == biocarvao)]
    return None if x.empty else x.iloc[0].to_dict()


if __name__ == "__main__":
    from bdsolos import carregar_perfis
    df = precalcular(carregar_perfis(Path(__file__).with_name("perfis_bdsolos_0_20.csv")))
    print(len(df), "linhas gravadas em", ARQ_PRE)
