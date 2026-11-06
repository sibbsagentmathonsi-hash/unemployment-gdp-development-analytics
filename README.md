# World Bank Unemployment & GDP Analytics

A reproducible project analyzing annual unemployment and GDP indicators for **South Africa, Botswana, Namibia, Kenya, and Brazil**. South Africa is the focus; Botswana and Namibia are neighbouring SADC comparisons, Kenya adds a sub-Saharan African comparator, and Brazil provides a larger emerging-economy comparison.

The project downloads data from the official [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386), aligns country-year observations, keeps missing years explicit, calculates transparent derived measures, and creates a formatted Excel workbook, charts, CSV data, and a short report.

## Included analysis

- Modelled ILO unemployment rate trends and country comparisons.
- GDP growth in constant local currency, suitable for studying real annual growth.
- Real GDP in constant 2015 US dollars, indexed within each country to **2015 = 100** to compare trends at different scales.
- Annual unemployment changes in percentage points and calculated growth of the constant-2015-US$ GDP series.
- Descriptive pairwise correlations between unemployment and GDP series by country, with paired-year counts.
- Data availability, source indicator IDs, API URLs, retrieval date, and license attribution.
- Excel overview dashboard, annual data table with formulas, country summaries, correlation results, charts, and methodology/source notes.

## Run the analysis

Requires Python 3.10+ and internet access to retrieve the latest available observations from the World Bank API.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python analytics.py
```

By default, the script requests 2000–2025. Change the period as needed:

```powershell
python analytics.py --start-year 1995 --end-year 2025
```

The generated files are written to `outputs/`. Rerunning the script refreshes the downloaded API values and replaces the same output filenames. No API key is required.

## Main deliverables

| File | Purpose |
| --- | --- |
| `outputs/world_bank_unemployment_gdp_analysis.xlsx` | Excel dashboard, annual data, formulas, country summary, correlations, and methodology |
| `outputs/ANALYSIS_SUMMARY.md` | Headline observations, South Africa correlation, definitions, and caveats |
| `outputs/world_bank_annual_data.csv` | Combined country-year indicators and calculated measures |
| `outputs/missing_values.csv` | Field-by-field register explaining unavailable or undefined values |
| `outputs/country_summary.csv` | Latest paired values and unemployment span summaries |
| `outputs/correlations.csv` | Country correlations with the number of paired observations |
| `outputs/source_metadata.json` | Indicator IDs, API URLs, retrieval date, last-updated dates, and license reference |
| `outputs/charts/*.png` | Unemployment trends, indexed real-GDP trends, South Africa scatter, and correlation heatmap |

## Measures and interpretation

- **Unemployment rate:** World Bank indicator `SL.UEM.TOTL.ZS`, *Unemployment, total (% of total labor force) (modeled ILO estimate)*. This is a modeled international series, not the national official unemployment measure.
- **GDP growth:** `NY.GDP.MKTP.KD.ZG`, annual percentage growth in constant local currency. This is used to compare annual growth without directly using nominal GDP.
- **Real GDP level:** `NY.GDP.MKTP.KD`, GDP in constant 2015 US dollars. For each country, the output divides each observation by that country's 2015 value and multiplies by 100. A missing 2015 value leaves that country's index missing.
- **Constant-US$ GDP growth:** percentage change of the constant-2015-US$ GDP level. It is not expected to match the World Bank constant-local-currency growth indicator, since the indicators use different currency units and source calculations.
- **Annual unemployment change:** current year's unemployment rate minus the preceding year's rate, in percentage points.
- **Correlation:** Pearson correlation for available paired annual observations within each country. The paired observation count is reported for context.

The first year in each country series has no prior-year comparison; unemployment change and constant-US$ GDP growth are marked `N/A: no prior year` in the annual CSV and workbook. The missing-value register records each cell and reason. Source observations unavailable from the World Bank are labeled `Not reported by World Bank`. These statuses are never treated as zero.

Annual correlation is descriptive; it does not establish causality or account for lagged effects, structural changes, economic shocks, estimation uncertainty, or revisions. Country series can have different coverage and may not be directly comparable as official national headline rates.

## Sources and license

The indicator pages list the source information and the World Bank's [CC BY 4.0 license reference](https://datacatalog.worldbank.org/public-licenses#cc-by):

- [Unemployment, total (% of labor force, modeled ILO estimate)](https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS)
- [GDP growth (annual %, constant local currency)](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG)
- [GDP (constant 2015 US$)](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD)

Attribute the World Bank and the original providers listed on the relevant indicator pages when reusing the data. API response metadata and exact URLs used are preserved in `outputs/source_metadata.json`.
