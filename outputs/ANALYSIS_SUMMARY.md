# World Bank Unemployment & GDP — Analysis Summary

## Scope

Annual observations from 2000–2025 for South Africa, Botswana, Namibia, Kenya, and Brazil. The peer set pairs South Africa's two SADC neighbours with Kenya as a sub-Saharan African comparator and Brazil as a large emerging-economy comparison. Comparisons are descriptive, not a country ranking or causal evaluation.

## Latest overlapping observations

| country | latest_paired_year | latest_unemployment_pct | latest_real_gdp_growth_pct |
| --- | --- | --- | --- |
| South Africa | 2025 | 32.39 | 1.11 |
| Botswana | 2025 | 24.48 | -0.73 |
| Namibia | 2025 | 19.29 | 1.73 |
| Kenya | 2025 | 5.45 | 4.63 |
| Brazil | 2025 | 5.97 | 2.29 |

GDP growth is the World Bank annual growth rate in constant local currency. The separate real-GDP trend is expressed in constant 2015 US dollars and indexed within each country to 2015 = 100.

## South Africa: unemployment and GDP growth

Across 26 annual paired observations, the Pearson correlation between the modeled unemployment rate and real GDP growth is **-0.39**. This describes co-movement in the selected years; it does not establish that GDP growth causes unemployment changes. Results can be influenced by business-cycle lags, labor-force participation, economic structure, shocks, revisions, and the short annual time series.

## Source indicators

- `SL.UEM.TOTL.ZS` — Unemployment, total (% of labor force, modeled ILO estimate); API last updated: 2026-10-08.
- `NY.GDP.MKTP.KD.ZG` — GDP growth (annual %, constant local currency); API last updated: 2026-10-08.
- `NY.GDP.MKTP.KD` — GDP (constant 2015 US$); API last updated: 2026-10-08.

Source: [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386). Indicator pages: [unemployment](https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS), [GDP growth](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG), and [real GDP](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD). World Bank open data is generally offered under [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by); cite the World Bank and the original source noted on each indicator page.

## Data caveats

- Unemployment is the **modeled ILO estimate**, not a national official estimate or a direct household-survey extract. It is an estimate and may be revised.
- Country-year series do not necessarily have identical availability. Missing values are retained as missing; each chart and correlation uses available paired observations.
- GDP growth in constant local currency is used for annual growth rates; real GDP in constant 2015 US dollars is used only as a normalized comparison series. Current-US-dollar GDP would mix real output changes with exchange-rate and price changes.
- GDP and unemployment may have timing lags and structural differences. Correlation is descriptive only; no causal claims, significance testing, or prediction is made.
- The API data are retrieved when the script runs; the accompanying source CSV and metadata record the values used in this published analysis.
