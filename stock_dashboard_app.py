import math
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import yfinance as yf
from pandas import DataFrame

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

METRIC_DEFINITIONS = {
    "Price": "Latest market price from Yahoo Finance. This is the stock's current trading price.",
    "52W High": "Highest price reached in the past 12 months. Useful as a reference point for momentum and previous peaks.",
    "52W Low": "Lowest price reached in the past 12 months. Helps you understand downside range.",
    "Pullback %": "Percent drop from the 52-week high, calculated as (52W High - Price) / 52W High. A larger pullback can mean a more interesting entry, but only if the business is still strong.",
    "P/E": "Trailing price-to-earnings ratio using the last 12 months of earnings. Lower can mean cheaper, but fast-growing stocks often trade at higher P/E ratios.",
    "Forward P/E": "Price relative to expected future earnings based on analyst estimates. Often more useful for growth stocks than trailing P/E.",
    "Revenue Growth %": "A year-by-year history built from annual financial statements. Format is newest comparison first, like +25.0% (1Y 2026 vs 2025) | -40.0% (2Y 2025 vs 2024).",
    "Earnings Growth %": "A year-by-year history of net income growth from annual financial statements, shown in the same format as revenue growth.",
    "Profit Margin %": "Net profit margin history by year, shown as annual values in a newest-first timeline like +22.4% (1Y 2026) | +18.1% (2Y 2025).",
    "Operating Margin %": "Operating margin history by year, shown as annual values in the same newest-first timeline format when available.",
    "ROE %": "Return on equity by year, shown as annual values in the same newest-first timeline format when available.",
    "Debt to Equity": "Debt relative to shareholder equity. Lower is usually safer. Under 50 is low, 50-120 is moderate, above 120 is heavy leverage.",
    "Checklist Score": "A simple composite score based on growth, profitability, debt, valuation, and pullback.",
    "Rating": "Quick label based on the checklist score: Strong, Good, Mixed, or Weak.",
    "Signal": "Decision helper based on your rules for P/E, growth, and pullback. Buy zone means all conditions are met. Watch closely means some good signs are present. Quality, maybe wait means the business may be strong but the setup is not ideal yet. Needs review means the setup is weaker.",
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



def metric_legend_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"Metric": k, "What it means": v} for k, v in METRIC_DEFINITIONS.items()]
    )



def color_metric(val: Any, column: str) -> str:
    if val is None or val == "N/A" or (isinstance(val, float) and math.isnan(val)):
        return "background-color: #f3f4f6; color: #6b7280"

    if isinstance(val, str) and "|" in val:
        first_part = val.split("|")[0].strip()
        try:
            num = float(first_part.split("%", 1)[0].replace("+", "").strip())
        except Exception:
            return ""
    else:
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


def _safe_div(a: Any, b: Any) -> Any:
    try:
        if a is None or b in (None, 0):
            return None
        return a / b
    except Exception:
        return None


def _build_series_from_financials(fin: DataFrame, row_name: str) -> Dict[str, Any]:
    if fin is None or fin.empty or row_name not in fin.index:
        return {}
    series = fin.loc[row_name]
    data = {}
    for col, val in series.items():
        try:
            year = pd.to_datetime(col).year
        except Exception:
            continue
        num = safe_num(val)
        if num is not None:
            data[str(year)] = num
    return dict(sorted(data.items(), reverse=True))


def _build_growth_history(year_map: Dict[str, Any], periods: int = 5) -> str:
    years = list(year_map.keys())
    vals = list(year_map.values())
    parts = []
    for i in range(min(periods, len(vals) - 1)):
        curr = vals[i]
        prev = vals[i + 1]
        curr_year = years[i]
        prev_year = years[i + 1]
        if prev in (None, 0):
            continue
        growth = ((curr - prev) / abs(prev)) * 100
        label = f"{i + 1}Y {curr_year} vs {prev_year}"
        parts.append(f"{growth:+.1f}% ({label})")
    return " | ".join(parts) if parts else "N/A"


def _build_margin_history(year_map_num: Dict[str, Any], year_map_den: Dict[str, Any], periods: int = 5) -> str:
    common_years = [y for y in year_map_num.keys() if y in year_map_den]
    common_years = sorted(common_years, reverse=True)
    parts = []
    for i, year in enumerate(common_years[:periods]):
        ratio = _safe_div(year_map_num.get(year), year_map_den.get(year))
        if ratio is None:
            continue
        parts.append(f"{ratio * 100:+.1f}% ({i + 1}Y {year})")
    return " | ".join(parts) if parts else "N/A"

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


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_one(ticker: str) -> Dict[str, Any]:
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    price = safe_num(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice"))
    high_52w = safe_num(info.get("fiftyTwoWeekHigh"))
    low_52w = safe_num(info.get("fiftyTwoWeekLow"))
    pe = safe_num(info.get("trailingPE"))
    fwd_pe = safe_num(info.get("forwardPE"))
    debt_to_equity = safe_num(info.get("debtToEquity"))
    beta = safe_num(info.get("beta"))
    analyst_target = safe_num(info.get("targetMeanPrice"))
    market_cap = safe_num(info.get("marketCap"))

    try:
        financials = tk.financials
    except Exception:
        financials = pd.DataFrame()
    try:
        balance_sheet = tk.balance_sheet
    except Exception:
        balance_sheet = pd.DataFrame()

    revenue_map = _build_series_from_financials(financials, "Total Revenue")
    net_income_map = _build_series_from_financials(financials, "Net Income")
    operating_income_map = _build_series_from_financials(financials, "Operating Income")
    equity_map = _build_series_from_financials(balance_sheet, "Stockholders Equity")

    revenue_growth_latest = None
    if len(revenue_map) >= 2:
        vals = list(revenue_map.values())
        if vals[1] not in (None, 0):
            revenue_growth_latest = round(((vals[0] - vals[1]) / abs(vals[1])) * 100, 2)

    earnings_growth_latest = None
    if len(net_income_map) >= 2:
        vals = list(net_income_map.values())
        if vals[1] not in (None, 0):
            earnings_growth_latest = round(((vals[0] - vals[1]) / abs(vals[1])) * 100, 2)

    revenue_growth_history = _build_growth_history(revenue_map, periods=5)
    earnings_growth_history = _build_growth_history(net_income_map, periods=5)
    profit_margin_history = _build_margin_history(net_income_map, revenue_map, periods=5)
    operating_margin_history = _build_margin_history(operating_income_map, revenue_map, periods=5)
    roe_history = _build_margin_history(net_income_map, equity_map, periods=5)

    pullback = pct_pullback(high_52w, price)
    upside_to_target = None
    if price and analyst_target and price != 0:
        upside_to_target = round(((analyst_target - price) / price) * 100, 2)

    if revenue_growth_latest is None:
        growth_bucket = "N/A"
    elif revenue_growth_latest >= 20:
        growth_bucket = "High"
    elif revenue_growth_latest >= 8:
        growth_bucket = "Moderate"
    else:
        growth_bucket = "Low"

    latest_profit_margin = None
    common_rev_years = [y for y in net_income_map.keys() if y in revenue_map]
    if common_rev_years:
        y = sorted(common_rev_years, reverse=True)[0]
        ratio = _safe_div(net_income_map.get(y), revenue_map.get(y))
        if ratio is not None:
            latest_profit_margin = round(ratio * 100, 2)

    if latest_profit_margin is None:
        profitability_bucket = "N/A"
    elif latest_profit_margin >= 20:
        profitability_bucket = "High"
    elif latest_profit_margin >= 8:
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
    if revenue_growth_history != "N/A":
        notes.append(f"Revenue: {revenue_growth_history}")
    if earnings_growth_history != "N/A":
        notes.append(f"Earnings: {earnings_growth_history}")
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
        "Revenue Growth %": revenue_growth_history,
        "Earnings Growth %": earnings_growth_history,
        "Profit Margin %": profit_margin_history,
        "Operating Margin %": operating_margin_history,
        "ROE %": roe_history,
        "Revenue Growth Latest": revenue_growth_latest,
        "Earnings Growth Latest": earnings_growth_latest,
        "Profit Margin Latest": latest_profit_margin,
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

    rev = row.get("Revenue Growth Latest")
    margin = row.get("Profit Margin Latest")
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
    growth = row.get("Revenue Growth Latest")
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
        styler = styler.map(color_rating, subset=["Rating"])

    styler = styler.set_properties(**{"white-space": "nowrap", "font-size": "13px"})
    return styler


st.title("📈 Daily Stock Checklist")
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

    with st.expander("Metric definitions", expanded=True):
        defs_df = metric_legend_df().copy()
        defs_df["What it means"] = defs_df["What it means"].astype(str)
        st.table(defs_df)

    legend_df = pd.DataFrame(
        [
            {"Color": "Green", "Meaning": "Generally favorable / stronger"},
            {"Color": "Yellow", "Meaning": "Mixed / okay / watch"},
            {"Color": "Blue", "Meaning": "Neutral quality / wait"},
            {"Color": "Red", "Meaning": "Weaker / expensive / riskier"},
            {"Color": "Gray", "Meaning": "Missing or unavailable data"},
        ]
    )
    st.markdown("**Color legend**")
    st.dataframe(legend_df, use_container_width=True, hide_index=True)

    st.markdown("**Sources**")
    st.markdown(
        """
- [Yahoo Finance](https://finance.yahoo.com/) for price, valuation, and company fundamentals
- [yfinance Python library](https://pypi.org/project/yfinance/) for pulling Yahoo Finance data into the app
- [Streamlit](https://streamlit.io/) for the app interface
        """
    )

    main_cols = [
        "Ticker", "Name", "Price", "52W High", "52W Low", "Pullback %", "P/E", "Forward P/E",
        "Revenue Growth %", "Earnings Growth %", "Profit Margin %", "Operating Margin %", "ROE %",
        "Debt to Equity", "Checklist Score", "Rating", "Signal", "My Note"
    ]
    watchlist_df = df[[c for c in main_cols if c in df.columns]].copy().sort_values(
        by=["Checklist Score", "Pullback %"],
        ascending=[False, False],
    )

    st.markdown("**Tip:** Use fullscreen on the table if you want the widest possible view.")
    st.dataframe(
        style_watchlist(watchlist_df),
        use_container_width=True,
        hide_index=True,
        height=min(900, 45 * (len(watchlist_df) + 1) + 40),
    )

    csv = watchlist_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download watchlist CSV",
        data=csv,
        file_name="daily_stock_watchlist.csv",
        mime="text/csv",
    )

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
        st.markdown(f"- Revenue growth history: **{row.get('Revenue Growth %') if row.get('Revenue Growth %') is not None else 'N/A'}**")
        st.markdown(f"- Earnings growth history: **{row.get('Earnings Growth %') if row.get('Earnings Growth %') is not None else 'N/A'}**")
        st.markdown(f"- Profit margin history: **{row.get('Profit Margin %') if row.get('Profit Margin %') is not None else 'N/A'}**")
        st.markdown(f"- Operating margin history: **{row.get('Operating Margin %') if row.get('Operating Margin %') is not None else 'N/A'}**")
        st.markdown(f"- ROE history: **{row.get('ROE %') if row.get('ROE %') is not None else 'N/A'}**")
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
