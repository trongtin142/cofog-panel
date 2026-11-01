# Replication: decentralised environmental spending and PM2.5 exposure

Reproduces all tables and figures of the article "Decentralised environmental spending, administrative capacity and PM2.5 exposure: evidence from 110 countries".

## Run

```bash
pip install -e .[replication]
python replication/sjiaos/evaluate_harmonisation.py   # builds the harmonised panel
python replication/eeps/env_federalism.py
```

Outputs are written to `replication/eeps/output/`: the tables `tabC1_descriptives`, `tabC2_main`, `tabC3_mundlak`, `tabC3b_twfe`, `tabC4_robustness` and `tabC4b_leave_one_out` (CSV), the sample composition `sample_composition.json`, the figures `figC1_marginal_subshare` and `figC2_ge_by_source` (PNG at 600 dpi and PDF), and the estimation panel `paperC_panel.csv`. Tested with Python 3.14, pandas 3.0, statsmodels 0.14, matplotlib 3.10.

## Data

The harmonised COFOG 05 panel comes from the SJIAOS replication (`replication/sjiaos/output/harmonised_all_divisions.csv`), so it needs the IMF extract described in `replication/sjiaos/README.md` (release of 3 February 2026); another release gives different numbers. External data in `data_ext/` were downloaded from the World Bank API on 20 October 2026: World Development Indicators (PM2.5 exposure EN.ATM.PM25.MC.M3; GDP per capita PPP NY.GDP.PCAP.PP.KD; industry NV.IND.TOTL.ZS; urban population SP.URB.TOTL.IN.ZS; trade NE.TRD.GNFS.ZS; population density EN.POP.DNST; natural resource rents NY.GDP.TOTL.RT.ZS) and Worldwide Governance Indicators (government effectiveness GOV_WGI_GE.EST; control of corruption GOV_WGI_CC.EST), period 1990–2024 (WGI 1996–2024). WDI and WGI data are licensed CC BY 4.0; cite "World Bank, World Development Indicators" and "World Bank, Worldwide Governance Indicators".
