import streamlit as st
import pandas as pd
from datetime import timedelta

st.set_page_config(page_title="DCA Investment Simulator", layout="wide")
st.title("Dollar-Cost Averaging Investment Simulator")

# ── Sidebar controls ──────────────────────────────────────────────────────────
st.sidebar.header("Settings")
uploaded_file = st.sidebar.file_uploader(
    "Upload stock CSV (needs Date & Close columns)", type=["csv"]
)
trailing_days = st.sidebar.slider("Trailing days", 30, 730, 90)
invest_amount = st.sidebar.number_input(
    "Weekly budget ($)", min_value=1, max_value=100000, value=100, step=10,
    help="Weekly & specific-day strategies invest this full amount. Daily strategy invests 1/5 of this per day."
)
date_format = st.sidebar.selectbox(
    "Date format in CSV",
    ["dd/mm/yyyy", "mm/dd/yyyy"],
)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ── Simulation engine ─────────────────────────────────────────────────────────
def simulate(df: pd.DataFrame, amount: float, buy_mask: pd.Series) -> dict:
    """Run a DCA simulation over *df* buying on rows where *buy_mask* is True.

    Returns a dict with summary stats and a portfolio-value series for charting.
    """
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

    # Max drawdown from peak portfolio value
    running_max = pd.Series(portfolio_values).cummax()
    drawdowns = (pd.Series(portfolio_values) - running_max) / running_max
    max_drawdown = drawdowns.min() * 100  # as negative %

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


# ── Main ──────────────────────────────────────────────────────────────────────
if uploaded_file is None:
    st.info(
        "Upload a CSV file with at least **Date** and **Close** columns. "
        "You can download historical data from Yahoo Finance, Google Finance, etc."
    )
    st.stop()

# Load & prepare data
raw = pd.read_csv(uploaded_file)

# Flexible column matching (case-insensitive)
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

# Filter to trailing X days
cutoff = df["Date"].max() - timedelta(days=trailing_days)
df = df[df["Date"] >= cutoff].reset_index(drop=True)

if len(df) < 2:
    st.warning("Not enough data after filtering. Try increasing trailing days.")
    st.stop()

st.subheader(f"Data: {df['Date'].min().date()} to {df['Date'].max().date()} ({len(df)} trading days)")

# ── Build buy masks ───────────────────────────────────────────────────────────
# 1. Daily
daily_mask = pd.Series(True, index=df.index)

# 2. Every weekday (Mon–Fri), each investing full weekly amount on that one day
strategies = {
    "Daily ($/5 per day)": (daily_mask, invest_amount / 5),
}
for dow, day_name in enumerate(WEEKDAYS):
    day_mask = df["Date"].dt.dayofweek == dow
    strategies[f"Every {day_name}"] = (day_mask, invest_amount)

# ── Run simulations ───────────────────────────────────────────────────────────
results = {}
for name, (mask, amount) in strategies.items():
    if mask.sum() == 0:
        st.warning(f"No buy days for strategy '{name}' in this period.")
        continue
    results[name] = simulate(df, amount, mask)

if not results:
    st.error("No strategies produced results. Check your data and settings.")
    st.stop()

# ── Comparison table ──────────────────────────────────────────────────────────
st.subheader("Strategy Comparison")

display_keys = ["Total Invested", "Final Value", "Gain ($)", "Gain (%)", "Max Drawdown (%)", "Buy Count"]
table_data = {name: {k: v for k, v in res.items() if k in display_keys} for name, res in results.items()}
comparison_df = pd.DataFrame(table_data).T
comparison_df.index.name = "Strategy"

# Highlight the best gain row
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

st.success(f"Best strategy by total gain: **{best_strategy}** with **${results[best_strategy]['Gain ($)']:,.2f}** gain ({results[best_strategy]['Gain (%)']:.2f}%)")

# ── Charts ────────────────────────────────────────────────────────────────────
st.subheader("Portfolio Value Over Time")

chart_df = pd.DataFrame({name: res["_portfolio"] for name, res in results.items()})
st.line_chart(chart_df)

st.subheader("Total Invested vs Final Value")
bar_data = pd.DataFrame(
    {
        "Total Invested": {name: res["Total Invested"] for name, res in results.items()},
        "Final Value": {name: res["Final Value"] for name, res in results.items()},
    }
)
st.bar_chart(bar_data)

# ── Raw price chart ───────────────────────────────────────────────────────────
with st.expander("Show raw price data"):
    price_chart = df.set_index("Date")[["Close"]]
    st.line_chart(price_chart)
