"""Organização das abas do app: as essenciais no topo e as técnicas agrupadas numa aba só.

Para mudar quais abas aparecem no topo, edite ESSENCIAIS (posições na lista de rótulos de app_pt.py).
"""

ROTULO_TECNICO = "Análises técnicas"
ROTULO_TECNICO_EN = "Technical analyses"

# 0 Início rápido · 1 Meu município · 3 Brasil — áreas degradadas · 5 Mercados de carbono
# 6 Resumo da operação · 7 Crédito embutido e fundo
ESSENCIAIS = (0, 1, 3, 5, 6, 7)


def criar_abas(st, rotulos, rotulo_tecnico=ROTULO_TECNICO):
    """Cria as abas e devolve uma por rótulo, na ordem original da lista."""
    ess = [i for i in ESSENCIAIS if i < len(rotulos)]
    tec = [i for i in range(len(rotulos)) if i not in ess]
    topo = st.tabs([rotulos[i] for i in ess] + ([rotulo_tecnico] if tec else []))
    saida = [None] * len(rotulos)
    for k, i in enumerate(ess):
        saida[i] = topo[k]
    if tec:
        with topo[-1]:
            internas = st.tabs([rotulos[i] for i in tec])
        for k, i in enumerate(tec):
            saida[i] = internas[k]
    return saida
