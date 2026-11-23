"""
Mercados regulados de carbono comparados com o SBCE (Brasil) para o crédito de biocarvão.

Cada mercado define a faixa de preço (US$/tCO2e) usada no simulador e se o crédito de biocarvão
já é aceito para cumprimento de metas. Os preços são convertidos com o câmbio informado em cada
entrada (fonte e data na chave "fonte_preco"). Os mercados em que o biocarvão NÃO é aceito são
simulados como "acesso hipotético": mostram quanto valeria o crédito se a regra mudasse.

Atualize os preços antes de cada uso: eles mudam diariamente.
"""

from __future__ import annotations

import copy

import pandas as pd

from regioes import avaliar_municipios

# câmbios usados na conversão (implícitos nas fontes citadas)
JPY_POR_USD = 4300 / 26.91       # S&P Global, abr. 2026: ¥4.300 = US$ 26,91
USD_POR_EUR = 99.10 / 88.82      # S&P Global, 12 out. 2026: €88,82 = US$ 99,10

MERCADOS = {
    "SBCE": {
        "nome_pt": "SBCE (Brasil) — CRVE, prospectivo",
        "nome_en": "SBCE (Brazil) — CRVE, prospective",
        "jurisdicao": "Brasil",
        "tipo_pt": "Cumprimento (em regulamentação)", "tipo_en": "Compliance (being regulated)",
        "biocarvao_pt": "Possível: depende do credenciamento de metodologia no PBCE",
        "biocarvao_en": "Possible: depends on methodology accreditation under the PBCE",
        "limite_pt": "% máximo de CRVE a definir no Plano Nacional de Alocação",
        "limite_en": "Maximum CRVE share to be set in the National Allocation Plan",
        "preco_min": 96.0, "preco_max": 144.0,
        "fonte_preco": "Tabela 3 do artigo GCB (US$ 120 ± 20%)",
        "hipotetico": False,
        "situacao_pt": "Fase 1 (regulamentação) até dez./2026; consulta pública do PBCE prevista para nov./2026.",
        "situacao_en": "Phase 1 (regulation) until Dec 2026; PBCE public consultation planned for Nov 2026.",
    },
    "GX": {
        "nome_pt": "GX-ETS via J-Credit (Japão)",
        "nome_en": "GX-ETS via J-Credit (Japan)",
        "jurisdicao": "Japão",
        "tipo_pt": "Cumprimento (obrigatório desde abr./2026)", "tipo_en": "Compliance (mandatory since Apr 2026)",
        "biocarvao_pt": "Sim: metodologia de biocarvão em solo agrícola no J-Credit",
        "biocarvao_en": "Yes: J-Credit methodology for biochar in agricultural soil",
        "limite_pt": "Até 10% das emissões com J-Credit/JCM",
        "limite_en": "Up to 10% of emissions with J-Credit/JCM",
        "preco_min": round(1700 / JPY_POR_USD, 1), "preco_max": round(4800 / JPY_POR_USD, 1),
        "fonte_preco": "Corredor GX-ETS ¥1.700–4.300; J-Credit eficiência ~¥4.800 (S&P Global, abr. 2026)",
        "hipotetico": False,
        "situacao_pt": "Só projetos japoneses no Japão geram J-Credit; para o Brasil é referência de desenho.",
        "situacao_en": "Only Japanese projects in Japan generate J-Credits; for Brazil it is a design benchmark.",
    },
    "CRCF": {
        "nome_pt": "UE voluntário certificado (CRCF / Puro, índice CORCCHAR)",
        "nome_en": "EU certified voluntary (CRCF / Puro, CORCCHAR index)",
        "jurisdicao": "União Europeia",
        "tipo_pt": "Voluntário com certificação pública", "tipo_en": "Voluntary with public certification",
        "biocarvao_pt": "Sim (voluntário): metodologia de biocarvão no CRCF, em vigor desde maio/2026",
        "biocarvao_en": "Yes (voluntary): CRCF biochar methodology, in force since May 2026",
        "limite_pt": "Sem limite (não conta para o EU ETS)",
        "limite_en": "No limit (does not count towards the EU ETS)",
        "preco_min": round(124.02 * 0.9 * USD_POR_EUR, 1), "preco_max": round(124.02 * 1.1 * USD_POR_EUR, 1),
        "fonte_preco": "Índice Puro/Nasdaq CORCCHAR €124,02 (set./2026) ± 10%",
        "hipotetico": False,
        "situacao_pt": "Acessível hoje a fornecedores brasileiros pelo mercado voluntário (Puro.earth).",
        "situacao_en": "Accessible today to Brazilian suppliers through the voluntary market (Puro.earth).",
    },
    "EUETS": {
        "nome_pt": "EU ETS (permissão EUA) — acesso hipotético",
        "nome_en": "EU ETS (EUA allowance) — hypothetical access",
        "jurisdicao": "União Europeia",
        "tipo_pt": "Cumprimento", "tipo_en": "Compliance",
        "biocarvao_pt": "Não: a revisão de jul./2026 propõe só BioCCS e DACCS",
        "biocarvao_en": "No: the July 2026 review proposes only BioCCS and DACCS",
        "limite_pt": "Proposta: até 250 Mt de remoções permanentes",
        "limite_en": "Proposal: up to 250 Mt of permanent removals",
        "preco_min": round(86.69 * 0.9 * USD_POR_EUR, 1), "preco_max": round(86.69 * 1.1 * USD_POR_EUR, 1),
        "fonte_preco": "EUA dez./2026 €86,69 (S&P Global, 6 nov. 2026) ± 10%",
        "hipotetico": True,
        "situacao_pt": "Biocarvão fora do mercado regulado; o preço mostra o valor se fosse incluído.",
        "situacao_en": "Biochar outside the compliance market; the price shows its value if included.",
    },
    "UKETS": {
        "nome_pt": "UK ETS (Reino Unido) — remoções a partir de 2029",
        "nome_en": "UK ETS (United Kingdom) — removals from 2029",
        "jurisdicao": "Reino Unido",
        "tipo_pt": "Cumprimento (remoções previstas para 2029)", "tipo_en": "Compliance (removals planned for 2029)",
        "biocarvao_pt": "Em avaliação: exige permanência ≥ 200 anos e Norma GGR do Reino Unido",
        "biocarvao_en": "Under consideration: requires ≥ 200-year permanence and the UK GGR Standard",
        "limite_pt": "Só projetos no Reino Unido; créditos emitidos após verificação",
        "limite_en": "UK projects only; credits issued after verification",
        "preco_min": round(84.41 * 0.9, 1), "preco_max": round(84.41 * 1.1, 1),
        "fonte_preco": "UKA dez./2026 £63,36 = US$ 84,41 (EEX, 16 out. 2026) ± 10%",
        "hipotetico": True,
        "situacao_pt": "Legislação até 2028 e integração em 2029; preço pode diferir do UKA.",
        "situacao_en": "Legislation by 2028 and integration in 2029; price may differ from the UKA.",
    },
    "CA": {
        "nome_pt": "Califórnia Cap-and-Invest — acesso hipotético",
        "nome_en": "California Cap-and-Invest — hypothetical access",
        "jurisdicao": "EUA (Califórnia)",
        "tipo_pt": "Cumprimento", "tipo_en": "Compliance",
        "biocarvao_pt": "Não: protocolos aprovados não incluem biocarvão",
        "biocarvao_en": "No: approved protocols do not include biochar",
        "limite_pt": "Offsets até 6% das obrigações (2026–2045)",
        "limite_en": "Offsets up to 6% of obligations (2026–2045)",
        "preco_min": 27.94, "preco_max": 32.48,
        "fonte_preco": "Leilões CARB 2026: US$ 27,94 (fev.) a 32,48 (ago.)",
        "hipotetico": True,
        "situacao_pt": "Força-tarefa avaliará novos protocolos de solo; CARB revisa protocolos até 2029.",
        "situacao_en": "A task force will assess new soil protocols; CARB updates protocols by 2029.",
    },
    "NENHUM": {
        "nome_pt": "Sem receita de carbono", "nome_en": "No carbon revenue",
        "jurisdicao": "—", "tipo_pt": "—", "tipo_en": "—",
        "biocarvao_pt": "—", "biocarvao_en": "—", "limite_pt": "—", "limite_en": "—",
        "preco_min": 0.0, "preco_max": 0.0, "fonte_preco": "—", "hipotetico": False,
        "situacao_pt": "Só o ganho de produtividade paga a operação.",
        "situacao_en": "Only the yield gain pays for the operation.",
    },
}


def tabela_mercados(lang: str = "pt") -> pd.DataFrame:
    s = "_en" if lang == "en" else "_pt"
    linhas = []
    for k, m in MERCADOS.items():
        if k == "NENHUM":
            continue
        linhas.append({"mercado": m["nome" + s], "tipo": m["tipo" + s], "biocarvao": m["biocarvao" + s],
                       "limite": m["limite" + s], "preco_usd": f"{m['preco_min']:.0f}–{m['preco_max']:.0f}",
                       "fonte_preco": m["fonte_preco"], "situacao": m["situacao" + s]})
    return pd.DataFrame(linhas)


def cenario_no_mercado(cenario, chave: str):
    c = copy.deepcopy(cenario)
    m = MERCADOS[chave]
    c.carbono.preco_min_usd_t, c.carbono.preco_max_usd_t = m["preco_min"], m["preco_max"]
    return c


def comparar_mercados(cenario, perfis, ufs=("PR", "SC"), min_perfis=3, n_simulacoes=2000, limiar=0.70,
                      chaves=None) -> tuple[pd.DataFrame, dict]:
    """Roda o ranking de municípios com o preço de cada mercado. Retorna (resumo, rankings por mercado)."""
    chaves = chaves or list(MERCADOS)
    rankings, linhas = {}, []
    for k in chaves:
        r = avaliar_municipios(cenario_no_mercado(cenario, k), perfis, ufs=ufs, min_perfis=min_perfis,
                               n_simulacoes=n_simulacoes)
        rankings[k] = r
        linhas.append({"chave": k, "n_municipios": len(r),
                       "viaveis": int((r.prob_vpl_com_carbono >= limiar).sum()),
                       "viaveis_so_produtividade": int((r.prob_vpl_sem_carbono >= limiar).sum()),
                       "p_mediana": float(r.prob_vpl_com_carbono.median()),
                       "preco_min": MERCADOS[k]["preco_min"], "preco_max": MERCADOS[k]["preco_max"],
                       "hipotetico": MERCADOS[k]["hipotetico"]})
    return pd.DataFrame(linhas), rankings
