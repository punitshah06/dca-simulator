# Investment Toolkit

A Streamlit app with three tools for retail investors:

1. **DCA Simulator** — Compare dollar-cost averaging strategies (daily vs each weekday) using historical stock price data
2. **Stock Risk Scorer** — Score and rank individual stocks on a 0-100 risk scale using KPIs from Google Finance
3. **ETF Risk Scorer** — Score and rank ETFs using price/volume KPIs (since PE, EPS, Beta are unavailable for ETFs)

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## DCA Simulator

Upload a CSV with `Date` and `Close` columns (e.g. from Yahoo Finance). The app simulates investing a fixed weekly budget across 6 strategies:

- **Daily** — invest 1/5 of the weekly budget each trading day
- **Every Monday / Tuesday / ... / Friday** — invest the full weekly budget on that weekday

For each strategy it calculates total invested, final portfolio value, gain ($/%),  max drawdown, and number of buys. Results are shown in a comparison table and charts.

### CSV format

```
Date,Close
03/01/2023 16:00:00,125.07
04/01/2023 16:00:00,126.36
```

Supports both `dd/mm/yyyy` and `mm/dd/yyyy` date formats (selectable in sidebar).

## Stock Risk Scorer

Upload a CSV with stock KPIs — all sourced directly from `=GOOGLEFINANCE()` in Google Sheets.

### Google Sheets setup

| | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| **1** | Company | PE | EPS | Beta | MarketCap | High52 | Low52 | Price |
| **2** | AAPL | `=GOOGLEFINANCE(A2,"pe")` | `=GOOGLEFINANCE(A2,"eps")` | `=GOOGLEFINANCE(A2,"beta")` | `=GOOGLEFINANCE(A2,"marketcap")` | `=GOOGLEFINANCE(A2,"high52")` | `=GOOGLEFINANCE(A2,"low52")` | `=GOOGLEFINANCE(A2,"price")` |

Copy row 2 down for each ticker, then File > Download > CSV.

### Scoring (5 dimensions, 20 pts each, 100 total)

| Dimension | KPI | Best score |
|-----------|-----|------------|
| Valuation | P/E ratio | 10-20x P/E |
| Profitability | EPS | EPS > $6 |
| Volatility | Beta | Beta < 0.5 |
| Size / Stability | Market Cap | > $200B |
| Price Strength | Position in 52-week range | Near 52-week high |

**Risk ratings:** 80-100 Low Risk, 60-79 Moderate, 40-59 Elevated, 0-39 High Risk.

Results are sorted from lowest to highest risk.

## ETF Risk Scorer

ETFs return `#N/A` for PE, EPS, Beta, and MarketCap in Google Finance. This scorer uses only price and volume data that GOOGLEFINANCE actually provides for ETFs.

### Google Sheets setup

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| **1** | ETF | Price | High52 | Low52 | VolumeAvg | ChangePct |
| **2** | SPY | `=GOOGLEFINANCE(A2,"price")` | `=GOOGLEFINANCE(A2,"high52")` | `=GOOGLEFINANCE(A2,"low52")` | `=GOOGLEFINANCE(A2,"volumeavg")` | `=GOOGLEFINANCE(A2,"changepct")` |

Copy row 2 down for each ETF, then File > Download > CSV.

### Scoring (5 dimensions, 20 pts each, 100 total)

| Dimension | KPI | Best score |
|-----------|-----|------------|
| Price Strength | Position in 52-week range | Near 52-week high |
| Range Tightness | 52-week high-low spread % | < 15% spread |
| Liquidity | Average daily volume | > 10M shares |
| Daily Volatility | Absolute daily % change | < 0.5% |
| Price Level | Share price | > $200 |

**Risk ratings:** 80-100 Low Risk, 60-79 Moderate, 40-59 Elevated, 0-39 High Risk.

Results are sorted from lowest to highest risk.

## Tech Stack

- Python 3
- Streamlit
- Pandas
