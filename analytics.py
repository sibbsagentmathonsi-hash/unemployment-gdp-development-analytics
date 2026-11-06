#!/usr/bin/env python3
"""Download public World Bank indicators and build reproducible country comparisons."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference, ScatterChart, Series
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
FIRST_YEAR = 2000
LAST_YEAR = 2025
COUNTRIES = {
    "ZAF": "South Africa",
    "BWA": "Botswana",
    "NAM": "Namibia",
    "KEN": "Kenya",
    "BRA": "Brazil",
}
INDICATORS = {
    "SL.UEM.TOTL.ZS": ("unemployment_rate_pct", "Unemployment, total (% of labor force, modeled ILO estimate)"),
    "NY.GDP.MKTP.KD.ZG": ("real_gdp_growth_pct", "GDP growth (annual %, constant local currency)"),
    "NY.GDP.MKTP.KD": ("real_gdp_constant_lcu", "GDP (constant 2015 US$)"),
}
COUNTRY_ORDER = list(COUNTRIES)
COLORS = {
    "ZAF": "#2878B5",
    "BWA": "#35A7A0",
    "NAM": "#F2B134",
    "KEN": "#D9685D",
    "BRA": "#7656A6",
}


def fetch_indicator(indicator_id: str, start_year: int, end_year: int) -> tuple[pd.DataFrame, dict]:
    url = (
        "https://api.worldbank.org/v2/country/"
        + ";".join(COUNTRIES)
        + f"/indicator/{indicator_id}?"
        + urllib.parse.urlencode(
            {
                "format": "json",
                "date": f"{start_year}:{end_year}",
                "per_page": 1000,
            }
        )
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "World-Bank-Development-Analytics/1.0", "Accept": "application/json"},
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt == 2:
                raise RuntimeError(f"World Bank API request failed for {indicator_id}: {url}") from error
            time.sleep(2**attempt)

    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Unexpected World Bank API response for {indicator_id}: {payload!r}")
    metadata, observations = payload[0], payload[1] or []
    column, _ = INDICATORS[indicator_id]
    records = []
    for row in observations:
        code = row.get("countryiso3code")
        if code not in COUNTRIES:
            continue
        records.append(
            {
                "country_code": code,
                "country": COUNTRIES[code],
                "year": int(row["date"]),
                column: row.get("value"),
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError(f"No observations returned for World Bank indicator {indicator_id}.")
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame, {
        "indicator_id": indicator_id,
        "indicator_name": INDICATORS[indicator_id][1],
        "api_url": url,
        "api_last_updated": metadata.get("lastupdated"),
        "observations_returned": len(frame),
    }


def fetch_all(start_year: int, end_year: int) -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    sources = []
    for indicator_id in INDICATORS:
        frame, source = fetch_indicator(indicator_id, start_year, end_year)
        frames.append(frame)
        sources.append(source)

    combined = frames[0]
    for frame in frames[1:]:
        combined = combined.merge(
            frame,
            on=["country_code", "country", "year"],
            how="outer",
            validate="one_to_one",
        )
    combined = combined.sort_values(["country_code", "year"]).reset_index(drop=True)
    complete_grid = pd.MultiIndex.from_product(
        [COUNTRY_ORDER, range(start_year, end_year + 1)],
        names=["country_code", "year"],
    ).to_frame(index=False)
    combined = complete_grid.merge(
        combined, on=["country_code", "year"], how="left", validate="one_to_one"
    )
    combined["country"] = combined["country_code"].map(COUNTRIES)
    combined["real_gdp_index_2015_100"] = np.nan
    combined["unemployment_change_pp"] = np.nan
    combined["real_gdp_constant_usd_growth_pct"] = np.nan
    for _, indices in combined.groupby("country_code", sort=False).groups.items():
        group = combined.loc[indices].sort_values("year")
        base = group.loc[group["year"].eq(2015), "real_gdp_constant_lcu"].dropna()
        if not base.empty and base.iloc[0] != 0:
            combined.loc[group.index, "real_gdp_index_2015_100"] = (
                group["real_gdp_constant_lcu"] / float(base.iloc[0]) * 100
            )
        combined.loc[group.index, "unemployment_change_pp"] = group[
            "unemployment_rate_pct"
        ].diff()
        combined.loc[group.index, "real_gdp_constant_usd_growth_pct"] = (
            group["real_gdp_constant_lcu"].pct_change() * 100
        )
    return combined, sources


def summarize_countries(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code in COUNTRY_ORDER:
        group = data.loc[data["country_code"].eq(code)].sort_values("year")
        observations = group.dropna(subset=["unemployment_rate_pct", "real_gdp_growth_pct"])
        if observations.empty:
            latest = None
            latest_gdp_growth = None
            latest_year = None
        else:
            last = observations.iloc[-1]
            latest = float(last["unemployment_rate_pct"])
            latest_gdp_growth = float(last["real_gdp_growth_pct"])
            latest_year = int(last["year"])
        paired = group[["unemployment_rate_pct", "real_gdp_growth_pct"]].dropna()
        correlation = (
            float(paired["unemployment_rate_pct"].corr(paired["real_gdp_growth_pct"]))
            if len(paired) >= 3
            else np.nan
        )
        earliest = group.dropna(subset=["unemployment_rate_pct"]).head(1)
        latest_unemployment = group.dropna(subset=["unemployment_rate_pct"]).tail(1)
        if not earliest.empty and not latest_unemployment.empty:
            start = earliest.iloc[0]
            finish = latest_unemployment.iloc[0]
            years_covered = int(finish["year"] - start["year"])
            unemployment_change = (
                float(finish["unemployment_rate_pct"] - start["unemployment_rate_pct"])
                if years_covered
                else np.nan
            )
        else:
            start, finish, years_covered, unemployment_change = (None, None, None, np.nan)

        rows.append(
            {
                "country_code": code,
                "country": COUNTRIES[code],
                "latest_paired_year": latest_year,
                "latest_unemployment_pct": latest,
                "latest_real_gdp_growth_pct": latest_gdp_growth,
                "unemployment_first_year": int(start["year"]) if start is not None else None,
                "unemployment_last_year": int(finish["year"]) if finish is not None else None,
                "unemployment_change_percentage_points": unemployment_change,
                "unemployment_change_span_years": years_covered,
                "unemployment_gdp_growth_correlation": correlation,
                "paired_observation_count": len(paired),
            }
        )
    return pd.DataFrame(rows)


def correlation_matrix(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code in COUNTRY_ORDER:
        sample = data.loc[data["country_code"].eq(code)]
        for left, right, label in [
            ("unemployment_rate_pct", "real_gdp_growth_pct", "Unemployment vs real GDP growth"),
            ("unemployment_rate_pct", "real_gdp_index_2015_100", "Unemployment vs real GDP index"),
        ]:
            paired = sample[[left, right]].dropna()
            rows.append(
                {
                    "country_code": code,
                    "country": COUNTRIES[code],
                    "comparison": label,
                    "correlation": paired[left].corr(paired[right]) if len(paired) >= 3 else np.nan,
                    "paired_years": len(paired),
                }
            )
    return pd.DataFrame(rows)


def _format_sheet(sheet, table_name: str | None = None) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    if sheet.max_row:
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="17324D")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.row_dimensions[1].height = 30
    for cells in sheet.columns:
        cells = list(cells)
        letter = cells[0].column_letter
        max_width = max((len(str(cell.value or "")) for cell in cells[:150]), default=0)
        sheet.column_dimensions[letter].width = min(max(max_width + 2, 12), 36)
    if table_name and sheet.max_row > 1:
        table = Table(displayName=table_name, ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        sheet.add_table(table)


def _write_frame(workbook: Workbook, name: str, frame: pd.DataFrame, table_name: str):
    sheet = workbook.create_sheet(name)
    columns = [str(column) for column in frame.columns]
    sheet.append(columns)
    for row in frame.itertuples(index=False, name=None):
        sheet.append([None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value for value in row])
    _format_sheet(sheet, table_name)
    for column_cells in sheet.columns:
        heading = str(column_cells[0].value).lower()
        if "pct" in heading or "correlation" in heading:
            for cell in list(column_cells)[1:]:
                cell.number_format = "0.00"
        if "gdp_constant" in heading:
            for cell in list(column_cells)[1:]:
                cell.number_format = "#,##0"
    return sheet


def create_workbook(path: Path, data: pd.DataFrame, country_summary: pd.DataFrame, correlations: pd.DataFrame, sources: list[dict]) -> None:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview.sheet_view.showGridLines = False
    overview["A1"] = "WORLD BANK | UNEMPLOYMENT & GDP"
    overview["A1"].font = Font(size=18, bold=True, color="FFFFFF")
    overview["A1"].fill = PatternFill("solid", fgColor="17324D")
    overview.merge_cells("A1:F1")
    overview["A2"] = "Annual trends and country comparisons | South Africa, Botswana, Namibia, Kenya, Brazil"
    overview.merge_cells("A2:F2")
    overview["A2"].font = Font(italic=True, color="536579")
    latest = country_summary.dropna(subset=["latest_paired_year"]).set_index("country_code")
    south_africa = latest.loc["ZAF"]
    kpis = [
        ("A4", "Latest South Africa unemployment", "A5", float(south_africa["latest_unemployment_pct"]), '0.00"%"'),
        ("C4", "Latest South Africa real GDP growth", "C5", float(south_africa["latest_real_gdp_growth_pct"]), '0.00"%"'),
        ("E4", "Latest paired year", "E5", int(south_africa["latest_paired_year"]), "0"),
    ]
    for label_cell, label, value_cell, value, number_format in kpis:
        overview[label_cell] = label
        overview[label_cell].font = Font(bold=True, color="FFFFFF")
        overview[label_cell].fill = PatternFill("solid", fgColor="2878B5")
        overview[value_cell] = value
        overview[value_cell].font = Font(bold=True, size=16, color="17324D")
        overview[value_cell].number_format = number_format
    overview["A7"] = "Read this first"
    overview["A7"].font = Font(bold=True, size=12, color="17324D")
    notes = [
        "Unemployment is the World Bank's modeled ILO estimate (% of total labor force), not the national official rate.",
        "GDP growth is annual percentage growth in constant local currency. GDP index is real GDP in constant 2015 US dollars, normalized to 2015 = 100.",
        "Correlations describe annual co-movement only. They are not causal estimates, forecasts, or proof that GDP changes cause unemployment changes.",
        "Country observations may end in different years. Always compare the years shown and check missing values before drawing conclusions.",
        "World Bank API data and the workbook can be refreshed by rerunning analytics.py. The API last-updated date is documented in Methodology.",
    ]
    for row, note in enumerate(notes, start=8):
        overview.cell(row, 1, note)
        overview.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        overview.cell(row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        overview.row_dimensions[row].height = 32

    annual_sheet = _write_frame(workbook, "Annual Data", data, "AnnualData")
    _write_frame(workbook, "Country Summary", country_summary, "CountrySummary")
    _write_frame(workbook, "Correlations", correlations, "Correlations")
    source_frame = pd.DataFrame(sources)
    _write_frame(workbook, "Methodology", source_frame, "SourceMetadata")

    chart_data = workbook.create_sheet("Chart Data")
    chart_data.append(["Year", *[COUNTRIES[code] for code in COUNTRY_ORDER]])
    unemployment_wide = data.pivot(index="year", columns="country_code", values="unemployment_rate_pct")
    for year in range(int(data["year"].min()), int(data["year"].max()) + 1):
        chart_data.append(
            [
                year,
                *[
                    None if pd.isna(unemployment_wide.loc[year, code]) else float(unemployment_wide.loc[year, code])
                    for code in COUNTRY_ORDER
                ],
            ]
        )
    _format_sheet(chart_data)
    chart_data.sheet_state = "hidden"

    # Add worksheet formulas so analysts can inspect/recalculate the derived measures in Excel.
    annual_sheet.cell(1, 10, "Excel unemployment change (pp)")
    annual_sheet.cell(1, 11, "Excel constant-USD GDP growth (%)")
    for cell in (annual_sheet.cell(1, 10), annual_sheet.cell(1, 11)):
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="17324D")
    for row in range(2, annual_sheet.max_row + 1):
        if row > 2 and annual_sheet.cell(row, 1).value == annual_sheet.cell(row - 1, 1).value:
            annual_sheet.cell(row, 10, f'=IFERROR(D{row}-D{row - 1},"")')
            annual_sheet.cell(row, 11, f'=IFERROR(G{row}/G{row - 1}*100-100,"")')
        annual_sheet.cell(row, 10).number_format = "0.00"
        annual_sheet.cell(row, 11).number_format = "0.00"
    annual_sheet.tables["AnnualData"].ref = f"A1:K{annual_sheet.max_row}"
    correlations_sheet = workbook["Correlations"]
    if correlations_sheet.max_row > 1:
        correlations_sheet.conditional_formatting.add(
            f"D2:D{correlations_sheet.max_row}",
            ColorScaleRule(
                start_type="num",
                start_value=-1,
                start_color="F8696B",
                mid_type="num",
                mid_value=0,
                mid_color="FFEB84",
                end_type="num",
                end_value=1,
                end_color="63BE7B",
            ),
        )

    scatter = ScatterChart()
    scatter.title = "South Africa: unemployment vs real GDP growth"
    scatter.x_axis.title = "Real GDP growth (%)"
    scatter.y_axis.title = "Unemployment rate (%)"
    scatter.style = 13
    sa_rows = [
        row
        for row in range(2, annual_sheet.max_row + 1)
        if annual_sheet.cell(row, 1).value == "ZAF"
    ]
    if sa_rows:
        scatter.series.append(
            Series(
                Reference(annual_sheet, min_col=4, min_row=sa_rows[0], max_row=sa_rows[-1]),
                Reference(annual_sheet, min_col=5, min_row=sa_rows[0], max_row=sa_rows[-1]),
                title="South Africa",
            )
        )
    overview.add_chart(scatter, "A15")

    line = LineChart()
    line.title = "Unemployment rate by country"
    line.y_axis.title = "Unemployment (%)"
    line.x_axis.title = "Year"
    line.add_data(
        Reference(chart_data, min_col=2, max_col=chart_data.max_column, min_row=1, max_row=chart_data.max_row),
        titles_from_data=True,
    )
    line.set_categories(Reference(chart_data, min_col=1, min_row=2, max_row=chart_data.max_row))
    line.height = 9
    line.width = 16
    overview.add_chart(line, "G4")
    overview.column_dimensions["A"].width = 38
    overview.column_dimensions["B"].width = 18
    overview.column_dimensions["C"].width = 34
    overview.column_dimensions["D"].width = 18
    overview.column_dimensions["E"].width = 24
    overview.column_dimensions["F"].width = 18
    for sheet in workbook.worksheets:
        sheet.sheet_view.zoomScale = 90
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.save(path)


def create_charts(data: pd.DataFrame, correlations: pd.DataFrame, chart_dir: Path) -> None:
    chart_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(11, 6))
    for code in COUNTRY_ORDER:
        group = data.loc[data["country_code"].eq(code)].dropna(subset=["unemployment_rate_pct"])
        sns.lineplot(
            data=group,
            x="year",
            y="unemployment_rate_pct",
            label=COUNTRIES[code],
            color=COLORS[code],
            marker="o",
            ax=ax,
        )
    ax.set(title="Modeled unemployment rate by country", xlabel="Year", ylabel="% of labor force")
    fig.tight_layout()
    fig.savefig(chart_dir / "unemployment_trends.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    for code in COUNTRY_ORDER:
        group = data.loc[data["country_code"].eq(code)].dropna(subset=["real_gdp_index_2015_100"])
        sns.lineplot(
            data=group,
            x="year",
            y="real_gdp_index_2015_100",
            label=COUNTRIES[code],
            color=COLORS[code],
            ax=ax,
        )
    ax.axhline(100, linestyle="--", linewidth=1, color="#666666")
    ax.set(title="Real GDP trend (2015 = 100)", xlabel="Year", ylabel="GDP index")
    fig.tight_layout()
    fig.savefig(chart_dir / "real_gdp_index.png", dpi=180)
    plt.close(fig)

    sa = data.loc[data["country_code"].eq("ZAF")].dropna(
        subset=["unemployment_rate_pct", "real_gdp_growth_pct"]
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.regplot(
        data=sa,
        x="real_gdp_growth_pct",
        y="unemployment_rate_pct",
        ci=None,
        scatter_kws={"s": 48, "color": COLORS["ZAF"]},
        line_kws={"color": COLORS["BRA"], "linewidth": 2},
        ax=ax,
    )
    ax.set(
        title="South Africa: annual unemployment and real GDP growth",
        xlabel="Real GDP growth (%)",
        ylabel="Unemployment (%)",
    )
    fig.tight_layout()
    fig.savefig(chart_dir / "south_africa_unemployment_vs_gdp.png", dpi=180)
    plt.close(fig)

    pivot = correlations.pivot(index="country", columns="comparison", values="correlation")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="vlag", center=0, vmin=-1, vmax=1, ax=ax)
    ax.set(title="Descriptive annual correlations (not causal)", xlabel="", ylabel="")
    fig.tight_layout()
    fig.savefig(chart_dir / "correlation_heatmap.png", dpi=180)
    plt.close(fig)


def write_summary(path: Path, data: pd.DataFrame, summary: pd.DataFrame, correlations: pd.DataFrame, sources: list[dict]) -> None:
    def markdown_table(frame: pd.DataFrame) -> str:
        headers = [str(column) for column in frame.columns]
        rows = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
        return "\n".join(
            ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
            + ["| " + " | ".join(row) + " |" for row in rows]
        )

    latest = summary.dropna(subset=["latest_paired_year"]).copy()
    latest_rows = latest[
        ["country", "latest_paired_year", "latest_unemployment_pct", "latest_real_gdp_growth_pct"]
    ]
    latest_rows["latest_unemployment_pct"] = latest_rows["latest_unemployment_pct"].map(
        lambda value: f"{value:.2f}"
    )
    latest_rows["latest_real_gdp_growth_pct"] = latest_rows["latest_real_gdp_growth_pct"].map(
        lambda value: f"{value:.2f}"
    )
    latest_table = markdown_table(latest_rows)
    sa_corr = correlations.loc[
        correlations["country_code"].eq("ZAF")
        & correlations["comparison"].eq("Unemployment vs real GDP growth")
    ].iloc[0]
    sources_text = "\n".join(
        f"- `{source['indicator_id']}` — {source['indicator_name']}; API last updated: {source['api_last_updated']}."
        for source in sources
    )
    text = f"""# World Bank Unemployment & GDP — Analysis Summary

## Scope

Annual observations from {int(data['year'].min())}–{int(data['year'].max())} for South Africa, Botswana, Namibia, Kenya, and Brazil. The peer set pairs South Africa's two SADC neighbours with Kenya as a sub-Saharan African comparator and Brazil as a large emerging-economy comparison. Comparisons are descriptive, not a country ranking or causal evaluation.

## Latest overlapping observations

{latest_table}

GDP growth is the World Bank annual growth rate in constant local currency. The separate real-GDP trend is expressed in constant 2015 US dollars and indexed within each country to 2015 = 100.

## South Africa: unemployment and GDP growth

Across {int(sa_corr['paired_years'])} annual paired observations, the Pearson correlation between the modeled unemployment rate and real GDP growth is **{sa_corr['correlation']:.2f}**. This describes co-movement in the selected years; it does not establish that GDP growth causes unemployment changes. Results can be influenced by business-cycle lags, labor-force participation, economic structure, shocks, revisions, and the short annual time series.

## Source indicators

{sources_text}

Source: [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386). Indicator pages: [unemployment](https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS), [GDP growth](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG), and [real GDP](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD). World Bank open data is generally offered under [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by); cite the World Bank and the original source noted on each indicator page.

## Data caveats

- Unemployment is the **modeled ILO estimate**, not a national official estimate or a direct household-survey extract. It is an estimate and may be revised.
- Country-year series do not necessarily have identical availability. Missing values are retained as missing; each chart and correlation uses available paired observations.
- GDP growth in constant local currency is used for annual growth rates; real GDP in constant 2015 US dollars is used only as a normalized comparison series. Current-US-dollar GDP would mix real output changes with exchange-rate and price changes.
- GDP and unemployment may have timing lags and structural differences. Correlation is descriptive only; no causal claims, significance testing, or prediction is made.
- The API data are retrieved when the script runs; the accompanying source CSV and metadata record the values used in this published analysis.
"""
    path.write_text(text, encoding="utf-8")


def run_analysis(start_year: int = FIRST_YEAR, end_year: int = LAST_YEAR) -> pd.DataFrame:
    if start_year < 1960 or end_year < start_year:
        raise ValueError(f"Invalid year range {start_year}:{end_year}; choose start >= 1960 and end >= start.")
    data, sources = fetch_all(start_year, end_year)
    summary = summarize_countries(data)
    correlations = correlation_matrix(data)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT_DIR / "world_bank_annual_data.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / "country_summary.csv", index=False, encoding="utf-8-sig")
    correlations.to_csv(OUTPUT_DIR / "correlations.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "retrieved_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "start_year": start_year,
        "end_year": end_year,
        "countries": COUNTRIES,
        "indicators": sources,
        "api_documentation": "https://datahelpdesk.worldbank.org/knowledgebase/articles/889386",
        "license_reference": "https://datacatalog.worldbank.org/public-licenses#cc-by",
        "data_rows": len(data),
    }
    (OUTPUT_DIR / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    create_charts(data, correlations, CHART_DIR)
    create_workbook(OUTPUT_DIR / "world_bank_unemployment_gdp_analysis.xlsx", data, summary, correlations, sources)
    write_summary(OUTPUT_DIR / "ANALYSIS_SUMMARY.md", data, summary, correlations, sources)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=FIRST_YEAR)
    parser.add_argument("--end-year", type=int, default=LAST_YEAR)
    args = parser.parse_args()
    data = run_analysis(args.start_year, args.end_year)
    print(
        f"Analysis complete: {len(data)} country-year rows, "
        f"{int(data['unemployment_rate_pct'].notna().sum())} unemployment observations, "
        f"{int(data['real_gdp_growth_pct'].notna().sum())} GDP-growth observations."
    )
    print(f"Outputs: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
