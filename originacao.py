"""
Pacote de originação e crédito embutido via agfintech.

- gerar_pacote(): monta o pacote de originação (JSON) de uma operação, com dados do
  imóvel, solo, biocarvão, simulação (duas vantagens), operação, garantias e estrutura
  de funding (crédito embutido e/ou fundo com cotas). Inclui hash SHA-256 do conteúdo
  canônico, para ancoragem no contrato inteligente.
- validar_pacote(): valida contra ESQUEMA_PACOTE (JSON Schema 2020-12).
- ClienteAgfintech: envia o pacote à API da agfintech (especificação em openapi.yaml).
  Sem URL configurada, roda em modo simulado com uma política de crédito local.

Dados pessoais: o produtor entra só por identificador pseudonimizado; o consentimento
(LGPD) é obrigatório para gerar o pacote.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

VERSAO_SCHEMA = "biocredito.originacao/1.0"

FINALIDADES = ["analise_credito", "registro_garantias", "certificacao_carbono", "pesquisa_anonimizada"]
CANAIS = ["credito_embutido_agfintech", "p2p_sep", "fundo_cotas"]


@dataclass
class MetadadosOriginacao:
    cooperativa_nome: str = ""
    cooperativa_cnpj: str = ""
    produtor_id: str = ""                 # identificador pseudonimizado na cooperativa
    codigo_car: str = ""
    municipio: str = ""
    uf: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    fornecedor_nome: str = ""
    fornecedor_cnpj: str = ""
    consentimento: bool = False
    finalidades: tuple = ("analise_credito", "registro_garantias", "certificacao_carbono")
    canal: str = "credito_embutido_agfintech"
    fundo_id: str = ""


def _limpo(x):
    """Converte numpy/NaN para tipos JSON."""
    if isinstance(x, dict):
        return {k: _limpo(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_limpo(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if (math.isnan(x) or math.isinf(x)) else round(float(x), 6)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def hash_conteudo(pacote: dict) -> str:
    corpo = {k: v for k, v in pacote.items() if k != "integridade"}
    canonico = json.dumps(corpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def gerar_pacote(cenario, resultado: dict, meta: MetadadosOriginacao,
                 perfis: Optional[pd.DataFrame] = None, fundo: Optional[dict] = None) -> dict:
    if not meta.consentimento:
        raise ValueError("Consentimento do produtor (LGPD) é obrigatório para gerar o pacote.")
    r = resultado["resumo"]
    cu, bc, e, cb = cenario.cultura, cenario.biocarvao, cenario.emprestimo, cenario.carbono

    solo = {"fonte": "bdsolos" if r.get("n_perfis_solo") else "parametros_informados",
            "n_perfis": r.get("n_perfis_solo", 0),
            "ph_mediano_simulado": r.get("ph_mediano_simulado"),
            "estoque_c_nativo_0_20_tha": r.get("estoque_c_nativo_mediano_tha"),
            "correcao_manejo": {"ph_min": cenario.solo.ph_min_manejo, "v_min": cenario.solo.v_min_manejo},
            "saude_solo": {"fonte": cenario.saude.fonte, "classe": cenario.saude.classe_saude,
                           "f1": cenario.saude.f1_ciclar, "f2": cenario.saude.f2_armazenar,
                           "f3": cenario.saude.f3_suprir, "iqs_fertbio": cenario.saude.iqs_fertbio}}
    if perfis is not None and len(perfis):
        solo["ids_perfis_bdsolos"] = perfis["id_perfil"].astype(str).head(200).tolist()

    pacote = {
        "versao_schema": VERSAO_SCHEMA,
        "id_pacote": str(uuid.uuid4()),
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canal": meta.canal,
        "originador": {"tipo": "cooperativa", "nome": meta.cooperativa_nome, "cnpj": meta.cooperativa_cnpj},
        "produtor": {"id_pseudonimo": meta.produtor_id,
                     "consentimento": {"concedido": True, "base_legal": "LGPD art. 7º, I (consentimento)",
                                       "finalidades": list(meta.finalidades),
                                       "data": datetime.now(timezone.utc).date().isoformat()}},
        "imovel": {"codigo_car": meta.codigo_car, "municipio": meta.municipio, "uf": meta.uf,
                   "lat": meta.lat, "lon": meta.lon, "area_ha": cu.area_ha},
        "cultura": {"nome": cu.cultura, "produtividade_base_t_ha": cu.produtividade_base_t_ha,
                    "preco_r_t": cu.preco_cultura_r_t, "fator_resposta_cultura": cu.fator_resposta_cultura},
        "solo": solo,
        "biocarvao": {"fornecedor": {"nome": meta.fornecedor_nome, "cnpj": meta.fornecedor_cnpj},
                      "tipo": bc.tipo, "dose_t_ha": bc.dose_t_ha, "preco_r_t": bc.preco_r_t, "frete_r_t": bc.frete_r_t,
                      "c_org_frac": bc.c_org_frac, "h_c_org": bc.h_c_org, "o_c_org": bc.o_c_org,
                      "elegivel_credito_carbono": r["biocarvao_elegivel"]},
        "operacao": {"custo_inicial_r": r["custo_inicial_r"], "principal_r": r["principal_p2p_r"],
                     "frac_financiada": e.frac_financiada, "taxa_anual": e.taxa_anual,
                     "carencia_anos": e.carencia_anos, "prazo_anos": e.prazo_anos,
                     "cronograma_r": r["parcelas_r"], "pagamento_direto_fornecedor": True},
        "simulacao": {
            "n_simulacoes": cenario.simulacao.n_simulacoes,
            "regra_decisao": cenario.simulacao.regra_decisao,
            "prob_viavel_pela_regra": r["prob_decisao"],
            "aprovado_pela_regra": r["aprovado"],
            "prob_vpl_pos_sem_carbono": r["prob_vpl_pos_sem_carbono"],
            "prob_vpl_pos_com_carbono": r["prob_vpl_pos_com_carbono"],
            "vpl_com_carbono_p10_p50_p90": r["vpl_com_carbono_p10_p50_p90"],
            "prob_inadimplencia": r["prob_inadimplencia"],
            "perda_esperada_pct_principal": r["perda_esperada_pct_principal"],
            "dscr_min_mediano": r["dscr_min_mediano"],
            "resposta_produtividade_media": r["resposta_media_usada"],
            "duas_vantagens": {"vp_custos_r": r["vp_custos_r"],
                               "vp_produtividade_r": r["vp_produtividade_mediano_r"],
                               "vp_economia_insumos_r": r["vp_economia_insumos_r"],
                               "vp_carbono_r": r["vp_carbono_mediano_r"],
                               "classes": r["classes_viabilidade"],
                               "preco_carbono_equilibrio_usd": r["preco_carbono_equilibrio_usd_mediano"],
                               "resposta_equilibrio_sem_carbono": r["resposta_equilibrio_sem_carbono_mediana"]},
        },
        "carbono": {"remocao_liquida_tco2e": r["remocao_liquida_tco2e"], "fator_permanencia": r["fator_permanencia"],
                    "preco_min_usd": cb.preco_min_usd_t, "preco_max_usd": cb.preco_max_usd_t,
                    "padrao_pretendido": "Puro.earth | Verra VM0044 | Isometric (a definir)"},
        "garantias": [
            {"tipo": "CPR", "modalidade": "financeira", "registro": "entidade registradora autorizada pelo BCB",
             "valor_referencia_r": r["principal_p2p_r"]},
            {"tipo": "retencao_entrega_safra", "agente": "cooperativa"},
        ],
        "funding": {"canal": meta.canal, "fundo_id": meta.fundo_id or None, "estrutura_fundo": fundo},
        "marcos_contrato": ["proposta", "financiada", "lote_certificado", "entregue", "aplicada",
                            "safra", "credito_emitido", "monitoramento"],
    }
    pacote = _limpo(pacote)
    pacote["integridade"] = {"algoritmo": "SHA-256", "hash": hash_conteudo(pacote)}
    return pacote


ESQUEMA_PACOTE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://biocredito.example/schemas/pacote-originacao-1.0.json",
    "title": "Pacote de originação BioCrédito Agro",
    "type": "object",
    "required": ["versao_schema", "id_pacote", "gerado_em", "canal", "originador", "produtor", "imovel",
                 "cultura", "solo", "biocarvao", "operacao", "simulacao", "garantias", "integridade"],
    "properties": {
        "versao_schema": {"const": VERSAO_SCHEMA},
        "id_pacote": {"type": "string", "format": "uuid"},
        "gerado_em": {"type": "string", "format": "date-time"},
        "canal": {"enum": CANAIS},
        "originador": {"type": "object", "required": ["tipo", "nome"],
                       "properties": {"tipo": {"const": "cooperativa"}, "nome": {"type": "string", "minLength": 1},
                                      "cnpj": {"type": "string"}}},
        "produtor": {"type": "object", "required": ["id_pseudonimo", "consentimento"],
                     "properties": {"id_pseudonimo": {"type": "string", "minLength": 1},
                                    "consentimento": {"type": "object", "required": ["concedido", "finalidades"],
                                                      "properties": {"concedido": {"const": True},
                                                                     "finalidades": {"type": "array", "minItems": 1,
                                                                                     "items": {"enum": FINALIDADES}}}}}},
        "imovel": {"type": "object", "required": ["area_ha"],
                   "properties": {"area_ha": {"type": "number", "exclusiveMinimum": 0},
                                  "lat": {"type": ["number", "null"], "minimum": -34, "maximum": 6},
                                  "lon": {"type": ["number", "null"], "minimum": -74, "maximum": -28}}},
        "operacao": {"type": "object", "required": ["principal_r", "taxa_anual", "prazo_anos", "cronograma_r"],
                     "properties": {"principal_r": {"type": "number", "minimum": 0},
                                    "taxa_anual": {"type": "number", "minimum": 0},
                                    "prazo_anos": {"type": "integer", "minimum": 1},
                                    "cronograma_r": {"type": "array", "items": {"type": "number"}}}},
        "simulacao": {"type": "object", "required": ["prob_vpl_pos_sem_carbono", "prob_vpl_pos_com_carbono",
                                                     "prob_inadimplencia", "duas_vantagens"]},
        "integridade": {"type": "object", "required": ["algoritmo", "hash"],
                        "properties": {"algoritmo": {"const": "SHA-256"},
                                       "hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}},
    },
}


def validar_pacote(pacote: dict) -> list[str]:
    """Erros de validação (lista vazia = válido). Também confere o hash."""
    erros = []
    try:
        import jsonschema
        v = jsonschema.Draft202012Validator(ESQUEMA_PACOTE)
        erros = [f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}" for e in v.iter_errors(pacote)]
    except ImportError:
        erros = [f"campo obrigatório ausente: {k}" for k in ESQUEMA_PACOTE["required"] if k not in pacote]
    if "integridade" in pacote and pacote["integridade"].get("hash") != hash_conteudo(pacote):
        erros.append("integridade: hash não confere com o conteúdo")
    return erros


# --------------------------------------------------------------------------- crédito embutido

@dataclass
class PoliticaCreditoSimulada:
    """Política usada no modo simulado (substituída pela da agfintech em produção)."""
    pd_maxima: float = 0.35
    prob_viavel_minima: float = 0.60
    taxa_base_aa: float = 0.14
    spread_por_pd: float = 0.20        # acréscimo de taxa por unidade de probabilidade de inadimplência
    limite_por_ha_r: float = 6000.0


class ClienteAgfintech:
    """Cliente da API de crédito embutido (ver openapi.yaml).

    base_url vazio => modo simulado (decisão local com PoliticaCreditoSimulada).
    """

    def __init__(self, base_url: str = "", token: str = "", timeout: int = 20,
                 politica: PoliticaCreditoSimulada | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.politica = politica or PoliticaCreditoSimulada()

    @property
    def simulado(self) -> bool:
        return not self.base_url

    def _post(self, caminho: str, corpo: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{caminho}", data=json.dumps(corpo).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}",
                     "Idempotency-Key": corpo.get("id_pacote", str(uuid.uuid4()))})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            raise RuntimeError(f"API respondeu {erro.code}: {erro.read().decode('utf-8', 'ignore')[:500]}") from erro

    def solicitar_credito(self, pacote: dict) -> dict:
        """Envia o pacote (POST /v1/originacoes) e devolve a decisão."""
        if not self.simulado:
            return self._post("/v1/originacoes", pacote)
        return self._decidir_localmente(pacote)

    def _decidir_localmente(self, pacote: dict) -> dict:
        p, sim, op = self.politica, pacote["simulacao"], pacote["operacao"]
        pd_ = sim["prob_inadimplencia"]
        viavel = sim["prob_viavel_pela_regra"]
        limite = p.limite_por_ha_r * pacote["imovel"]["area_ha"]
        motivos = []
        if pd_ > p.pd_maxima:
            motivos.append(f"probabilidade de inadimplência {pd_:.0%} acima do máximo {p.pd_maxima:.0%}")
        if viavel < p.prob_viavel_minima:
            motivos.append(f"probabilidade de viabilidade {viavel:.0%} abaixo do mínimo {p.prob_viavel_minima:.0%}")
        if op["principal_r"] > limite:
            motivos.append(f"principal acima do limite de R$ {limite:,.0f}")
        aprovado = not motivos
        return {
            "id_originacao": pacote["id_pacote"],
            "status": "aprovado" if aprovado else "recusado",
            "modo": "simulado",
            "oferta": {"principal_r": op["principal_r"], "taxa_anual": round(p.taxa_base_aa + p.spread_por_pd * pd_, 4),
                       "prazo_anos": op["prazo_anos"], "carencia_anos": op.get("carencia_anos", 0),
                       "garantias_exigidas": ["CPR registrada", "retencao_entrega_safra"],
                       "validade_dias": 15} if aprovado else None,
            "motivos": motivos,
            "hash_pacote": pacote["integridade"]["hash"],
        }
