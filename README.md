# BioCrédito Agro — simulador

Simulador Monte Carlo do framework BioCrédito Agro: biocarvão aplicado na lavoura, financiado por P2P lending (SEP), com receita opcional de crédito de carbono.

## Arquivos

- `simulador.py` — núcleo de cálculo, sem dependência de interface. Importável em notebooks, scripts ou outros apps.
- `app.py` — interface Streamlit.
- `bdsolos.py` — pré-processamento e consultas aos perfis do BDsolos.
- `regioes.py` — avaliação e ranking de municípios (PR e SC).
- `fundo.py` — fundo com cotas sênior (investidores e P2P) e subordinada (cooperativa), com cascata e inadimplência correlacionada.
- `originacao.py` — pacote de originação (JSON + JSON Schema + hash SHA-256) e cliente de crédito embutido da agfintech.
- `validacao.py` — validação com a literatura: ensaios de campo, presets de biocarvão, limites dos padrões, conteúdo do artigo GCB e referências.
- `openapi.yaml` — especificação OpenAPI 3.1 da integração cooperativa ↔ agfintech/SEP ↔ fundo.
- `requirements.txt` — dependências.

## Rodar

```bash
pip install -r requirements.txt
python simulador.py          # cenário-base no terminal
streamlit run app.py         # interface web
```

Para encaixar num app Streamlit multipágina existente, copie `app.py` para a pasta `pages/` (ex.: `pages/3_BioCredito.py`) e deixe `simulador.py` na raiz do app. Remova a linha `st.set_page_config` se o app principal já a define.

## Uso programático

```python
from simulador import Cenario, simular, analise_sensibilidade

c = Cenario()
c.solo.ph_agua = 5.0
c.biocarvao.dose_t_ha = 1.5
c.resposta.ensaios_observados = [0.05, 0.08, 0.03]   # ensaios da cooperativa
out = simular(c)
print(out["resumo"])
df = out["simulacoes"]                                 # uma linha por simulação

analise_sensibilidade(c, "carbono.preco_max_usd_t", [120, 200, 300])
```

## Modelo

| Módulo | Equação |
| --- | --- |
| Agronômico | ΔB_agro,t = Y0 · r_t · P_cult + S_cal + S_fert − C_apl |
| Carbono | CO2e_liq = M_bc · C_org · F_perm(H/Corg, T) · 44/12 − E_ACV |
| Financeiro | VPL = Σ (ΔB_agro,t + R_CO2,t − A_t) / (1+i)^t |

- `r_t`: priori normal com média sugerida pelo solo (âncora: +25% médio nos trópicos, ~0 em clima temperado, Jeffery et al. 2017) e atualização bayesiana com ensaios.
- Elegibilidade de carbono: H/Corg < 0,7 e O/Corg < 0,4 (Figura 1 do artigo GCB Bioenergy).
- Empréstimo: juros na carência e Price depois, parcelas anuais na safra.
- Inadimplência: em algum ano, (margem comprometível + ganho do biocarvão + carbono) < parcela.
- Investidor: perda = saldo devedor no default × LGD.
- Regra de decisão proposta: aprovar se P(VPL>0) ≥ 0,70 **sem** carbono (carbono como upside).

## Perfis de solo do BDsolos (Embrapa)

`bdsolos.py` reduz o export do BDsolos (`bd_solos_para_redape.csv`, um registro por horizonte) a `perfis_bdsolos_0_20.csv`: um registro por perfil, com a camada 0–20 cm ponderada pela espessura (pH, V%, argila, C orgânico, CTC, saturação por Al, P), coordenadas decimais, classe de solo, uso atual e estoque de C 0–20 cm (t/ha).

```bash
python bdsolos.py bd_solos_para_redape.csv perfis_bdsolos_0_20.csv   # ~30 s, gera ~3 MB
```

O arquivo já processado vai junto; o CSV bruto (97 MB) não precisa ir para o repositório do Streamlit Cloud.

No app, filtre por UF, município, raio a partir de coordenadas, classe de solo e uso agrícola. Cada simulação sorteia um perfil da seleção e calcula a resposta esperada a partir do pH e V% dele. Assim, a variabilidade real dos solos da região entra no resultado.

Limpeza aplicada: linhas desalinhadas descartadas (UF inválida) e valores fora de faixa viram ausentes (pH 3–10, V% 0–100, argila 0–1000 g/kg etc.). A densidade foi medida em só ~15% dos perfis; nos demais, é estimada por pedotransferência (Benites et al., 2007). Confira os coeficientes em `densidade_benites` antes de publicar.

**Correção de manejo.** A mediana de coleta é ~1979, e a maioria dos perfis está sob vegetação nativa ou pastagem. Em lavoura corrigida, pH e V% atuais são maiores. A opção "Lavoura corrigida" (padrão: pH ≥ 5,5 e V% ≥ 60) eleva os valores sorteados a esse mínimo. Essa escolha muda muito o resultado: no Paraná, a chance de VPL positivo sem carbono cai bastante quando se assume lavoura corrigida (ver aba "Duas vantagens").

## Saúde do solo (Embrapa — Plataforma Saúde do Solo BR / BioAS)

O simulador aceita indicadores da plataforma pública `https://saudedosolo.embrapa.gov.br/plataforma-publica` de duas formas:

1. **Classe do município** — a classe de saúde predominante (saudável, recuperando, intermediário, adoecendo, doente) e o nº de amostras. Preencha `modelo_municipios_saude_solo.csv` com o que a plataforma mostra para os municípios do piloto e carregue no app. Como a classe é a moda do município, o simulador aumenta a incerteza, e mais ainda com poucas amostras.
2. **Laudo BioAS do talhão** — escores F1 (ciclar), F2 (armazenar), F3 (suprir) e IQS FertBio, de 0 a 1, emitidos por laboratório da Rede BioAS.

Efeito no modelo (`ajuste_saude_solo`): multiplica a média a priori da resposta r_t. Hipótese: o biocarvão atua sobretudo em F2 e F3, então a resposta esperada é maior onde esses escores são baixos. Os coeficientes são provisórios e devem ser calibrados com ensaios.

A plataforma não publica API nem download documentados; a leitura é manual ou via CSV. Para acesso em lote, consulte a Embrapa.

## Avaliação das duas vantagens (aba "Duas vantagens")

O app separa o valor presente do projeto em custo, aumento de produtividade, economia de insumos e crédito de carbono. Com isso, mostra:

- quanto do custo cada vantagem cobre sozinha;
- a fração das simulações em que: cada vantagem sozinha paga; só a produtividade paga; só o carbono paga; **só as duas juntas pagam**; é inviável;
- pontos de equilíbrio: preço de carbono necessário (com e sem ganho de produtividade) e aumento de produtividade necessário (com e sem carbono);
- mapa de viabilidade: P(VPL>0) para cada par preço do carbono × aumento médio de produtividade. O VPL é linear nos dois, então a grade reaproveita as simulações (função `mapa_viabilidade`).

Regras de decisão: `produtividade` (só a vantagem agronômica conta; carbono é bônus) ou `combinada` (soma as duas, com desconto de prudência sobre o carbono, padrão 30%).

## Ranking regional (aba "Ranking PR e SC")

`regioes.avaliar_municipios` roda o simulador com os perfis de cada município e calcula: aumento de produtividade esperado, ganho em R$/ha, incremento relativo do estoque de C 0–20 cm (C do biocarvão ÷ estoque nativo), remoção creditável, P(VPL>0) com e sem carbono e o índice combinado (média dos percentis de produtividade e de carbono). O app mostra mapa, tabela e download em CSV.

A resposta de produtividade depende de pH, V%, argila e C orgânico (`resposta_media_vetor`). Textura e C entram porque a calagem não os altera, e assim as regiões se diferenciam mesmo com a correção de manejo. Todos os fatores são hipóteses a calibrar com ensaios.

## Cultura

O seletor de cultura preenche produtividade, preço, volatilidade e margem com valores de referência aproximados (`CULTURAS` em `simulador.py`). Substitua pelos dados da cooperativa, CONAB ou CEPEA. A cultura muda o valor do ganho (produtividade × preço) e a capacidade de pagamento. O `fator_resposta_cultura` (padrão 1,0) multiplica o aumento relativo ao biocarvão; mude-o só com ensaios da cultura.

## Crédito embutido e fundo (aba "Crédito embutido e fundo")

**Fundo.** A carteira é formada por N operações iguais à simulada. A inadimplência é correlacionada por um fator comum (cópula gaussiana). A cascata paga despesas, depois a sênior (principal mais remuneração-alvo) e por fim a subordinada. A aba mostra:
- chance de perda e perda esperada da sênior;
- múltiplo da subordinada;
- curva de subordinação e subordinação mínima para chance de perda da sênior ≤ 1%.

A cessão de parte da receita de carbono ao fundo funciona como reforço de crédito.

**Originação.** Preencha cooperativa, produtor (ID pseudonimizado), CAR, fornecedor, canal e consentimento (LGPD). O app gera o pacote JSON, valida contra o esquema e confere o hash. O botão "Enviar à agfintech" chama `POST /v1/originacoes` na URL informada. Sem URL, roda em modo simulado com uma política de crédito ajustável.

**API.** A `openapi.yaml` cobre: originação → decisão → aceite (CCB e CPR) → marcos do contrato com hash das evidências (o marco `entregue` libera o pagamento ao fornecedor) → cessão ao fundo → carteira, além de webhooks. Autenticação por OAuth2 client credentials com mTLS, e `Idempotency-Key` em todo POST.

## Validação com a literatura (aba "Validação")

| Artigo | Uso no app |
| --- | --- |
| Chagas et al. (2024), *Soil Use and Management* 40:e70001 | Fator de adubação com NPK (0,4); sem NPK com biocarvão de nutriente (3,5); decaimento do efeito; C retido medido (≈ 3,0 t C/ha com 30 t/ha de lodo a 500 °C); presets de lodo de esgoto |
| Latawiec et al. (2019), *Scientific Reports* 9:11993 | Fator sem adubação com biocarvão estrutural (1,3; Brachiaria +27%); 13 tCO₂e/ha no solo; custo de US$ 6.410/ha para 15 t/ha |
| Rani & Garg (2025), *J. Soil Sci. Plant Nutr.* 25:3285–3305 | Ordem de grandeza: meta-análises com +13% e ≈ +20%; soja +7% com 20 t/ha |
| Al-Gaashani et al. (2026), *Scientific Reports* 16:23914 | Presets por matéria-prima e temperatura: H/C 0,79–0,99 a 300 °C; 0,30–0,42 a ≥ 500 °C; C 54,8% (verde) e 66,1% (lenhoso) |
| Lin et al. (2025), *Bioresour. Technol. Rep.* 29:102059 | Limites de C, H/C e O/C por padrão (IBI, EBC, BQM, ANZBI, CNAIS I/II, SGS) |
| Buratto et al., *GCB Bioenergy* (manuscrito) | Aba "Framework": Figuras 1–3 e Tabela 3 (preços viáveis por ETS, selecionáveis como cenário) |

Mudanças no modelo:
- **Fator de dose** saturante, igual a 1,0 a 15 t/ha (a dose dos ensaios). A meia-saturação de 5 t/ha é hipótese: não há ensaios com dose baixa.
- **Fator de adubação × tipo de biocarvão:** com NPK, 0,4; sem adubação, 1,3 (estrutural) ou 3,5 (nutriente).
- **Decaimento** padrão de 10% ao ano.
- **Elegibilidade por padrão** de certificação.
- **Carbono físico retido no solo**, informado mesmo quando o biocarvão não gera crédito.

Erro médio absoluto nos cinco ensaios: 17,0 p.p. (modelo anterior) → 3,5 p.p. (calibrado). Os fatores foram ajustados nesses mesmos ensaios, então isso mede ajuste, não validação independente.

## Atenção

Valores padrão são ilustrativos. Antes de usar em artigo ou decisão de crédito:

1. Calibre a heurística `sugerir_resposta_media` com ensaios de campo.
2. Confirme os coeficientes do fator de permanência (`perm_intercepto`, `perm_inclinacao`, ajuste de temperatura) na tabela da metodologia escolhida (EBC/WBC, Puro.earth, Verra VM0044, Isometric).
3. Substitua `e_acv_tco2e_t` pela ACV do fornecedor.
