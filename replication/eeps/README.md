# Replication: decentralised environmental spending and air pollution

Reproduces all tables and figures of the article "Decentralised environmental protection expenditure, government effectiveness and air pollution: cross-country evidence from harmonised IMF GFS data".

## Run

```bash
pip install -e .[replication]
python replication/sjiaos/evaluate_harmonisation.py   # builds the harmonised panel
python replication/eeps/env_federalism.py
```

Outputs are written to `replication/eeps/output/` (`tabC1`–`tabC5`, `figC1`–`figC3`, and the estimation panel `paperC_panel.csv`).

## Data

The harmonised COFOG 05 panel comes from the SJIAOS replication. External data in `data_ext/` were downloaded from the World Bank API on 20 October 2026: World Development Indicators (PM2.5 exposure EN.ATM.PM25.MC.M3; CO2 per capita excluding LULUCF EN.GHG.CO2.PC.CE.AR5; GDP per capita PPP NY.GDP.PCAP.PP.KD; industry NV.IND.TOTL.ZS; urban population SP.URB.TOTL.IN.ZS; trade NE.TRD.GNFS.ZS; population density EN.POP.DNST; natural resource rents NY.GDP.TOTL.RT.ZS) and Worldwide Governance Indicators (government effectiveness GOV_WGI_GE.EST; control of corruption GOV_WGI_CC.EST), period 1990–2024 (WGI 1996–2024). WDI and WGI data are licensed CC BY 4.0; cite "World Bank, World Development Indicators" and "World Bank, Worldwide Governance Indicators".
