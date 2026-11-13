"""
BioCrédito Agro — Simulador de benefícios do biocarvão financiado por P2P lending.

Núcleo de cálculo independente de interface (pode ser importado no Streamlit,
em notebooks ou em scripts). Implementa os três módulos do framework:

  1. Agronômico:   ΔB_agro,t = Y0 · r_t · P_cult + S_cal,t + S_fert,t − C_apl,t
  2. Carbono:      CO2e_liq  = M_bc · C_org · F_perm(H/Corg, T_solo) · 44/12 − E_ACV
  3. Financeiro:   VPL = Σ (ΔB_agro,t + R_CO2,t − A_t) / (1+i)^t
                   + risco do investidor P2P (prob. de inadimplência, perda esperada)

Tudo é rodado por Monte Carlo: o resultado é uma distribuição, não um número.

ATENÇÃO: os valores padrão são ilustrativos. Calibre com os laudos e ensaios
das cooperativas e com a tabela de permanência da metodologia de certificação
escolhida (EBC/WBC, Puro.earth, Verra VM0044, Isometric).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------

@dataclass
class ParametrosSolo:
    ph_agua: float = 5.4          # pH em água do talhão
    v_pct: float = 50.0           # saturação por bases (%)
    argila_pct: float = 45.0      # teor de argila (%)
    c_org_gkg: Optional[float] = None  # carbono orgânico 0–20 cm (g/kg); None = neutro
    temperatura_solo_c: float = 21.0  # temperatura média anual do solo (°C)
    # Correção de manejo: perfis do BDsolos são, em geral, de solo nativo/pastagem.
    # Em lavoura corrigida, pH e V% atuais ficam pelo menos nestes valores. None = sem correção.
    ph_min_manejo: Optional[float] = None
    v_min_manejo: Optional[float] = None


CLASSES_SAUDE = ["saudavel", "recuperando", "intermediario", "adoecendo", "doente"]


@dataclass
class ParametrosSaudeSolo:
    """Indicadores da Plataforma Saúde do Solo BR / tecnologia BioAS (Embrapa).

    fonte:
      "nenhuma"   -> não usa
      "municipio" -> classe de saúde predominante (moda) do município na plataforma pública
      "laudo"     -> laudo BioAS do talhão: F1 (ciclar), F2 (armazenar), F3 (suprir), escores 0–1
    """
    fonte: str = "nenhuma"
    classe_saude: str = "intermediario"
    n_amostras_municipio: int = 0
    f1_ciclar: Optional[float] = None
    f2_armazenar: Optional[float] = None
    f3_suprir: Optional[float] = None
    iqs_fertbio: Optional[float] = None


@dataclass
class ParametrosBiocarvao:
    dose_t_ha: float = 2.0        # biocarvão seco aplicado (t/ha)
    preco_r_t: float = 1200.0     # preço FOB do fornecedor (R$/t)
    frete_r_t: float = 150.0      # frete até a propriedade (R$/t)
    c_org_frac: float = 0.70      # carbono orgânico (fração da massa seca)
    h_c_org: float = 0.40         # razão molar H/Corg
    o_c_org: float = 0.15         # razão molar O/Corg
    tipo: str = "estrutural"      # "estrutural" (madeira, palha) ou "nutriente" (esterco, lodo)
    e_acv_tco2e_t: float = 0.25   # emissões de ciclo de vida por t de biocarvão (tCO2e/t) — ilustrativo


# Valores de REFERÊNCIA APROXIMADOS para preencher o app; substitua por dados da
# cooperativa, CONAB ou CEPEA. "fator_resposta" multiplica a resposta relativa ao
# biocarvão; fica em 1,0 até haver ensaios por cultura que justifiquem outro valor.
CULTURAS = {
    "soja":           {"produtividade_t_ha": 3.6,  "preco_r_t": 2000.0, "cv_preco": 0.15, "margem_r_ha": 1500.0, "fator_resposta": 1.0},
    "milho":          {"produtividade_t_ha": 6.0,  "preco_r_t": 1000.0, "cv_preco": 0.20, "margem_r_ha": 1200.0, "fator_resposta": 1.0},
    "milho safrinha": {"produtividade_t_ha": 5.5,  "preco_r_t": 1000.0, "cv_preco": 0.20, "margem_r_ha": 800.0,  "fator_resposta": 1.0},
    "trigo":          {"produtividade_t_ha": 3.0,  "preco_r_t": 1300.0, "cv_preco": 0.20, "margem_r_ha": 500.0,  "fator_resposta": 1.0},
    "feijão":         {"produtividade_t_ha": 1.8,  "preco_r_t": 4500.0, "cv_preco": 0.30, "margem_r_ha": 1500.0, "fator_resposta": 1.0},
    "arroz irrigado": {"produtividade_t_ha": 8.0,  "preco_r_t": 1300.0, "cv_preco": 0.20, "margem_r_ha": 1500.0, "fator_resposta": 1.0},
    "cana-de-açúcar": {"produtividade_t_ha": 75.0, "preco_r_t": 150.0,  "cv_preco": 0.15, "margem_r_ha": 1500.0, "fator_resposta": 1.0},
    "personalizada":  {"produtividade_t_ha": 3.0,  "preco_r_t": 1500.0, "cv_preco": 0.20, "margem_r_ha": 1000.0, "fator_resposta": 1.0},
}


@dataclass
class ParametrosCultura:
    cultura: str = "soja"
    fator_resposta_cultura: float = 1.0      # multiplica a resposta relativa (calibrar por ensaio)
    area_ha: float = 50.0
    produtividade_base_t_ha: float = 3.6     # Y0 (ex.: soja ~60 sc/ha)
    preco_cultura_r_t: float = 2000.0        # P_cult (R$/t)
    preco_cultura_cv: float = 0.15           # coef. de variação do preço
    margem_base_r_ha: float = 1500.0         # margem líquida sem biocarvão (R$/ha/ano), usada na capacidade de pagamento
    frac_margem_comprometivel: float = 0.6   # fração da margem base que pode ir ao serviço da dívida
    custo_aplicacao_r_ha: float = 120.0      # aplicação no ano 0 (R$/ha)
    economia_calcario_r_ha_ano: float = 80.0 # S_cal (R$/ha/ano)
    economia_fert_r_ha_ano: float = 60.0     # S_fert (R$/ha/ano)
    prob_quebra_safra: float = 0.15          # probabilidade anual de evento climático adverso (ZARC)
    perda_quebra_frac: float = 0.35          # perda de produtividade quando ocorre o evento


@dataclass
class ParametrosResposta:
    """Resposta relativa de produtividade r_t (fração, ex.: 0.10 = +10%)."""
    media: Optional[float] = None   # None => sugerida a partir do solo (heurística abaixo)
    desvio: float = 0.10            # incerteza entre talhões (desvio-padrão da priori)
    ruido_anual: float = 0.05       # variação ano a ano dentro do talhão
    decaimento_anual: float = 0.10  # fração perdida por ano; Chagas et al. (2024) observaram queda a partir do 4º ano
    # Manejo de adubação do talhão: "completa" (lavoura comercial com NPK) ou "sem_adubacao"
    # (pastagem degradada, área sem fertilização). Calibrado com Chagas et al. (2024) e Latawiec et al. (2019).
    manejo_adubacao: str = "completa"
    # Dose-resposta saturante, ancorada na dose dos ensaios de campo (15 t/ha em Chagas et al. 2024 e
    # Latawiec et al. 2019). A meia-saturação é HIPÓTESE: não há ensaios com doses baixas nos artigos.
    dose_referencia_t_ha: float = 15.0
    dose_meia_saturacao_t_ha: float = 5.0
    ensaios_observados: Sequence[float] = field(default_factory=list)  # respostas medidas em ensaios (frações)
    desvio_ensaio: float = 0.08     # erro de medição de cada ensaio


@dataclass
class ParametrosCarbono:
    preco_min_usd_t: float = 100.0
    preco_max_usd_t: float = 200.0
    cambio_r_usd: float = 5.40
    taxas_frac: float = 0.25          # certificação, verificação, registro e plataforma
    prob_emissao: float = 0.85        # probabilidade de o crédito ser efetivamente emitido
    ano_recebimento: int = 1          # ano em que a receita de carbono entra
    perm_intercepto: float = 1.13     # F_perm = a − b·H/Corg (VERIFIQUE na metodologia escolhida)
    perm_inclinacao: float = 0.46
    perm_ajuste_temp_por_c: float = 0.0  # ajuste opcional por °C acima de 15 °C (negativo reduz)
    padrao: str = "EBC"               # padrão de certificação (limites em PADROES, Lin et al. 2025)
    h_c_max: float = 0.7              # usados só no padrão "personalizado" (Figura 1 do artigo GCB)
    o_c_max: float = 0.4


@dataclass
class ParametrosEmprestimo:
    frac_financiada: float = 1.0     # fração do custo inicial financiada via P2P
    taxa_anual: float = 0.18         # custo efetivo anual para o tomador
    carencia_anos: int = 1           # só juros na carência
    prazo_anos: int = 6              # prazo total (inclui carência), parcelas anuais na safra
    lgd: float = 0.45                # perda dada a inadimplência para o investidor
    tarifa_plataforma_frac: float = 0.03  # retida pela SEP sobre o principal


@dataclass
class ParametrosSimulacao:
    horizonte_anos: int = 8
    taxa_desconto_produtor: float = 0.12
    n_simulacoes: int = 10_000
    semente: Optional[int] = 42
    # Regra de decisão:
    #   "produtividade" -> aprova só se a vantagem agronômica sozinha paga (carbono = upside)
    #   "combinada"     -> soma as duas vantagens, com desconto de prudência sobre o carbono
    regra_decisao: str = "produtividade"
    desconto_carbono_decisao: float = 0.30
    limiar_prob_vpl: float = 0.70


@dataclass
class Cenario:
    solo: ParametrosSolo = field(default_factory=ParametrosSolo)
    saude: ParametrosSaudeSolo = field(default_factory=ParametrosSaudeSolo)
    biocarvao: ParametrosBiocarvao = field(default_factory=ParametrosBiocarvao)
    cultura: ParametrosCultura = field(default_factory=ParametrosCultura)
    resposta: ParametrosResposta = field(default_factory=ParametrosResposta)
    carbono: ParametrosCarbono = field(default_factory=ParametrosCarbono)
    emprestimo: ParametrosEmprestimo = field(default_factory=ParametrosEmprestimo)
    simulacao: ParametrosSimulacao = field(default_factory=ParametrosSimulacao)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Módulo agronômico
# ---------------------------------------------------------------------------

def resposta_media_vetor(ph, v, tipo: str, argila_pct=None, c_org_gkg=None) -> np.ndarray:
    """Média a priori da resposta relativa de produtividade (vetorizada, contínua).

    Âncora: +25% médio nos trópicos (Jeffery et al., 2017), via correção de acidez e
    nutrientes em solos ácidos e pobres. Fatores (HIPÓTESES a calibrar com ensaios):
      - pH e V%: menor resposta em solo já corrigido;
      - textura e C orgânico: atributos que a calagem não muda; resposta maior em solo
        arenoso e com pouco C, onde o biocarvão mais aumenta retenção de água e CTC;
      - tipo de biocarvão: "nutriente" responde mais que "estrutural".
    Valores ausentes de argila ou C contam como fator neutro (1,0).
    """
    ph = np.asarray(ph, dtype=float)
    v = np.asarray(v, dtype=float)
    f_ph = np.interp(ph, [4.5, 5.0, 5.5, 6.0, 6.5], [1.0, 0.85, 0.60, 0.35, 0.10])
    f_v = np.interp(v, [30, 40, 60, 80], [1.0, 0.90, 0.75, 0.60])
    f_arg = 1.0 if argila_pct is None else np.nan_to_num(
        np.interp(np.asarray(argila_pct, dtype=float), [10, 20, 35, 60], [1.30, 1.10, 1.00, 0.85]), nan=1.0)
    f_c = 1.0 if c_org_gkg is None else np.nan_to_num(
        np.interp(np.asarray(c_org_gkg, dtype=float), [5, 10, 20, 35], [1.20, 1.05, 0.95, 0.85]), nan=1.0)
    f_tipo = 1.3 if tipo == "nutriente" else 0.8
    return 0.25 * f_ph * f_v * f_arg * f_c * f_tipo


def aplicar_manejo(ph, v, solo: "ParametrosSolo"):
    ph = np.asarray(ph, dtype=float)
    v = np.asarray(v, dtype=float)
    if solo.ph_min_manejo is not None:
        ph = np.maximum(ph, solo.ph_min_manejo)
    if solo.v_min_manejo is not None:
        v = np.maximum(v, solo.v_min_manejo)
    return ph, v


def sugerir_resposta_media(solo: ParametrosSolo, biocarvao: ParametrosBiocarvao) -> float:
    """Heurística para a média a priori de r_t.

    Âncora: meta-análise de Jeffery et al. (2017, Environ. Res. Lett. 12:053001):
    +25% em média nos trópicos, ~0 em clima temperado; efeito via calagem e
    fertilização em solos ácidos e pobres; biocarvões de nutriente respondem mais.
    Os fatores são HIPÓTESES a calibrar com os ensaios das cooperativas.
    """
    ph, v = aplicar_manejo(solo.ph_agua, solo.v_pct, solo)
    return float(resposta_media_vetor(ph, v, biocarvao.tipo, solo.argila_pct, solo.c_org_gkg))


def ajuste_saude_solo(saude: ParametrosSaudeSolo) -> tuple[float, float]:
    """Fator multiplicativo na média de r_t e desvio extra a somar, a partir da saúde do solo.

    Lógica (HIPÓTESE a calibrar): o biocarvão acrescenta carbono estável e CTC, atuando
    sobretudo no armazenamento (F2) e, por efeito corretivo, no suprimento (F3). Logo,
    espera-se resposta maior onde F2/F3 são baixos e menor em solos já saudáveis.
    A classe municipal é a moda das amostras do município e não representa o talhão,
    por isso aumenta a incerteza, mais ainda com poucas amostras.
    """
    if saude.fonte == "laudo" and saude.f2_armazenar is not None and saude.f3_suprir is not None:
        fator = 1.0 + 0.6 * (0.6 - saude.f2_armazenar) + 0.4 * (0.6 - saude.f3_suprir)
        return float(np.clip(fator, 0.5, 1.5)), 0.0
    if saude.fonte in ("municipio", "laudo"):
        fator = {"doente": 1.30, "adoecendo": 1.15, "intermediario": 1.00,
                 "recuperando": 0.95, "saudavel": 0.80}.get(saude.classe_saude, 1.0)
        if saude.fonte == "laudo":
            return fator, 0.0
        n = max(saude.n_amostras_municipio, 1)
        desvio_extra = 0.03 + 0.10 / np.sqrt(n)
        return fator, float(desvio_extra)
    return 1.0, 0.0


def carregar_municipios(caminho_ou_arquivo) -> pd.DataFrame:
    """Lê CSV com a classe de saúde por município (preenchido a partir da plataforma pública).

    Colunas esperadas: uf, municipio, classe_saude, n_amostras
    classe_saude ∈ {saudavel, recuperando, intermediario, adoecendo, doente}
    """
    df = pd.read_csv(caminho_ou_arquivo)
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = {"uf", "municipio", "classe_saude"} - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {sorted(faltando)}")
    if "n_amostras" not in df.columns:
        df["n_amostras"] = 0
    df["classe_saude"] = (df["classe_saude"].astype(str).str.strip().str.lower()
                          .str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii"))
    invalidas = set(df["classe_saude"]) - set(CLASSES_SAUDE)
    if invalidas:
        raise ValueError(f"Classes inválidas: {sorted(invalidas)}. Use {CLASSES_SAUDE}")
    return df


def posteriori_resposta(media_priori: float, desvio_priori: float,
                        ensaios: Sequence[float], desvio_ensaio: float) -> tuple[float, float]:
    """Atualização bayesiana normal–normal da resposta média com ensaios de campo."""
    if not ensaios:
        return media_priori, desvio_priori
    n = len(ensaios)
    prec_priori = 1.0 / desvio_priori**2
    prec_dados = n / desvio_ensaio**2
    media_post = (prec_priori * media_priori + prec_dados * float(np.mean(ensaios))) / (prec_priori + prec_dados)
    desvio_post = (prec_priori + prec_dados) ** -0.5
    return media_post, desvio_post


# ---------------------------------------------------------------------------
# Módulo de carbono
# ---------------------------------------------------------------------------

# Limites de propriedades básicas por padrão, conforme a Tabela 2 de Lin et al. (2025,
# Bioresour. Technol. Rep. 29:102059). c_min = carbono total ou orgânico mínimo (fração);
# None = sem limite. O app usa o C orgânico do biocarvão como aproximação do C total.
PADROES = {
    "EBC":         {"c_min": 0.50, "h_c_max": 0.71, "o_c_max": 0.42, "nota": "C total ≥ 50%; H/Corg < 0,71; O/Corg < 0,42"},
    "IBI":         {"c_min": 0.10, "h_c_max": 0.71, "o_c_max": None, "nota": "C orgânico ≥ 10%; H/Corg ≤ 0,71"},
    "BQM":         {"c_min": 0.10, "h_c_max": 0.71, "o_c_max": None, "nota": "C orgânico ≥ 10%; H/Corg ≤ 0,71"},
    "ANZBI":       {"c_min": 0.50, "h_c_max": 0.71, "o_c_max": None, "nota": "C total > 50% e C orgânico > 30%; H/Corg ≤ 0,71"},
    "CNAIS I":     {"c_min": 0.60, "h_c_max": 0.40, "o_c_max": 0.20, "nota": "C total ≥ 60%; C fixo ≥ 50%; H/C ≤ 0,4; O/C ≤ 0,2"},
    "CNAIS II":    {"c_min": 0.30, "h_c_max": 0.75, "o_c_max": 0.40, "nota": "C total ≥ 30%; C fixo ≥ 25%; H/C ≤ 0,75; O/C ≤ 0,4"},
    "SGS":         {"c_min": 0.30, "h_c_max": 0.71, "o_c_max": None, "nota": "C orgânico 30–95% (pirólise); H/Corg ≤ 0,71"},
    "personalizado": {"c_min": None, "h_c_max": None, "o_c_max": None, "nota": "limites definidos pelo usuário"},
}

# Fator de adubação × tipo de biocarvão, calibrado com ensaios de campo (validacao.py):
#  - "completa": 0,4 — Chagas et al. (2024), milho com NPK, SSB300/SSB500 (2 casos; +2% a +11%).
#    Sem ensaio de biocarvão estrutural com NPK nos artigos: usa o mesmo valor.
#  - "sem_adubacao"/estrutural: 1,3 — Latawiec et al. (2019), Brachiaria (+27%, 1 caso).
#  - "sem_adubacao"/nutriente: 3,5 — Chagas et al. (2024), sem NPK (+42% a +50%, 2 casos):
#    o lodo rico em P age como adubo quando não há fertilização.
FATOR_ADUBACAO = {"completa": {"estrutural": 0.4, "nutriente": 0.4},
                  "sem_adubacao": {"estrutural": 1.3, "nutriente": 3.5}}


def fator_adubacao(manejo: str, tipo: str) -> float:
    return FATOR_ADUBACAO.get(manejo, FATOR_ADUBACAO["completa"]).get(tipo, 0.4)


def checar_padrao(c_org: float, h_c: float, o_c: float, padrao: str,
                  h_c_max: float = 0.7, o_c_max: float = 0.4) -> tuple[bool, list[str]]:
    """Elegibilidade do biocarvão a um padrão e os motivos de reprovação."""
    lim = dict(PADROES.get(padrao, PADROES["EBC"]))
    if padrao == "personalizado":
        lim.update(h_c_max=h_c_max, o_c_max=o_c_max)
    motivos = []
    if lim["c_min"] is not None and c_org < lim["c_min"]:
        motivos.append(f"C {c_org:.0%} < {lim['c_min']:.0%}")
    if lim["h_c_max"] is not None and h_c > lim["h_c_max"]:
        motivos.append(f"H/C {h_c:.2f} > {lim['h_c_max']}")
    if lim["o_c_max"] is not None and o_c > lim["o_c_max"]:
        motivos.append(f"O/C {o_c:.2f} > {lim['o_c_max']}")
    return not motivos, motivos


def elegivel(bc: ParametrosBiocarvao, cb: ParametrosCarbono) -> bool:
    return checar_padrao(bc.c_org_frac, bc.h_c_org, bc.o_c_org, cb.padrao, cb.h_c_max, cb.o_c_max)[0]


def fator_dose(dose_t_ha: float, referencia: float = 15.0, meia_saturacao: float = 5.0) -> float:
    """Fator de dose saturante (1,0 na dose de referência dos ensaios de campo)."""
    if dose_t_ha <= 0:
        return 0.0
    k = np.log(2) / meia_saturacao
    return float((1 - np.exp(-k * dose_t_ha)) / (1 - np.exp(-k * referencia)))


def fator_manejo_resposta(c: "Cenario") -> float:
    """Dose × adubação, aplicados à resposta heurística (não à média informada pelo usuário)."""
    rp = c.resposta
    return (fator_dose(c.biocarvao.dose_t_ha, rp.dose_referencia_t_ha, rp.dose_meia_saturacao_t_ha)
            * fator_adubacao(rp.manejo_adubacao, c.biocarvao.tipo))


def fator_permanencia(bc: ParametrosBiocarvao, cb: ParametrosCarbono, solo: ParametrosSolo) -> float:
    f = cb.perm_intercepto - cb.perm_inclinacao * bc.h_c_org
    f += cb.perm_ajuste_temp_por_c * (solo.temperatura_solo_c - 15.0)
    return float(np.clip(f, 0.0, 1.0))


def incremento_c_solo_tha(c: "Cenario") -> float:
    """Carbono do biocarvão que se espera permanecer no solo (t C/ha), elegível ou não.

    Diferente do crédito: vale também para biocarvões fora dos padrões (ex.: lodo de
    esgoto de Chagas et al. 2024, que aumentou o estoque de C mesmo com H/C > 0,7).
    """
    bc = c.biocarvao
    return bc.dose_t_ha * bc.c_org_frac * fator_permanencia(bc, c.carbono, c.solo)


def remocao_liquida_tco2e(c: Cenario) -> float:
    """CO2e líquida credível para toda a área (tCO2e). Zero se inelegível."""
    bc, cb = c.biocarvao, c.carbono
    if not elegivel(bc, cb):
        return 0.0
    massa = bc.dose_t_ha * c.cultura.area_ha
    bruto = massa * bc.c_org_frac * fator_permanencia(bc, cb, c.solo) * 44.0 / 12.0
    return max(bruto - massa * bc.e_acv_tco2e_t, 0.0)


# ---------------------------------------------------------------------------
# Módulo financeiro
# ---------------------------------------------------------------------------

def custo_inicial(c: Cenario) -> float:
    bc, cu = c.biocarvao, c.cultura
    return cu.area_ha * (bc.dose_t_ha * (bc.preco_r_t + bc.frete_r_t) + cu.custo_aplicacao_r_ha)


def cronograma_emprestimo(principal: float, e: ParametrosEmprestimo, horizonte: int) -> np.ndarray:
    """Parcelas anuais A_t (t = 1..horizonte): juros na carência, depois Price."""
    a = np.zeros(horizonte + 1)
    if principal <= 0:
        return a
    i = e.taxa_anual
    n_amort = max(e.prazo_anos - e.carencia_anos, 1)
    for t in range(1, min(e.carencia_anos, horizonte) + 1):
        a[t] = principal * i
    pmt = principal * i / (1 - (1 + i) ** -n_amort) if i > 0 else principal / n_amort
    for k in range(n_amort):
        t = e.carencia_anos + 1 + k
        if t <= horizonte:
            a[t] = pmt
    return a


def simular(c: Cenario, perfis: Optional[pd.DataFrame] = None) -> dict:
    """Roda o Monte Carlo e devolve resumo + DataFrame por simulação.

    perfis: tabela de perfis de solo (ex.: BDsolos já filtrado, colunas 'ph' e 'v_pct').
            Se informada, cada simulação sorteia um perfil e a média a priori de r_t
            é calculada a partir dele, propagando a variabilidade real dos solos.
    """
    s, cu, bc, cb, e = c.simulacao, c.cultura, c.biocarvao, c.carbono, c.emprestimo
    rng = np.random.default_rng(s.semente)
    N, T = s.n_simulacoes, s.horizonte_anos
    anos = np.arange(T + 1)

    # Resposta de produtividade (priori -> posteriori)
    fator_saude, desvio_saude = ajuste_saude_solo(c.saude)
    desvio0 = float(np.hypot(c.resposta.desvio, desvio_saude))
    usa_perfis = perfis is not None and len(perfis) > 0 and c.resposta.media is None
    if usa_perfis:
        idx = rng.integers(0, len(perfis), size=N)
        ph_p = perfis["ph"].to_numpy(dtype=float)[idx]
        v_p = perfis["v_pct"].to_numpy(dtype=float)[idx]
        ph_p = np.where(np.isnan(ph_p), c.solo.ph_agua, ph_p)
        v_p = np.where(np.isnan(v_p), c.solo.v_pct, v_p)
        ph_p, v_p = aplicar_manejo(ph_p, v_p, c.solo)
        arg_p = perfis["argila_pct"].to_numpy(dtype=float)[idx] if "argila_pct" in perfis else None
        c_p = perfis["c_org_gkg"].to_numpy(dtype=float)[idx] if "c_org_gkg" in perfis else None
        media0 = (resposta_media_vetor(ph_p, v_p, bc.tipo, arg_p, c_p) * fator_saude * cu.fator_resposta_cultura
                  * fator_manejo_resposta(c))
    else:
        idx = None
        base = c.resposta.media if c.resposta.media is not None else sugerir_resposta_media(c.solo, bc)
        if c.resposta.media is None:
            base *= cu.fator_resposta_cultura * fator_manejo_resposta(c)
        media0 = np.full(N, base * fator_saude)
    ens = list(c.resposta.ensaios_observados)
    if ens:
        prec0 = 1.0 / desvio0**2
        prec_d = len(ens) / c.resposta.desvio_ensaio**2
        media_post = (prec0 * media0 + prec_d * float(np.mean(ens))) / (prec0 + prec_d)
        desvio_r = (prec0 + prec_d) ** -0.5
    else:
        media_post, desvio_r = media0, desvio0
    media_r = float(np.mean(media_post))
    r_talhao = rng.normal(media_post, desvio_r)                             # efeito do talhão
    r = r_talhao[:, None] + rng.normal(0, c.resposta.ruido_anual, (N, T))  # variação anual
    r *= (1 - c.resposta.decaimento_anual) ** np.arange(T)[None, :]

    # Clima e preço
    quebra = rng.random((N, T)) < cu.prob_quebra_safra
    fator_clima = np.where(quebra, 1 - cu.perda_quebra_frac, 1.0)
    preco = cu.preco_cultura_r_t * rng.lognormal(-0.5 * np.log(1 + cu.preco_cultura_cv**2),
                                                 np.sqrt(np.log(1 + cu.preco_cultura_cv**2)), (N, T))

    # Fluxo agronômico (anos 1..T), por área total
    decaimento = (1 - c.resposta.decaimento_anual) ** np.arange(T)[None, :]
    ganho_prod = cu.produtividade_base_t_ha * fator_clima * r * preco
    db_agro = cu.area_ha * (ganho_prod + cu.economia_calcario_r_ha_ano + cu.economia_fert_r_ha_ano)

    # Carbono
    co2e = remocao_liquida_tco2e(c)
    preco_c = rng.uniform(cb.preco_min_usd_t, cb.preco_max_usd_t, N) * cb.cambio_r_usd
    emitido = rng.random(N) < cb.prob_emissao
    r_co2 = np.zeros((N, T + 1))
    if 0 <= cb.ano_recebimento <= T:
        r_co2[:, cb.ano_recebimento] = co2e * preco_c * (1 - cb.taxas_frac) * emitido

    # Empréstimo
    c0 = custo_inicial(c)
    principal = c0 * e.frac_financiada
    a = cronograma_emprestimo(principal, e, T)
    proprio = c0 - principal  # parte paga à vista pelo produtor

    # Fluxos do produtor (ano 0 = desembolso próprio)
    fluxo_agro = np.zeros((N, T + 1))
    fluxo_agro[:, 1:] = db_agro
    desconto = (1 + s.taxa_desconto_produtor) ** -anos
    fluxo_sem_c = fluxo_agro - a[None, :]
    fluxo_sem_c[:, 0] -= proprio
    fluxo_com_c = fluxo_sem_c + r_co2
    vpl_sem = fluxo_sem_c @ desconto
    vpl_com = fluxo_com_c @ desconto

    # Capacidade de pagamento e inadimplência
    margem_base = cu.area_ha * cu.margem_base_r_ha * cu.frac_margem_comprometivel * np.ones((N, T)) * fator_clima
    caixa = margem_base + db_agro + r_co2[:, 1:]
    servico = a[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        dscr = np.where(servico > 0, caixa / servico, np.inf)
    dscr_min = dscr.min(axis=1)
    inadimplente = (dscr < 1.0).any(axis=1)

    # Investidor: exposição no momento do 1º default ≈ saldo devedor naquele ano
    saldo = _saldo_devedor(principal, e, T)
    ano_default = np.where(inadimplente, (dscr < 1.0).argmax(axis=1) + 1, 0)
    exposicao = np.where(inadimplente, saldo[np.clip(ano_default - 1, 0, T)], 0.0)
    perda = exposicao * e.lgd
    recebido_bruto = a.sum() if principal > 0 else 0.0
    pago_acumulado = np.concatenate([[0.0], a[1:].cumsum()])  # pago até o fim do ano t
    pago_antes_default = pago_acumulado[np.clip(ano_default - 1, 0, T)]
    retorno_investidor = np.where(inadimplente,
                                  pago_antes_default + exposicao * (1 - e.lgd),
                                  recebido_bruto)
    multiplo = retorno_investidor / (principal * (1 - e.tarifa_plataforma_frac)) if principal > 0 else np.full(N, np.nan)

    # ---------------- Decomposição nas duas vantagens (valores presentes, R$)
    d1 = desconto[1:]
    pv_custos = proprio + float(a @ desconto)                                   # empréstimo + parte própria
    pv_prod = (cu.area_ha * ganho_prod) @ d1                                      # aumento de produtividade
    pv_econ = cu.area_ha * (cu.economia_calcario_r_ha_ano + cu.economia_fert_r_ha_ano) * float(d1.sum())
    pv_carb = r_co2 @ desconto                                                    # crédito de carbono
    pv_agro = pv_prod + pv_econ
    vpl_agro_so = pv_agro - pv_custos
    vpl_carb_so = pv_carb - pv_custos
    vpl_total = pv_agro + pv_carb - pv_custos                                     # = vpl_com
    classe = np.select(
        [(vpl_agro_so > 0) & (vpl_carb_so > 0), vpl_agro_so > 0, vpl_carb_so > 0, vpl_total > 0],
        ["Cada vantagem sozinha paga", "Só a produtividade paga", "Só o carbono paga",
         "Só as duas juntas pagam"], default="Inviável")

    # Sensibilidades lineares por simulação (para equilíbrio e mapa de viabilidade)
    u_resp = (cu.area_ha * cu.produtividade_base_t_ha * fator_clima * preco * decaimento) @ d1  # R$ por +1,0 em r
    k_carb = np.zeros(N)                                                          # R$ de VP por US$/t
    if 0 <= cb.ano_recebimento <= T:
        k_carb = co2e * cb.cambio_r_usd * (1 - cb.taxas_frac) * emitido * desconto[cb.ano_recebimento]
    with np.errstate(divide="ignore", invalid="ignore"):
        preco_eq = np.where(k_carb > 0, np.maximum(pv_custos - pv_agro, 0) / k_carb, np.nan)
        preco_eq_sem_prod = np.where(k_carb > 0, np.maximum(pv_custos - pv_econ, 0) / k_carb, np.nan)
        r_eq_sem_c = r_talhao + (pv_custos - pv_agro) / u_resp
        r_eq_com_c = r_talhao + (pv_custos - pv_agro - pv_carb) / u_resp

    if s.regra_decisao == "combinada":
        vpl_decisao = pv_agro + (1 - s.desconto_carbono_decisao) * pv_carb - pv_custos
    else:
        vpl_decisao = vpl_agro_so
    prob_vpl_sem = float((vpl_sem > 0).mean())
    prob_vpl_com = float((vpl_com > 0).mean())
    prob_decisao = float((vpl_decisao > 0).mean())

    resumo = {
        "fator_saude_solo": fator_saude,
        "n_perfis_solo": int(len(perfis)) if usa_perfis else 0,
        "ph_mediano_simulado": float(np.median(ph_p)) if usa_perfis else float(aplicar_manejo(c.solo.ph_agua, c.solo.v_pct, c.solo)[0]),
        "estoque_c_nativo_mediano_tha": float(perfis["estoque_c_0_20_tha"].median()) if usa_perfis and "estoque_c_0_20_tha" in perfis else float("nan"),
        "c_biocarvao_tha": bc.dose_t_ha * bc.c_org_frac,
        "resposta_media_usada": media_r,
        "resposta_desvio_usado": desvio_r,
        "biocarvao_elegivel": elegivel(bc, cb),
        "padrao_carbono": cb.padrao,
        "motivos_inelegivel": checar_padrao(bc.c_org_frac, bc.h_c_org, bc.o_c_org, cb.padrao, cb.h_c_max, cb.o_c_max)[1],
        "fator_dose": fator_dose(bc.dose_t_ha, c.resposta.dose_referencia_t_ha, c.resposta.dose_meia_saturacao_t_ha),
        "fator_adubacao": fator_adubacao(c.resposta.manejo_adubacao, bc.tipo),
        "incremento_c_solo_tha": incremento_c_solo_tha(c),
        "fator_permanencia": fator_permanencia(bc, cb, c.solo),
        "remocao_liquida_tco2e": co2e,
        "remocao_tco2e_por_ha": co2e / cu.area_ha if cu.area_ha else 0.0,
        "custo_inicial_r": c0,
        "principal_p2p_r": principal,
        "parcelas_r": a.tolist(),
        "prob_vpl_pos_sem_carbono": prob_vpl_sem,
        "prob_vpl_pos_com_carbono": prob_vpl_com,
        "vpl_sem_carbono_p10_p50_p90": np.percentile(vpl_sem, [10, 50, 90]).tolist(),
        "vpl_com_carbono_p10_p50_p90": np.percentile(vpl_com, [10, 50, 90]).tolist(),
        "prob_inadimplencia": float(inadimplente.mean()),
        "perda_esperada_r": float(perda.mean()),
        "perda_esperada_pct_principal": float(perda.mean() / principal) if principal > 0 else 0.0,
        "multiplo_investidor_medio": float(np.nanmean(multiplo)),
        "dscr_min_mediano": float(np.median(dscr_min[np.isfinite(dscr_min)])) if np.isfinite(dscr_min).any() else float("inf"),
        "aprovado": prob_decisao >= s.limiar_prob_vpl,
        "prob_decisao": prob_decisao,
        # duas vantagens
        "vp_custos_r": pv_custos,
        "vp_produtividade_mediano_r": float(np.median(pv_prod)),
        "vp_economia_insumos_r": pv_econ,
        "vp_carbono_mediano_r": float(np.median(pv_carb)),
        "cobertura_agro_mediana": float(np.median(pv_agro) / pv_custos) if pv_custos else float("nan"),
        "cobertura_carbono_mediana": float(np.median(pv_carb) / pv_custos) if pv_custos else float("nan"),
        "classes_viabilidade": pd.Series(classe).value_counts(normalize=True).reindex(CLASSES_VIABILIDADE, fill_value=0.0).to_dict(),
        "preco_carbono_equilibrio_usd_mediano": float(np.nanmedian(preco_eq)) if np.isfinite(preco_eq).any() else float("nan"),
        "preco_carbono_equilibrio_sem_ganho_prod_usd": float(np.nanmedian(preco_eq_sem_prod)) if np.isfinite(preco_eq_sem_prod).any() else float("nan"),
        "resposta_equilibrio_sem_carbono_mediana": float(np.nanmedian(r_eq_sem_c)),
        "resposta_equilibrio_com_carbono_mediana": float(np.nanmedian(r_eq_com_c)),
    }

    df = pd.DataFrame({
        "vpl_sem_carbono": vpl_sem,
        "vpl_com_carbono": vpl_com,
        "receita_carbono": r_co2.sum(axis=1),
        "resposta_media_talhao": r_talhao,
        "id_perfil": perfis["id_perfil"].to_numpy()[idx] if usa_perfis and "id_perfil" in perfis else None,
        "dscr_min": dscr_min,
        "inadimplente": inadimplente,
        "perda_investidor": perda,
        "caixa_credor": retorno_investidor,
        "vp_produtividade": pv_prod,
        "vp_carbono": pv_carb,
        "classe_viabilidade": classe,
    })
    componentes = {"principal": principal, "parcelas": a, "pv_prod": pv_prod, "pv_econ": pv_econ, "pv_custos": pv_custos, "u_resp": u_resp,
                   "k_carb": k_carb, "media_r": media_r, "inadimplente": inadimplente, "classe": classe}
    return {"resumo": resumo, "simulacoes": df, "componentes": componentes}


CLASSES_VIABILIDADE = ["Cada vantagem sozinha paga", "Só a produtividade paga", "Só o carbono paga",
                       "Só as duas juntas pagam", "Inviável"]


def mapa_viabilidade(resultado: dict, precos_usd: Sequence[float], respostas: Sequence[float]) -> pd.DataFrame:
    """P(VPL > 0) para cada combinação de preço de carbono (US$/t) e resposta média de produtividade.

    Reaproveita as simulações já feitas: o VPL é linear no preço do carbono e num deslocamento
    da resposta média, então a grade sai sem novo Monte Carlo. Clima, preços da cultura,
    emissão do crédito e variabilidade entre talhões continuam sorteados.
    """
    cpt = resultado["componentes"]
    linhas = []
    for m in respostas:
        base = cpt["pv_prod"] + (m - cpt["media_r"]) * cpt["u_resp"] + cpt["pv_econ"] - cpt["pv_custos"]
        for p in precos_usd:
            linhas.append({"resposta_media": m, "preco_carbono_usd": p,
                           "prob_viavel": float(((base + p * cpt["k_carb"]) > 0).mean())})
    return pd.DataFrame(linhas)


def _saldo_devedor(principal: float, e: ParametrosEmprestimo, horizonte: int) -> np.ndarray:
    """Saldo devedor no início de cada ano t=1..horizonte (índice 0 = ano 1)."""
    saldo = np.zeros(horizonte + 1)
    s = principal
    a = cronograma_emprestimo(principal, e, horizonte)
    for t in range(1, horizonte + 1):
        saldo[t - 1] = s
        juros = s * e.taxa_anual
        s = max(s + juros - a[t], 0.0)
    saldo[horizonte] = s
    return saldo


def analise_sensibilidade(c: Cenario, parametro: str, valores: Sequence[float],
                          perfis: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Varia um parâmetro ("grupo.campo", ex. 'carbono.preco_max_usd_t') e devolve métricas."""
    import copy
    grupo, campo = parametro.split(".")
    linhas = []
    for v in valores:
        cc = copy.deepcopy(c)
        setattr(getattr(cc, grupo), campo, v)
        res = simular(cc, perfis)["resumo"]
        linhas.append({
            parametro: v,
            "P(VPL>0) sem carbono": res["prob_vpl_pos_sem_carbono"],
            "P(VPL>0) com carbono": res["prob_vpl_pos_com_carbono"],
            "Prob. inadimplência": res["prob_inadimplencia"],
            "VPL mediano com carbono (R$)": res["vpl_com_carbono_p10_p50_p90"][1],
        })
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    cen = Cenario()
    out = simular(cen)
    for k, v in out["resumo"].items():
        print(f"{k:35s} {v}")
