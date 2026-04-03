import math
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Daily Stock Checklist", page_icon="📈", layout="wide")

DEFAULT_TICKERS = [
    "PLTR", "NVDA", "MSFT", "AMD", "WMT", "IREN", "VOO", "QQQ", "SCHD",
    "AGX", "ONDS", "TSLA", "SNDK", "MRVL", "TSM", "MELI", "AMZN", "GOOGL",
    "NBIS", "KTOS", "MU"
]

DEFAULT_NOTES = {
    "PLTR": "High-upside AI/data platform; valuation usually rich.",
    "NVDA": "AI leader; best bought on pullbacks.",
    "MSFT": "High-quality compounder.",
    "AMD": "Strong semiconductor growth story.",
    "WMT": "Defensive compounder.",
    "VOO": "Core S&P 500 ETF.",
    "QQQ": "Growth-heavy Nasdaq ETF.",
    "SCHD": "Dividend/income ETF.",
    "TSLA": "Volatile growth name.",
    "AMZN": "Long-term cloud + ads + ecommerce.",
    "GOOGL": "Strong cash machine; often more reasonably valued than peers.",
    "TSM": "Critical semiconductor foundry.",
    "MU": "Cyclical memory play.",
}


def safe_num(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def safe_pct_from_decimal(value: Any) -> Any:
    value = safe_num(value)
    if value is None:
        return None
    return round(value * 100, 2)


def pct_pullback(high: Any, current: Any) -> Any:
    high = safe_num(high)
    current = safe_num(current)
    if not high or not current or high == 0:
        return None
    return round(((high - current) / high) * 100, 2)


def format_large_number(value: Any) -> str:
    value = safe_num(value)
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000_000:
        return f"${value/1_000_000_000_000:.2f}T"
    if abs_val >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    return f"${value:,.0f}"


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_one(ticker: str) -> Dict[str, Any]:
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    price = safe_num(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice"))
    high_52w = safe_num(info.get("fiftyTwoWeekHigh"))
    low_52w = safe_num(info.get("fiftyTwoWeekLow"))
    pe = safe_num(info.get("trailingPE"))
    fwd_pe = safe_num(info.get("forwardPE"))
    revenue_growth = safe_pct_from_decimal(info.get("revenueGrowth"))
    earnings_growth = safe_pct_from_decimal(info.get("earningsGrowth"))
    profit_margin = safe_pct_from_decimal(info.get("profitMargins"))
    operating_margin = safe_pct_from_decimal(info.get("operatingMargins"))
    debt_to_equity = safe_num(info.get("debtToEquity"))
    roe = safe_pct_from_decimal(info.get("returnOnEquity"))
    market_cap = safe_num(info.get("marketCap"))
    beta = safe_num(info.get("beta"))
    analyst_target = safe_num(info.get("targetMeanPrice"))

    pullback = pct_pullback(high_52w, price)
    upside_to_target = None
    if price and analyst_target and price != 0:
        upside_to_target = round(((analyst_target - price) / price) * 100, 2)

    if revenue_growth is None:
        growth_bucket = "N/A"
    elif revenue_growth >= 20:
        growth_bucket = "High"
    elif revenue_growth >= 8:
        growth_bucket = "Moderate"
    else:
        growth_bucket = "Low"

    if profit_margin is None:
        profitability_bucket = "N/A"
    elif profit_margin >= 20:
        profitability_bucket = "High"
    elif profit_margin >= 8:
        profitability_bucket = "Medium"
    else:
        profitability_bucket = "Low"

    if debt_to_equity is None:
        debt_bucket = "N/A"
    elif debt_to_equity < 50:
        debt_bucket = "Low"
    elif debt_to_equity < 120:
        debt_bucket = "Medium"
    else:
        debt_bucket = "High"

    summary = info.get("longBusinessSummary") or ""
    short_summary = summary[:220] + "..." if len(summary) > 220 else summary

    notes = []
    if revenue_growth is not None:
        notes.append(f"Revenue growth {revenue_growth}%")
    if earnings_growth is not None:
        notes.append(f"Earnings growth {earnings_growth}%")
    if profit_margin is not None:
        notes.append(f"Profit margin {profit_margin}%")
    if pullback is not None:
        notes.append(f"{pullback}% below 52W high")

    return {
        "Ticker": ticker,
        "Name": info.get("shortName") or info.get("longName") or ticker,
        "Sector": info.get("sector") or info.get("category") or "N/A",
        "Price": price,
        "52W High": high_52w,
        "52W Low": low_52w,
        "Pullback %": pullback,
        "P/E": round(pe, 2) if pe is not None else None,
        "Forward P/E": round(fwd_pe, 2) if fwd_pe is not None else None,
        "Revenue Growth %": revenue_growth,
        "Earnings Growth %": earnings_growth,
        "Profit Margin %": profit_margin,
        "Operating Margin %": operating_margin,
        "ROE %": roe,
        "Debt to Equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
        "Market Cap": market_cap,
        "Beta": round(beta, 2) if beta is not None else None,
        "Analyst Target": round(analyst_target, 2) if analyst_target is not None else None,
        "Upside to Target %": upside_to_target,
        "Growth Bucket": growth_bucket,
        "Profitability Bucket": profitability_bucket,
        "Debt Bucket": debt_bucket,
        "Quick Notes": " | ".join(notes),
        "Business": short_summary,
        "My Note": DEFAULT_NOTES.get(ticker, ""),
    }


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_all(tickers: List[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        clean = ticker.strip().upper()
        if not clean:
            continue
        try:
            rows.append(fetch_one(clean))
        except Exception as exc:
            rows.append({
                "Ticker": clean,
                "Name": "Error loading",
                "Quick Notes": str(exc),
                "My Note": "",
            })
    return pd.DataFrame(rows)


def score_stock(row: pd.Series) -> int:
    score = 0

    rev = row.get("Revenue Growth %")
    margin = row.get("Profit Margin %")
    debt = row.get("Debt to Equity")
    pe = row.get("P/E")
    pullback = row.get("Pullback %")

    if isinstance(rev, (int, float)):
        score += 5 if rev >= 20 else 4 if rev >= 10 else 3 if rev >= 5 else 1
    if isinstance(margin, (int, float)):
        score += 5 if margin >= 20 else 4 if margin >= 10 else 3 if margin >= 5 else 1
    if isinstance(debt, (int, float)):
        score += 5 if debt < 50 else 3 if debt < 120 else 1
    if isinstance(pe, (int, float)):
        score += 5 if pe < 20 else 4 if pe < 30 else 3 if pe < 45 else 1
    if isinstance(pullback, (int, float)):
        score += 5 if pullback >= 25 else 4 if pullback >= 15 else 3 if pullback >= 8 else 1

    return score


def rating_label(score: int) -> str:
    if score >= 22:
        return "Strong"
    if score >= 16:
        return "Good"
    if score >= 10:
        return "Mixed"
    return "Weak"


def signal_from_rules(row: pd.Series, max_pe: float, min_growth: float, min_pullback: float) -> str:
    pe = row.get("P/E")
    growth = row.get("Revenue Growth %")
    pullback = row.get("Pullback %")

    pe_ok = isinstance(pe, (int, float)) and pe <= max_pe
    growth_ok = isinstance(growth, (int, float)) and growth >= min_growth
    dip_ok = isinstance(pullback, (int, float)) and pullback >= min_pullback

    if pe_ok and growth_ok and dip_ok:
        return "✅ Buy zone"
    if growth_ok and dip_ok:
        return "👀 Watch closely"
    if growth_ok:
        return "📌 Quality, maybe wait"
    return "⚠️ Needs review"


def style_watchlist(df: pd.DataFrame):
    def color_signal(val: str) -> str:
        if "Buy zone" in str(val):
            return "background-color: #dcfce7; color: #166534"
        if "Watch closely" in str(val):
            return "background-color: #fef9c3; color: #854d0e"
        if "Quality, maybe wait" in str(val):
            return "background-color: #e0f2fe; color: #075985"
        if "Needs review" in str(val):
            return "background-color: #fee2e2; color: #991b1b"
        return ""

    def color_rating(val: str) -> str:
        if val == "Strong":
            return "background-color: #dcfce7; color: #166534"
        if val == "Good":
            return "background-color: #fef9c3; color: #854d0e"
        if val == "Mixed":
            return "background-color: #e0f2fe; color: #075985"
        if val == "Weak":
            return "background-color: #fee2e2; color: #991b1b"
        return ""

    styler = df.style

    for col in df.columns:
        if col in [
            "P/E", "Forward P/E", "Revenue Growth %", "Earnings Growth %",
            "Profit Margin %", "Operating Margin %", "ROE %", "Debt to Equity",
            "Pullback %", "Checklist Score"
        ]:
            styler = styler.map(lambda v, c=col: color_metric(v, c), subset=[col])

    if "Signal" in df.columns:
        styler = styler.map(color_signal, subset=["Signal"])
    if "Rating" in df.columns:
        styler = styler.map(color_rating, subset=["


st.title("📈 Daily Stock Checklist")

METRIC_DEFINITIONS = {
    "Price": "Latest market price pulled from Yahoo Finance.",
    "52W High": "Highest price reached in the last 52 weeks.",
    "52W Low": "Lowest price reached in the last 52 weeks.",
    "Pullback %": "How far the stock is below its 52-week high. Bigger pullbacks can mean a better entry, but not always.",
    "P/E": "Trailing price-to-earnings ratio. Lower can be better, but growth stocks often deserve higher P/E.",
    "Forward P/E": "Price compared with expected future earnings.",
    "Revenue Growth %": "How fast sales are growing year over year.",
    "Earnings Growth %": "How fast earnings are growing year over year.",
    "Profit Margin %": "Percent of revenue that becomes profit. Higher is usually better.",
    "Operating Margin %": "Profit from operations before some non-operating items. Higher is better.",
    "ROE %": "Return on equity. Shows how efficiently the company uses shareholder capital.",
    "Debt to Equity": "Debt relative to shareholder equity. Lower is usually safer.",
    "Checklist Score": "A simple score based on growth, profitability, debt, valuation, and pullback.",
    "Rating": "Overall quick label based on the checklist score.",
    "Signal": "A shortlist signal based on your own rules in the sidebar.",
}

def metric_legend_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"Metric": k, "What it means": v} for k, v in METRIC_DEFINITIONS.items()]
    )


def color_metric(val: Any, column: str) -> str:
    if val is None or val == "N/A" or (isinstance(val, float) and math.isnan(val)):
        return "background-color: #f3f4f6; color: #6b7280"

    try:
        num = float(val)
    except Exception:
        return ""

    if column in ["Revenue Growth %", "Earnings Growth %"]:
        if num >= 20:
            return "background-color: #dcfce7; color: #166534"
        if num >= 8:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    if column in ["Profit Margin %", "Operating Margin %", "ROE %"]:
        if num >= 20:
            return "background-color: #dcfce7; color: #166534"
        if num >= 8:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    if column == "Debt to Equity":
        if num < 50:
            return "background-color: #dcfce7; color: #166534"
        if num < 120:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    if column in ["P/E", "Forward P/E"]:
        if num < 20:
            return "background-color: #dcfce7; color: #166534"
        if num < 35:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    if column == "Pullback %":
        if num >= 20:
            return "background-color: #dcfce7; color: #166534"
        if num >= 8:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    if column == "Checklist Score":
        if num >= 22:
            return "background-color: #dcfce7; color: #166534"
        if num >= 16:
            return "background-color: #fef9c3; color: #854d0e"
        return "background-color: #fee2e2; color: #991b1b"

    return ""
st.caption("A simple investing dashboard that refreshes from Yahoo Finance and turns your watchlist into a daily checklist.")

with st.sidebar:
    st.header("Watchlist")
    ticker_text = st.text_area(
        "Tickers (comma-separated)",
        value=", ".join(DEFAULT_TICKERS),
        height=180,
    )
    tickers = [t.strip().upper() for t in ticker_text.split(",") if t.strip()]

    st.header("Your rules")
    max_pe = st.slider("Max P/E for comfort", min_value=10, max_value=120, value=40, step=1)
    min_growth = st.slider("Minimum revenue growth %", min_value=0, max_value=50, value=10, step=1)
    min_pullback = st.slider("Minimum pullback % to care", min_value=0, max_value=50, value=10, step=1)

    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.write("**Simple rule:**")
    st.write("Growth + reasonable valuation + a dip = better hunting ground.")

last_loaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.write(f"Last opened: **{last_loaded}**")

df = fetch_all(tickers)

if df.empty:
    st.warning("No tickers loaded.")
    st.stop()

df["Checklist Score"] = df.apply(score_stock, axis=1)
df["Rating"] = df["Checklist Score"].apply(rating_label)
df["Signal"] = df.apply(lambda row: signal_from_rules(row, max_pe, min_growth, min_pullback), axis=1)

summary1, summary2, summary3, summary4 = st.columns(4)
summary1.metric("Stocks tracked", len(df))
summary2.metric("Buy zones", int((df["Signal"] == "✅ Buy zone").sum()))
summary3.metric("Avg checklist score", round(df["Checklist Score"].mean(), 1) if len(df) else 0)
summary4.metric("Strong or good", int(df["Rating"].isin(["Strong", "Good"]).sum()))

tab1, tab2, tab3, tab4 = st.tabs(["Watchlist", "Deep Dive", "Buy Signals", "How to Use"])

with tab1:
    st.subheader("Main watchlist")
    main_cols = [
        "Ticker", "Name", "Price", "52W High", "Pullback %", "P/E", "Forward P/E",
        "Revenue Growth %", "Profit Margin %", "Debt to Equity", "Checklist Score", "Rating", "Signal", "My Note"
    ]
    watchlist_df = df[[c for c in main_cols if c in df.columns]].copy().sort_values(by=["Checklist Score", "Pullback %"], ascending=[False, False])
    st.dataframe(style_watchlist(watchlist_df), use_container_width=True, hide_index=True)

    csv = watchlist_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download watchlist CSV", data=csv, file_name="daily_stock_watchlist.csv", mime="text/csv")

with tab2:
    st.subheader("One stock at a time")
    selected = st.selectbox("Choose a ticker", options=df["Ticker"].tolist())
    row = df[df["Ticker"] == selected].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Price", row.get("Price") if row.get("Price") is not None else "N/A")
    c2.metric("P/E", row.get("P/E") if row.get("P/E") is not None else "N/A")
    c3.metric("Revenue Growth %", row.get("Revenue Growth %") if row.get("Revenue Growth %") is not None else "N/A")
    c4.metric("Pullback %", row.get("Pullback %") if row.get("Pullback %") is not None else "N/A")

    left, right = st.columns([1.2, 1])
    with left:
        st.write("**Quick interpretation**")
        interpretation = {
            "Name": row.get("Name"),
            "Sector": row.get("Sector"),
            "Growth Bucket": row.get("Growth Bucket"),
            "Profitability Bucket": row.get("Profitability Bucket"),
            "Debt Bucket": row.get("Debt Bucket"),
            "Checklist Score": row.get("Checklist Score"),
            "Rating": row.get("Rating"),
            "Signal": row.get("Signal"),
            "My Note": row.get("My Note"),
        }
        st.json(interpretation)

        st.write("**Business summary**")
        st.write(row.get("Business") or "No summary available.")

    with right:
        st.write("**Extra metrics**")
        st.markdown(f"- Market cap: **{format_large_number(row.get('Market Cap'))}**")
        st.markdown(f"- Profit margin: **{row.get('Profit Margin %') if row.get('Profit Margin %') is not None else 'N/A'}%**")
        st.markdown(f"- Operating margin: **{row.get('Operating Margin %') if row.get('Operating Margin %') is not None else 'N/A'}%**")
        st.markdown(f"- ROE: **{row.get('ROE %') if row.get('ROE %') is not None else 'N/A'}%**")
        st.markdown(f"- Debt to equity: **{row.get('Debt to Equity') if row.get('Debt to Equity') is not None else 'N/A'}**")
        st.markdown(f"- Analyst target: **{row.get('Analyst Target') if row.get('Analyst Target') is not None else 'N/A'}**")
        st.markdown(f"- Upside to target: **{row.get('Upside to Target %') if row.get('Upside to Target %') is not None else 'N/A'}%**")
        st.markdown(f"- Beta: **{row.get('Beta') if row.get('Beta') is not None else 'N/A'}**")
        st.write("**Quick notes**")
        st.write(row.get("Quick Notes") or "No notes available.")

with tab3:
    st.subheader("Names matching your rules")
    signals_df = df[df["Signal"].isin(["✅ Buy zone", "👀 Watch closely", "📌 Quality, maybe wait"])].copy()
    signal_cols = ["Ticker", "Name", "Price", "P/E", "Revenue Growth %", "Pullback %", "Checklist Score", "Rating", "Signal"]
    signals_df = signals_df[[c for c in signal_cols if c in signals_df.columns]].sort_values(by=["Signal", "Checklist Score"], ascending=[True, False])

    if len(signals_df):
        st.dataframe(style_watchlist(signals_df), use_container_width=True, hide_index=True)
    else:
        st.info("Nothing matches your current rules yet.")

    st.write("**Suggested way to use this tab**")
    st.write("Look at buy zones first. Then open the deep dive tab and decide whether the valuation and business still make sense to you.")

with tab4:
    st.subheader("How to use this app in 5 minutes a day")
    st.markdown(
        """
1. Open the **Watchlist** tab.
2. Look for names with a strong score and a useful pullback.
3. Check whether revenue growth is still healthy.
4. Open **Deep Dive** for the stocks you already like.
5. Use **Buy Signals** as a shortlist, not an automatic buy button.

**Good rule of thumb:**
- ETFs: ignore P/E sometimes if the fund structure makes it messy.
- Hyper-growth names: a high P/E can still be okay if growth is very strong.
- Cyclical stocks: revenue and margins can swing a lot, so be careful.
        """
    )

st.markdown("---")
st.markdown("### Local setup")
st.code(
    "pip install streamlit yfinance pandas\nstreamlit run stock_dashboard_app.py",
    language="bash",
)
st.markdown("### Optional next upgrades")
st.markdown(
    "- Add email alerts\n"
    "- Save your own notes per stock\n"
    "- Track your cost basis and position size\n"
    "- Add earnings dates and dividend yields"
)

# Save this file locally as: stock_dashboard_app.py
