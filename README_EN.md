# BioCrédito Agro — biochar adoption simulator (English version)

Monte Carlo decision-support app for financing biochar application in Brazilian agriculture through
P2P lending, cooperatives and smart contracts. It implements the framework proposed in
*Biochar framework for carbon capture and credit certification across regulatory standards*
(Buratto et al., GCB Bioenergy, manuscript) and validates the agronomic and carbon modules against five papers.

## Run

```bash
pip install -r requirements.txt
streamlit run app_en.py     # English interface
streamlit run app.py        # Portuguese interface
```

On Streamlit Community Cloud, create a second app from the same repository with `app_en.py` as the main file.

## What the app does

| Tab | Output |
| --- | --- |
| My municipality | For a municipality in Paraná or Santa Catarina: viability verdict, yield increase (%, t/ha, R$/ha/yr), carbon retained in soil and creditable removal, probability of paying off with and without carbon, break-even points, and soil compared with the state |
| PR and SC ranking | All municipalities with Embrapa BDsolos soil profiles, map and CSV |
| Two benefits | Decomposition of present value into yield, input savings and carbon; viability classes; carbon price × yield viability map |
| Embedded credit and fund | Tranched fund (senior: investors and P2P; subordinated: cooperative), origination package (JSON + SHA-256) and embedded-credit request (OpenAPI spec in `openapi.yaml`) |
| Validation (literature) | Observed vs. predicted yield and soil carbon; eligibility of reference biochars by standard |
| Framework (GCB paper) | Figures 1–3 and Table 3 of the base paper and where each element is implemented |

## Model

- Yield: ΔB = Y₀ · r · P + input savings − application cost, with r depending on pH, base saturation, clay and soil
  organic C (BDsolos profiles), biochar type, a saturating dose factor (1.0 at 15 t/ha), a fertilisation factor
  (0.4 with NPK; 1.3 structural / 3.5 nutrient-rich biochar without fertilisation) and 10% annual decay.
- Carbon: CO₂e = dose · C_org · F_perm(H/C) · 44/12 − LCA emissions, credited only if the biochar meets the selected
  standard (IBI, EBC, BQM, ANZBI, CNAIS I/II, SGS; limits from Lin et al., 2025).
- Finance: NPV over the horizon with a P2P loan (grace period + annuity), default when debt service exceeds the
  available margin; fund waterfall with a one-factor Gaussian copula for correlated defaults.

Fitted factors reduce the mean absolute error against five field results from 17.0 to 3.5 percentage points; this
is in-sample fit, not independent validation. Not validated by the papers: input savings, dose half-saturation
(5 t/ha) and crop-specific responses under full fertilisation.

## Data

- `perfis_bdsolos_0_20.csv`: 7,676 soil profiles (0–20 cm) derived from the Embrapa BDsolos export with `bdsolos.py`.
  Profiles are mostly from old surveys under native vegetation or pasture; a liming correction is available.

## References

- Chagas, J. K. M. et al. (2024). Soil Use and Management 40, e70001. https://doi.org/10.1111/sum.70001
- Latawiec, A. E. et al. (2019). Scientific Reports 9, 11993. https://doi.org/10.1038/s41598-019-47647-x
- Rani, R.; Garg, N. (2025). Journal of Soil Science and Plant Nutrition 25, 3285–3305. https://doi.org/10.1007/s42729-025-02335-w
- Al-Gaashani, R. et al. (2026). Scientific Reports 16, 23914. https://doi.org/10.1038/s41598-026-54140-9
- Lin, G. et al. (2025). Bioresource Technology Reports 29, 102059. https://doi.org/10.1016/j.biteb.2025.102059
- Jeffery, S. et al. (2017). Environmental Research Letters 12, 053001. https://doi.org/10.1088/1748-9326/aa67bd

## Maintenance

`app_en.py` is generated from `app.py` by `python gerar_app_en.py` (translations in the script and in `i18n_en.py`).
After changing `app.py`, rerun the generator; it stops with an error if a text or code block no longer matches.

## Carbon markets tab

`mercados.py` holds the rules and prices of the SBCE, GX-ETS/J-Credit (Japan), CRCF/Puro and EU ETS (EU) and California; `aba_mercados.py` renders the tab (PT and EN). Update prices in `MERCADOS` before publishing. Use at least 10,000 simulations per municipality: many municipalities lie close to the 0.70 threshold.
