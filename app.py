"""
BioCrédito Agro — entrada única do app, com seletor de idioma na barra lateral.

Rodar localmente:   streamlit run app.py
Interface em português: app_pt.py · Interface em inglês: app_en.py (gerada por gerar_app_en.py).
Link direto para o inglês: acrescente ?lang=en ao endereço do app.
"""

import runpy
from pathlib import Path

import streamlit as st

# set_page_config só pode valer uma vez por execução: chamamos aqui e neutralizamos
# a chamada que existe dentro de app_pt.py / app_en.py.
_real = getattr(st, "_set_page_config_real", st.set_page_config)
st._set_page_config_real = _real
_real(page_title="BioCrédito Agro", layout="wide")
st.set_page_config = lambda *a, **k: None

IDIOMAS = {"pt": ("Português", "app_pt.py"), "en": ("English", "app_en.py")}
_lang_url = st.query_params.get("lang", "pt")
if _lang_url not in IDIOMAS:
    _lang_url = "pt"

with st.sidebar:
    lang = st.radio("Idioma / Language", list(IDIOMAS), index=list(IDIOMAS).index(_lang_url),
                    format_func=lambda k: IDIOMAS[k][0], horizontal=True, key="idioma")

if st.query_params.get("lang") != lang:
    st.query_params["lang"] = lang

runpy.run_path(str(Path(__file__).with_name(IDIOMAS[lang][1])), run_name="__main__")
