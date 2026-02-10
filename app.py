import streamlit as st
import pandas as pd
from datetime import timedelta

st.set_page_config(page_title="Investment Toolkit", layout="wide")

# ── Page selector ─────────────────────────────────────────────────────────────
page = st.sidebar.radio("Navigate", ["DCA Simulator", "Financial Risk Scorer"])

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — DCA SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════
def simulate(df: pd.DataFrame, amount: float, buy_mask: pd.Series) -> dict:
    """Run a DCA simulation over *df* buying on rows where *buy_mask* is True."""
    total_shares = 0.0
    total_invested = 0.0
    portfolio_values = []
    invested_over_time = []

    for idx, row in df.iterrows():
        if buy_mask.loc[idx]:
            shares = amount / row["Close"]
            total_shares += shares
            total_invested += amount

        current_value = total_shares * row["Close"]
        portfolio_values.append(current_value)
        invested_over_time.append(total_invested)

    portfolio_series = pd.Series(portfolio_values, index=df["Date"].values)
    invested_series = pd.Series(invested_over_time, index=df["Date"].values)

    final_value = portfolio_values[-1] if portfolio_values else 0
    gain = final_value - total_invested
    gain_pct = (gain / total_invested * 100) if total_invested else 0

    running_max = pd.Series(portfolio_values).cummax()
    drawdowns = (pd.Series(portfolio_values) - running_max) / running_max
    max_drawdown = drawdowns.min() * 100

    return {
        "Total Invested": round(total_invested, 2),
        "Final Value": round(final_value, 2),
        "Gain ($)": round(gain, 2),
        "Gain (%)": round(gain_pct, 2),
        "Max Drawdown (%)": round(max_drawdown, 2),
        "Buy Count": int(buy_mask.sum()),
        "_portfolio": portfolio_series,
        "_invested": invested_series,
    }


def run_dca_simulator():
    st.title("Dollar-Cost Averaging Investment Simulator")

    # ── Sidebar controls ──────────────────────────────────────────────────────
    st.sidebar.header("DCA Settings")
    uploaded_file = st.sidebar.file_uploader(
        "Upload stock CSV (needs Date & Close columns)", type=["csv"], key="dca_csv"
    )
    trailing_days = st.sidebar.slider("Trailing days", 30, 730, 90)
    invest_amount = st.sidebar.number_input(
        "Weekly budget ($)", min_value=1, max_value=100000, value=100, step=10,
        help="Weekly & specific-day strategies invest this full amount. Daily strategy invests 1/5 of this per day.",
    )
    date_format = st.sidebar.selectbox(
        "Date format in CSV", ["dd/mm/yyyy", "mm/dd/yyyy"]
    )

    if uploaded_file is None:
        st.info(
            "Upload a CSV file with at least **Date** and **Close** columns. "
            "You can download historical data from Yahoo Finance, Google Finance, etc."
        )
        st.stop()

    # ── Load & prepare data ───────────────────────────────────────────────────
    raw = pd.read_csv(uploaded_file)
    raw.columns = [c.strip() for c in raw.columns]
    col_map = {c.lower(): c for c in raw.columns}
    if "date" not in col_map or "close" not in col_map:
        st.error("CSV must contain **Date** and **Close** columns.")
        st.stop()

    df = raw[[col_map["date"], col_map["close"]]].copy()
    df.columns = ["Date", "Close"]
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=(date_format == "dd/mm/yyyy"))
    df = df.dropna(subset=["Close"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])
    df = df.sort_values("Date").reset_index(drop=True)

    cutoff = df["Date"].max() - timedelta(days=trailing_days)
    df = df[df["Date"] >= cutoff].reset_index(drop=True)

    if len(df) < 2:
        st.warning("Not enough data after filtering. Try increasing trailing days.")
        st.stop()

    st.subheader(f"Data: {df['Date'].min().date()} to {df['Date'].max().date()} ({len(df)} trading days)")

    # ── Build buy masks ───────────────────────────────────────────────────────
    daily_mask = pd.Series(True, index=df.index)
    strategies = {
        "Daily ($/5 per day)": (daily_mask, invest_amount / 5),
    }
    for dow, day_name in enumerate(WEEKDAYS):
        day_mask = df["Date"].dt.dayofweek == dow
        strategies[f"Every {day_name}"] = (day_mask, invest_amount)

    # ── Run simulations ───────────────────────────────────────────────────────
    results = {}
    for name, (mask, amount) in strategies.items():
        if mask.sum() == 0:
            st.warning(f"No buy days for strategy '{name}' in this period.")
            continue
        results[name] = simulate(df, amount, mask)

    if not results:
        st.error("No strategies produced results. Check your data and settings.")
        st.stop()

    # ── Comparison table ──────────────────────────────────────────────────────
    st.subheader("Strategy Comparison")
    display_keys = ["Total Invested", "Final Value", "Gain ($)", "Gain (%)", "Max Drawdown (%)", "Buy Count"]
    table_data = {name: {k: v for k, v in res.items() if k in display_keys} for name, res in results.items()}
    comparison_df = pd.DataFrame(table_data).T
    comparison_df.index.name = "Strategy"

    best_strategy = comparison_df["Gain ($)"].idxmax()
    st.dataframe(
        comparison_df.style.highlight_max(subset=["Gain ($)", "Gain (%)"], color="#c6efce")
        .highlight_min(subset=["Max Drawdown (%)"], color="#ffc7ce")
        .format({
            "Total Invested": "${:,.2f}",
            "Final Value": "${:,.2f}",
            "Gain ($)": "${:,.2f}",
            "Gain (%)": "{:.2f}%",
            "Max Drawdown (%)": "{:.2f}%",
        }),
        use_container_width=True,
    )
    st.success(
        f"Best strategy by total gain: **{best_strategy}** with "
        f"**${results[best_strategy]['Gain ($)']:,.2f}** gain "
        f"({results[best_strategy]['Gain (%)']:.2f}%)"
    )

    # ── Charts ────────────────────────────────────────────────────────────────
    st.subheader("Portfolio Value Over Time")
    chart_df = pd.DataFrame({name: res["_portfolio"] for name, res in results.items()})
    st.line_chart(chart_df)

    st.subheader("Total Invested vs Final Value")
    bar_data = pd.DataFrame({
        "Total Invested": {name: res["Total Invested"] for name, res in results.items()},
        "Final Value": {name: res["Final Value"] for name, res in results.items()},
    })
    st.bar_chart(bar_data)

    with st.expander("Show raw price data"):
        price_chart = df.set_index("Date")[["Close"]]
        st.line_chart(price_chart)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — STOCK RISK SCORER  (Google Finance KPIs only)
# ══════════════════════════════════════════════════════════════════════════════
#
#  All inputs come from =GOOGLEFINANCE() in Google Sheets:
#    pe, eps, beta, marketcap, high52, low52, price, volumeavg
#
#  5 scoring dimensions (20 pts each → 100 total):
#    1. Valuation    — P/E ratio
#    2. Profitability — EPS
#    3. Volatility   — Beta
#    4. Size/Stability — Market Cap
#    5. Price Strength — how close price is to 52-week high vs low
# ──────────────────────────────────────────────────────────────────────────────

def score_valuation(pe: float) -> int:
    """Score P/E ratio (0-20). Moderate P/E is best; negative or extreme is worst."""
    if pe <= 0:
        return 0          # negative earnings
    elif pe < 10:
        return 15         # possibly value trap or cyclical
    elif pe <= 20:
        return 20         # healthy valuation
    elif pe <= 30:
        return 15         # growth premium
    elif pe <= 50:
        return 10         # expensive
    else:
        return 5          # speculative


def score_profitability(eps: float) -> int:
    """Score EPS (0-20). Higher positive EPS is better."""
    if eps <= 0:
        return 0          # losing money
    elif eps < 1:
        return 5
    elif eps < 3:
        return 10
    elif eps < 6:
        return 15
    else:
        return 20         # strong earnings


def score_volatility(beta: float) -> int:
    """Score Beta (0-20). Lower beta = lower risk."""
    if beta < 0:
        return 5          # inverse — unusual
    elif beta <= 0.5:
        return 20         # very defensive
    elif beta <= 0.8:
        return 18
    elif beta <= 1.0:
        return 15         # market-like
    elif beta <= 1.3:
        return 12
    elif beta <= 1.6:
        return 8
    else:
        return 4          # highly volatile


def score_size(marketcap: float) -> int:
    """Score Market Cap in USD (0-20). Larger = more stable."""
    if marketcap >= 200e9:
        return 20         # mega-cap
    elif marketcap >= 50e9:
        return 18         # large-cap
    elif marketcap >= 10e9:
        return 15         # mid-cap
    elif marketcap >= 2e9:
        return 10         # small-cap
    elif marketcap >= 300e6:
        return 5          # micro-cap
    else:
        return 2          # nano-cap


def score_price_strength(price: float, high52: float, low52: float) -> int:
    """Score where current price sits in 52-week range (0-20).
    Closer to high = stronger momentum / less downside risk."""
    if high52 == low52:
        return 10
    pct = (price - low52) / (high52 - low52)  # 0 = at low, 1 = at high
    if pct >= 0.8:
        return 20         # near 52-week high — strong
    elif pct >= 0.6:
        return 16
    elif pct >= 0.4:
        return 12
    elif pct >= 0.2:
        return 8
    else:
        return 4          # near 52-week low — weak


# ── Orchestrator ──────────────────────────────────────────────────────────────

REQUIRED_COLS = ["PE", "EPS", "Beta", "MarketCap", "High52", "Low52", "Price"]


def compute_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute risk scores for each row (company)."""
    records = []
    for _, row in df.iterrows():
        val = score_valuation(row["PE"])
        prof = score_profitability(row["EPS"])
        vol = score_volatility(row["Beta"])
        sz = score_size(row["MarketCap"])
        ps = score_price_strength(row["Price"], row["High52"], row["Low52"])

        composite = val + prof + vol + sz + ps

        if composite >= 80:
            risk_label = "Low Risk"
        elif composite >= 60:
            risk_label = "Moderate Risk"
        elif composite >= 40:
            risk_label = "Elevated Risk"
        else:
            risk_label = "High Risk"

        identifier = row.get("Company", row.get("Ticker", "Unknown"))
        records.append({
            "Company": identifier,
            "Valuation (0-20)": val,
            "Profitability (0-20)": prof,
            "Volatility (0-20)": vol,
            "Size (0-20)": sz,
            "Price Strength (0-20)": ps,
            "Composite (0-100)": composite,
            "Risk Rating": risk_label,
        })
    return pd.DataFrame(records)


# ── Risk Scorer UI ────────────────────────────────────────────────────────────

def run_risk_scorer():
    st.title("Stock Risk Scorer")

    st.sidebar.header("Risk Scorer Settings")
    uploaded = st.sidebar.file_uploader(
        "Upload stock KPIs CSV", type=["csv"], key="risk_csv"
    )

    if uploaded is None:
        st.info(
            "Upload a CSV with one row per stock. **All columns come directly "
            "from** `=GOOGLEFINANCE()` **in Google Sheets** — no manual data entry needed."
        )

        st.subheader("Required CSV Columns")
        st.markdown("""
| Column | Google Sheets Formula | Example |
|--------|----------------------|---------|
| `Company` | *(type the ticker)* | AAPL |
| `PE` | `=GOOGLEFINANCE("AAPL","pe")` | 28.5 |
| `EPS` | `=GOOGLEFINANCE("AAPL","eps")` | 6.42 |
| `Beta` | `=GOOGLEFINANCE("AAPL","beta")` | 1.24 |
| `MarketCap` | `=GOOGLEFINANCE("AAPL","marketcap")` | 2.8E+12 |
| `High52` | `=GOOGLEFINANCE("AAPL","high52")` | 199.62 |
| `Low52` | `=GOOGLEFINANCE("AAPL","low52")` | 164.08 |
| `Price` | `=GOOGLEFINANCE("AAPL","price")` | 189.84 |
        """)

        st.markdown("---")
        st.subheader("Google Sheets Setup")
        st.markdown("""
**Step 1** — Create a sheet with this layout:

| | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| **1** | Company | PE | EPS | Beta | MarketCap | High52 | Low52 | Price |
| **2** | AAPL | *formula* | *formula* | *formula* | *formula* | *formula* | *formula* | *formula* |

**Step 2** — In row 2, enter formulas (replace `A2` with the ticker cell):

```
B2: =GOOGLEFINANCE(A2, "pe")
C2: =GOOGLEFINANCE(A2, "eps")
D2: =GOOGLEFINANCE(A2, "beta")
E2: =GOOGLEFINANCE(A2, "marketcap")
F2: =GOOGLEFINANCE(A2, "high52")
G2: =GOOGLEFINANCE(A2, "low52")
H2: =GOOGLEFINANCE(A2, "price")
```

**Step 3** — Copy row 2 down for each ticker. Then **File → Download → CSV**.
        """)

        # Downloadable sample CSV
        sample = pd.DataFrame({
            "Company": ["AAPL", "TSLA", "MSFT", "F", "NVDA"],
            "PE": [28.5, 62.3, 34.1, 11.2, 55.8],
            "EPS": [6.42, 3.08, 11.53, 1.52, 1.71],
            "Beta": [1.24, 2.05, 0.89, 1.47, 1.68],
            "MarketCap": [2.8e12, 6.2e11, 2.9e12, 4.8e10, 1.8e12],
            "High52": [199.62, 299.29, 430.82, 14.85, 152.89],
            "Low52": [164.08, 138.80, 309.45, 9.49, 47.32],
            "Price": [189.84, 248.42, 415.60, 11.21, 135.58],
        })
        st.download_button(
            "Download sample CSV",
            sample.to_csv(index=False),
            "sample_stock_kpis.csv",
            "text/csv",
        )

        st.markdown("---")
        st.subheader("Scoring Methodology")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**Valuation (0-20 pts)** — P/E Ratio
| Range | Score |
|-------|-------|
| ≤ 0 (losses) | 0 |
| 1–10 | 15 |
| 10–20 | 20 |
| 20–30 | 15 |
| 30–50 | 10 |
| > 50 | 5 |

**Volatility (0-20 pts)** — Beta
| Range | Score |
|-------|-------|
| ≤ 0.5 | 20 |
| 0.5–0.8 | 18 |
| 0.8–1.0 | 15 |
| 1.0–1.3 | 12 |
| 1.3–1.6 | 8 |
| > 1.6 | 4 |
            """)
        with col2:
            st.markdown("""
**Profitability (0-20 pts)** — EPS
| Range | Score |
|-------|-------|
| ≤ 0 | 0 |
| 0–1 | 5 |
| 1–3 | 10 |
| 3–6 | 15 |
| > 6 | 20 |

**Size / Stability (0-20 pts)** — Market Cap
| Range | Score |
|-------|-------|
| ≥ $200B | 20 |
| $50–200B | 18 |
| $10–50B | 15 |
| $2–10B | 10 |
| $300M–2B | 5 |
| < $300M | 2 |
            """)
        st.markdown("""
**Price Strength (0-20 pts)** — Position in 52-week range

| % of Range | Score |
|------------|-------|
| 80–100% (near high) | 20 |
| 60–80% | 16 |
| 40–60% | 12 |
| 20–40% | 8 |
| 0–20% (near low) | 4 |

---
**Composite Risk Score = Sum of 5 scores (0–100)**

| Score | Rating |
|-------|--------|
| 80–100 | Low Risk |
| 60–79 | Moderate Risk |
| 40–59 | Elevated Risk |
| 0–39 | High Risk |
        """)
        st.stop()

    # ── Load & validate CSV ───────────────────────────────────────────────────
    raw = pd.read_csv(uploaded)
    raw.columns = [c.strip() for c in raw.columns]

    has_id = "Company" in raw.columns or "Ticker" in raw.columns
    if not has_id:
        st.error("CSV must have a **Company** or **Ticker** column.")
        st.stop()

    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    if missing:
        st.error(f"Missing columns: **{', '.join(missing)}**")
        st.stop()

    for col in REQUIRED_COLS:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw = raw.dropna(subset=REQUIRED_COLS)

    if len(raw) == 0:
        st.warning("No valid rows after cleaning. Check your data.")
        st.stop()

    # ── Compute scores ────────────────────────────────────────────────────────
    results_df = compute_risk_scores(raw)
    results_df = results_df.sort_values("Composite (0-100)", ascending=False).reset_index(drop=True)
    st.subheader(f"Risk Assessment — {len(results_df)} companies (sorted lowest → highest risk)")

    # ── 1. Breakdown table with color-coded risk ──────────────────────────────
    def color_risk(val):
        colors = {
            "Low Risk": "background-color: #c6efce; color: #006100",
            "Moderate Risk": "background-color: #ffeb9c; color: #9c6500",
            "Elevated Risk": "background-color: #ffc7ce; color: #9c0006",
            "High Risk": "background-color: #ff9999; color: #800000",
        }
        return colors.get(val, "")

    st.dataframe(
        results_df.style.applymap(color_risk, subset=["Risk Rating"]),
        use_container_width=True,
        hide_index=True,
    )

    # Best / worst summary
    best = results_df.loc[results_df["Composite (0-100)"].idxmax()]
    worst = results_df.loc[results_df["Composite (0-100)"].idxmin()]
    col1, col2 = st.columns(2)
    with col1:
        st.success(f"Lowest risk: **{best['Company']}** — {best['Composite (0-100)']}/100 ({best['Risk Rating']})")
    with col2:
        st.error(f"Highest risk: **{worst['Company']}** — {worst['Composite (0-100)']}/100 ({worst['Risk Rating']})")

    # ── 2. Composite score bar chart ──────────────────────────────────────────
    st.subheader("Composite Risk Scores")
    chart_data = results_df.set_index("Company")[["Composite (0-100)"]]
    st.bar_chart(chart_data)

    # ── 3. Score composition stacked bar ──────────────────────────────────────
    st.subheader("Score Breakdown by Company")
    sub_cols = ["Valuation (0-20)", "Profitability (0-20)", "Volatility (0-20)",
                "Size (0-20)", "Price Strength (0-20)"]
    composition_df = results_df.set_index("Company")[sub_cols]
    st.bar_chart(composition_df)

    # ── 4. Per-company detail expanders ───────────────────────────────────────
    st.subheader("Detailed Breakdown")
    for _, row in results_df.iterrows():
        with st.expander(f"{row['Company']} — {row['Risk Rating']} ({row['Composite (0-100)']}/100)"):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Valuation", f"{row['Valuation (0-20)']}/20")
            with c2:
                st.metric("Profitability", f"{row['Profitability (0-20)']}/20")
            with c3:
                st.metric("Volatility", f"{row['Volatility (0-20)']}/20")
            with c4:
                st.metric("Size", f"{row['Size (0-20)']}/20")
            with c5:
                st.metric("Price Strength", f"{row['Price Strength (0-20)']}/20")


# ══════════════════════════════════════════════════════════════════════════════
#  DISPATCH
# ══════════════════════════════════════════════════════════════════════════════
if page == "DCA Simulator":
    run_dca_simulator()
elif page == "Financial Risk Scorer":
    run_risk_scorer()
