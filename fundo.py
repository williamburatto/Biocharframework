"""
Fundo com cotas sênior e subordinada para carteiras de crédito de biocarvão.

Estrutura modelada (ex.: FIDC/Fiagro-Direitos Creditórios no Brasil):
  - Ativos: direitos creditórios das operações originadas pela cooperativa
    (CCB/CPR dos cooperados), opcionalmente com cessão de parte dos recebíveis
    de carbono.
  - Cota subordinada: cooperativa (e/ou fornecedor), absorve as primeiras perdas.
  - Cota sênior: investidores, inclusive a fração captada via plataforma P2P/varejo.
  - Cascata: despesas do fundo -> sênior (principal + remuneração-alvo) -> subordinada (residual).

Inadimplência correlacionada por um modelo de um fator (cópula gaussiana, Vasicek):
um choque comum (clima, preço) atinge todos os cooperados da mesma região.
As probabilidades e os caixas por operação vêm do simulador (Monte Carlo do talhão).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd

from simulador import ParametrosEmprestimo, cronograma_emprestimo

_N = NormalDist()


@dataclass
class ParametrosFundo:
    n_operacoes: int = 100               # operações (cooperados) na carteira
    subordinacao: float = 0.20           # fração do PL em cota subordinada
    taxa_senior_aa: float = 0.14         # remuneração-alvo da sênior (a.a.)
    custo_fundo_aa: float = 0.015        # administração, gestão, custódia, registro (a.a. sobre o PL)
    correlacao: float = 0.25             # correlação de inadimplência entre operações (choque regional)
    frac_carbono_cedida: float = 0.0     # fração da receita de carbono cedida ao fundo
    frac_p2p_senior: float = 0.40        # parte da sênior captada via P2P/varejo (informativo)
    n_cenarios: int = 5000
    semente: int = 7


def _fator_cronograma(taxa: float, e: ParametrosEmprestimo, horizonte: int) -> float:
    """Soma nominal das parcelas por R$ 1 de principal, no prazo e carência das operações."""
    e2 = ParametrosEmprestimo(**{**vars(e), "taxa_anual": taxa})
    return float(cronograma_emprestimo(1.0, e2, max(horizonte, e.prazo_anos)).sum())


def simular_fundo(resultado: dict, emprestimo: ParametrosEmprestimo, horizonte: int,
                  pf: ParametrosFundo) -> dict:
    """Cascata do fundo a partir das simulações de uma operação-tipo."""
    df = resultado["simulacoes"]
    principal = float(resultado["componentes"]["principal"])
    if principal <= 0:
        raise ValueError("Operação sem principal financiado: aumente a fração financiada.")
    rng = np.random.default_rng(pf.semente)

    pd_op = float(df["inadimplente"].mean())
    caixa_ok = df.loc[~df["inadimplente"], "caixa_credor"].to_numpy()
    caixa_def = df.loc[df["inadimplente"], "caixa_credor"].to_numpy()
    carbono = df["receita_carbono"].to_numpy() * pf.frac_carbono_cedida
    carb_ok = carbono[~df["inadimplente"].to_numpy()]
    carb_def = carbono[df["inadimplente"].to_numpy()]
    if len(caixa_ok) == 0:
        caixa_ok, carb_ok = caixa_def, carb_def
    if len(caixa_def) == 0:
        caixa_def, carb_def = caixa_ok, carb_ok

    n, m = pf.n_operacoes, pf.n_cenarios
    pl = principal * n
    prazo = max(emprestimo.prazo_anos, 1)

    # inadimplência correlacionada (Vasicek)
    limiar = _N.inv_cdf(min(max(pd_op, 1e-6), 1 - 1e-6))
    z = rng.standard_normal((m, 1))
    eps = rng.standard_normal((m, n))
    default = (np.sqrt(pf.correlacao) * z + np.sqrt(1 - pf.correlacao) * eps) < limiar

    i_ok = rng.integers(0, len(caixa_ok), (m, n))
    i_def = rng.integers(0, len(caixa_def), (m, n))
    caixa = np.where(default, caixa_def[i_def] + carb_def[i_def], caixa_ok[i_ok] + carb_ok[i_ok]).sum(axis=1)

    despesas = pl * pf.custo_fundo_aa * prazo
    disponivel = np.maximum(caixa - despesas, 0.0)
    senior = pl * (1 - pf.subordinacao)
    sub = pl * pf.subordinacao
    prometido_senior = senior * _fator_cronograma(pf.taxa_senior_aa, emprestimo, horizonte)
    pago_senior = np.minimum(disponivel, prometido_senior)
    residual_sub = disponivel - pago_senior

    perda_senior = np.clip(1 - pago_senior / prometido_senior, 0, 1)
    multiplo_sub = residual_sub / sub if sub > 0 else np.full(m, np.nan)
    multiplo_sen = pago_senior / senior
    taxa_inad = default.mean(axis=1)

    resumo = {
        "pd_operacao": pd_op,
        "pl_r": pl,
        "senior_r": senior,
        "senior_p2p_r": senior * pf.frac_p2p_senior,
        "subordinada_r": sub,
        "inadimplencia_media_carteira": float(taxa_inad.mean()),
        "inadimplencia_p99_carteira": float(np.percentile(taxa_inad, 99)),
        "prob_perda_senior": float((perda_senior > 1e-9).mean()),
        "perda_esperada_senior": float(perda_senior.mean()),
        "multiplo_senior_medio": float(multiplo_sen.mean()),
        "multiplo_sub_p10_p50_p90": np.percentile(multiplo_sub, [10, 50, 90]).tolist() if sub > 0 else [np.nan] * 3,
        "prob_sub_perde_capital": float((multiplo_sub < 1).mean()) if sub > 0 else float("nan"),
        "prob_sub_zerada": float((residual_sub <= 1e-6).mean()) if sub > 0 else float("nan"),
        "retorno_sub_aa_mediano": float(np.median(multiplo_sub) ** (1 / prazo) - 1) if sub > 0 else float("nan"),
    }
    cenarios = pd.DataFrame({"inadimplencia_carteira": taxa_inad, "multiplo_senior": multiplo_sen,
                             "multiplo_subordinada": multiplo_sub, "perda_senior": perda_senior})
    return {"resumo": resumo, "cenarios": cenarios}


def curva_subordinacao(resultado: dict, emprestimo: ParametrosEmprestimo, horizonte: int,
                       pf: ParametrosFundo, niveis=None) -> pd.DataFrame:
    niveis = np.round(np.arange(0.05, 0.51, 0.05), 2) if niveis is None else niveis
    linhas = []
    for s in niveis:
        r = simular_fundo(resultado, emprestimo, horizonte,
                          ParametrosFundo(**{**vars(pf), "subordinacao": float(s), "n_cenarios": 2000}))["resumo"]
        linhas.append({"subordinacao": float(s), "prob_perda_senior": r["prob_perda_senior"],
                       "perda_esperada_senior": r["perda_esperada_senior"],
                       "multiplo_sub_mediano": r["multiplo_sub_p10_p50_p90"][1]})
    return pd.DataFrame(linhas)


def subordinacao_minima(curva: pd.DataFrame, alvo_prob_perda: float = 0.01) -> float | None:
    ok = curva[curva["prob_perda_senior"] <= alvo_prob_perda]
    return float(ok["subordinacao"].min()) if len(ok) else None
