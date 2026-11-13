"""
Integração do BDsolos (Embrapa — Sistema de Informação de Solos Brasileiros) ao simulador.

O export bruto (bd_solos_para_redape.csv, separador ';', um registro por HORIZONTE)
é reduzido a uma tabela com UM registro por PERFIL, com os atributos da camada
0–20 cm ponderados pela espessura, e o estoque de carbono orgânico 0–20 cm.

Uso:
    python bdsolos.py bd_solos_para_redape.csv perfis_bdsolos_0_20.csv

Cuidados de interpretação:
- Os perfis vêm de levantamentos pedológicos (mediana de coleta ~1979), em sua
  maioria sob vegetação nativa ou pastagem. pH e V% representam o solo pouco ou
  não corrigido; em lavoura manejada os valores atuais tendem a ser maiores.
  O simulador oferece uma correção de manejo (pH e V% mínimos) para esse caso.
- Densidade do solo falta em ~85% dos horizontes; quando ausente, é estimada
  pela função de pedotransferência de Benites et al. (2007, Geoderma 139:90–97)
  para solos brasileiros: Ds = 1,56 − 0,0005·argila − 0,01·C + 0,0075·SB
  (argila e C em g/kg, SB em cmolc/kg). Confira os coeficientes antes de publicar.
"""

from __future__ import annotations

import sys
import unicodedata

import numpy as np
import pandas as pd

UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB",
       "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}

COL = {
    "perfil": "Código PA",
    "trabalho": "Código Trabalho",
    "numero_pa": "Número PA",
    "data": "Data da Coleta",
    "uf": "UF",
    "municipio": "Município",
    "uso": "Uso Atual",
    "classe_n1": "Classe de Solos Nível 1",
    "classe_n2": "Classe de Solos Nível 2",
    "classe_atual": "Classificação Atual",
    "link": "Link para Descrição em PDF",
    "lat_g": "Latitude Graus", "lat_m": "Latitude Minutos", "lat_s": "Latitude Segundos",
    "lat_h": "Latitude Hemisfério",
    "lon_g": "Longitude Graus", "lon_m": "Longitude Minutos", "lon_s": "Longitude Segundos",
    "sup": "Profundidade Superior", "inf": "Profundidade Inferior",
    "ph": "pH - H2O",
    "v": "Complexo Sortivo - Valor V &Delta; Saturação por Bases (100. S/T)%",
    "sb": "Complexo Sortivo - Valor S (Ca2++Mg2++K++Na+)",
    "ctc": "Complexo Sortivo - Valor T (S+H++Al3+)",
    "m_al": "Complexo Sortivo - Saturação por Alumínio (100. Al3+/S+Al3+)%",
    "argila": "Composição Granulométrica da terra fina - Argila (g/Kg)",
    "c_org": "Carbono orgânico",
    "p": "Fósforo assimilável (mg/kg)",
    "ds": "Densidade - Solo (aparente)",
    "cascalho": "Frações da Amostra Total - Cascalho (g/Kg)",
    "calhau": "Frações da Amostra Total - Calhaus (g/Kg)",
}

# faixas plausíveis; fora delas o valor vira NaN
FAIXAS = {"ph": (3.0, 10.0), "v": (0, 100), "m_al": (0, 100), "argila": (0, 1000),
          "c_org": (0, 600), "ctc": (0, 300), "sb": (0, 300), "p": (0, 1000), "ds": (0.1, 2.3),
          "cascalho": (0, 1000), "calhau": (0, 1000)}

PADRAO_USO_AGRICOLA = ("lavoura|cultur|soja|milho|cana|caf[eé]|plantio|arroz|feij|trigo|"
                       "mandioca|algod|reflorest|eucalip|pinus|horta|fruti")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False)
                         .str.replace("<", "", regex=False).str.strip(), errors="coerce")


def _sem_acento(s: pd.Series) -> pd.Series:
    return s.astype(str).map(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii"))


def densidade_benites(argila_gkg, c_gkg, sb_cmolc):
    """Função de pedotransferência (Benites et al., 2007) — g/cm³."""
    ds = 1.56 - 0.0005 * argila_gkg - 0.01 * c_gkg + 0.0075 * sb_cmolc
    return np.clip(ds, 0.5, 1.9)


def preprocessar(caminho_csv: str, prof_max_cm: float = 20.0) -> pd.DataFrame:
    bruto = pd.read_csv(caminho_csv, sep=";", low_memory=False)
    d = pd.DataFrame({k: bruto[v] for k, v in COL.items() if v in bruto.columns})

    d = d[d["uf"].isin(UFS)].copy()                 # descarta linhas desalinhadas
    for k in list(FAIXAS) + ["sup", "inf", "lat_g", "lat_m", "lat_s", "lon_g", "lon_m", "lon_s", "perfil"]:
        d[k] = _num(d[k])
    for k, (lo, hi) in FAIXAS.items():
        d.loc[(d[k] < lo) | (d[k] > hi), k] = np.nan
    d.loc[(d["sup"] > 1000) | (d["inf"] > 1000), ["sup", "inf"]] = np.nan

    # identificador de perfil: Código PA; se ausente, trabalho + número do ponto
    d["id_perfil"] = d["perfil"].astype("Int64").astype(str)
    sem_id = d["perfil"].isna()
    d.loc[sem_id, "id_perfil"] = "T" + d.loc[sem_id, "trabalho"].astype(str) + "-" + d.loc[sem_id, "numero_pa"].astype(str)

    # sobreposição de cada horizonte com 0–prof_max cm
    d["esp"] = (np.minimum(d["inf"], prof_max_cm) - d["sup"]).clip(lower=0)
    camada = d[(d["sup"] < prof_max_cm) & (d["esp"] > 0)].copy()

    # densidade: medida ou estimada
    ds_est = densidade_benites(camada["argila"], camada["c_org"], camada["sb"].fillna(0))
    camada["ds_medida"] = camada["ds"].notna()
    camada["ds_usada"] = camada["ds"].fillna(ds_est)
    grosso = (camada["cascalho"].fillna(0) + camada["calhau"].fillna(0)).clip(0, 1000) / 1000
    # estoque de C (t/ha) = C (g/kg) × Ds (g/cm³) × espessura (cm) × (1 − fração grossa) × 0,1
    camada["estoque_c"] = camada["c_org"] * camada["ds_usada"] * camada["esp"] * (1 - grosso) * 0.1

    def media_ponderada(g: pd.DataFrame, col: str) -> float:
        ok = g[col].notna() & (g["esp"] > 0)
        return float(np.average(g.loc[ok, col], weights=g.loc[ok, "esp"])) if ok.any() else np.nan

    linhas = []
    for pid, g in camada.groupby("id_perfil", sort=False):
        esp_total = g["esp"].sum()
        cobertura_c = g.loc[g["estoque_c"].notna(), "esp"].sum()
        estoque = g["estoque_c"].sum() * (esp_total / cobertura_c) if cobertura_c > 0 else np.nan
        linhas.append({
            "id_perfil": pid,
            "ph": media_ponderada(g, "ph"),
            "v_pct": media_ponderada(g, "v"),
            "argila_pct": media_ponderada(g, "argila") / 10,
            "c_org_gkg": media_ponderada(g, "c_org"),
            "ctc_cmolc": media_ponderada(g, "ctc"),
            "m_al_pct": media_ponderada(g, "m_al"),
            "p_mgkg": media_ponderada(g, "p"),
            "ds_gcm3": media_ponderada(g, "ds_usada"),
            "ds_medida": bool(g["ds_medida"].any()),
            # estoque na profundidade coberta (até 20 cm); solos rasos não são extrapolados
            "estoque_c_0_20_tha": estoque,
            "prof_coberta_cm": esp_total,
        })
    atrib = pd.DataFrame(linhas)

    # metadados por perfil (primeiro horizonte)
    meta = d.sort_values("sup").groupby("id_perfil", sort=False).first().reset_index()
    lat = meta["lat_g"] + meta["lat_m"].fillna(0) / 60 + meta["lat_s"].fillna(0) / 3600
    lat = np.where(meta["lat_h"].astype(str).str.startswith("Norte"), lat, -lat)
    lon = -(meta["lon_g"] + meta["lon_m"].fillna(0) / 60 + meta["lon_s"].fillna(0) / 3600)  # Brasil: oeste
    meta["lat"] = lat
    meta["lon"] = lon
    fora = ~((meta["lat"].between(-34, 6)) & (meta["lon"].between(-74, -28)))
    meta.loc[fora, ["lat", "lon"]] = np.nan
    meta["ano_coleta"] = _num(meta["data"].astype(str).str[-4:])
    meta.loc[~meta["ano_coleta"].between(1900, 2030), "ano_coleta"] = np.nan
    meta["uso_agricola"] = meta["uso"].astype(str).str.lower().str.contains(PADRAO_USO_AGRICOLA, regex=True)
    meta["municipio_chave"] = _sem_acento(meta["municipio"]).str.upper().str.strip()

    perfis = meta[["id_perfil", "uf", "municipio", "municipio_chave", "lat", "lon", "ano_coleta",
                   "classe_n1", "classe_n2", "classe_atual", "uso", "uso_agricola", "link"]].merge(
        atrib, on="id_perfil", how="inner")
    perfis = perfis[perfis["ph"].notna() | perfis["v_pct"].notna()].reset_index(drop=True)
    return perfis


# --------------------------------------------------------------------------- consultas

def carregar_perfis(caminho: str) -> pd.DataFrame:
    return pd.read_csv(caminho, dtype={"id_perfil": str})


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def filtrar(perfis: pd.DataFrame, uf: str | None = None, municipio: str | None = None,
            lat: float | None = None, lon: float | None = None, raio_km: float | None = None,
            classes_n1: list[str] | None = None, so_uso_agricola: bool = False) -> pd.DataFrame:
    sel = perfis
    if uf:
        sel = sel[sel["uf"] == uf]
    if municipio:
        chave = unicodedata.normalize("NFKD", municipio).encode("ascii", "ignore").decode("ascii").upper().strip()
        sel = sel[sel["municipio_chave"] == chave]
    if lat is not None and lon is not None and raio_km:
        dist = distancia_km(lat, lon, sel["lat"], sel["lon"])
        sel = sel.assign(dist_km=dist)
        sel = sel[sel["dist_km"] <= raio_km].sort_values("dist_km")
    if classes_n1:
        sel = sel[sel["classe_n1"].isin(classes_n1)]
    if so_uso_agricola:
        sel = sel[sel["uso_agricola"]]
    return sel


def resumo(sel: pd.DataFrame) -> pd.DataFrame:
    cols = ["ph", "v_pct", "argila_pct", "c_org_gkg", "ctc_cmolc", "m_al_pct", "estoque_c_0_20_tha"]
    return sel[cols].describe(percentiles=[0.1, 0.5, 0.9]).T[["count", "10%", "50%", "90%"]]


def resumo_municipios(perfis: pd.DataFrame) -> pd.DataFrame:
    return (perfis.groupby(["uf", "municipio"])
            .agg(n_perfis=("id_perfil", "count"), ph_mediano=("ph", "median"),
                 v_mediano=("v_pct", "median"), argila_mediana=("argila_pct", "median"),
                 estoque_c_mediano=("estoque_c_0_20_tha", "median"))
            .reset_index().sort_values(["uf", "municipio"]))


if __name__ == "__main__":
    origem = sys.argv[1] if len(sys.argv) > 1 else "bd_solos_para_redape.csv"
    destino = sys.argv[2] if len(sys.argv) > 2 else "perfis_bdsolos_0_20.csv"
    p = preprocessar(origem)
    p.to_csv(destino, index=False)
    print(f"{len(p)} perfis gravados em {destino}")
    print(resumo(p).round(2))
