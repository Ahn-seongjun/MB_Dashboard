from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="데르뜨 Sales Dashboard",
    page_icon="🍰",
    layout="wide",
    initial_sidebar_state="expanded",
)


COLORS = {
    "primary": "#7C3AED",
    "secondary": "#EC4899",
    "accent": "#F59E0B",
    "success": "#10B981",
    "muted": "#64748B",
    "grid": "#E2E8F0",
}

# 집계 로직 변경 시 값을 올리면 기존 Streamlit 데이터 캐시를 즉시 폐기합니다.
DATA_TRANSFORM_VERSION = 7


st.markdown(
    """
    <style>
        .stApp { background: #F7F7FB; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #ECECF2; }
        /* Streamlit의 고정 상단 툴바 아래에서 본문이 시작되도록 여백 확보 */
        .block-container { padding-top: 4.5rem; padding-bottom: 2rem; }
        .brand { font-size: 1.65rem; font-weight: 800; letter-spacing: -0.04em; color: #211A2F; }
        .brand-sub { color: #777184; font-size: .9rem; margin-top: -.25rem; }
        .section-title { font-size: 1.1rem; font-weight: 750; color: #211A2F; margin: .4rem 0 .2rem; }
        .section-sub { color: #777184; font-size: .84rem; margin-bottom: .8rem; }
        [data-testid="stMetric"] {
            background: #FFFFFF; border: 1px solid #ECECF2; border-radius: 16px;
            padding: 18px 20px; box-shadow: 0 3px 14px rgba(42, 32, 60, .04);
        }
        [data-testid="stMetricLabel"] { color: #777184; }
        [data-testid="stMetricValue"] { color: #211A2F; }
        div[data-testid="stPlotlyChart"] {
            background: white; border: 1px solid #ECECF2; border-radius: 16px;
            padding: 8px; box-shadow: 0 3px 14px rgba(42, 32, 60, .04);
        }
        .status-pill {
            display: inline-block; padding: 5px 10px; border-radius: 999px;
            background: #EDE9FE; color: #6D28D9; font-size: .78rem; font-weight: 700;
        }
        .nav-title { color: #9A94A3; font-size: .7rem; font-weight: 800; letter-spacing: .12em; margin: .2rem 0 .55rem; }
        [data-testid="stSidebar"] div[role="radiogroup"] { gap: .45rem; }
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            width: 100%; padding: .72rem .78rem; border: 1px solid #ECECF2;
            border-radius: 12px; background: #FAFAFC; transition: all .15s ease;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            border-color: #C4B5FD; background: #F5F3FF;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            border-color: #8B5CF6; background: #EDE9FE;
            box-shadow: 0 4px 12px rgba(124, 58, 237, .10);
        }
        [data-testid="stSidebar"] div[role="radiogroup"] input { display: none; }
        [data-testid="stSidebar"] div[role="radiogroup"] p { font-weight: 700; color: #3E3650; }
        .insight-box {
            padding: 15px 18px; border-radius: 14px; background: linear-gradient(90deg, #F5F3FF, #FDF2F8);
            border: 1px solid #E9D5FF; color: #4C3C63; font-size: .92rem; margin: .7rem 0 1rem;
        }
        .insight-box b { color: #6D28D9; }
    </style>
    """,
    unsafe_allow_html=True,
)


def won(value: float) -> str:
    """Compact Korean won formatter."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 100_000_000:
        return f"{sign}{value / 100_000_000:,.1f}억원"
    if value >= 10_000:
        return f"{sign}{value / 10_000:,.0f}만원"
    return f"{sign}{value:,.0f}원"


def percent_change(current: float, previous: float) -> float:
    return 0.0 if previous == 0 else (current - previous) / previous * 100


def comparison_period(
    start_date: date | pd.Timestamp,
    end_date: date | pd.Timestamp,
    frequency: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """현재 선택 기간과 길이·달력 위치가 대응되는 이전 비교 기간을 반환합니다."""
    current_start = pd.Timestamp(start_date).normalize()
    current_end = pd.Timestamp(end_date).normalize()

    if frequency == "일간":
        return current_start - pd.DateOffset(days=1), current_end - pd.DateOffset(days=1)
    if frequency == "월간":
        previous_start = current_start - pd.DateOffset(months=1)
        previous_end = current_end - pd.DateOffset(months=1)
        # 현재 날짜가 말일이면 일수 차이가 있는 전월도 말일까지 비교합니다.
        if current_start.is_month_end:
            previous_start = previous_start + pd.offsets.MonthEnd(0)
        if current_end.is_month_end:
            previous_end = previous_end + pd.offsets.MonthEnd(0)
        return previous_start, previous_end

    return current_start - pd.DateOffset(days=7), current_end - pd.DateOffset(days=7)


def weighted_unit_price(frame: pd.DataFrame) -> float:
    total_quantity = frame["quantity"].sum()
    if total_quantity == 0:
        return 0.0
    return float((frame["unit_price"] * frame["quantity"]).sum() / total_quantity)


def clean_product_name(product_name: object, product_spec: object) -> str:
    """제품명에서 규격 문자열을 제거하고 끝의 밑줄·공백을 정리합니다."""
    name = "" if pd.isna(product_name) else str(product_name)
    spec = "" if pd.isna(product_spec) else str(product_spec)
    name = name.replace("\u00a0", " ").strip()
    spec = spec.replace("\u00a0", " ").strip()
    if spec:
        name = name.replace(spec, "")
    name = re.sub(r"[_\s]+$", "", name).strip()
    return name or "미분류"


def aggregate_query_result(frame: pd.DataFrame) -> pd.DataFrame:
    """원본 쿼리 결과를 대시보드 일별 집계 구조로 변환합니다."""
    korean_column_map = {
        "일자": "date",
        "유통경로": "channel",
        "매출처명": "account_name",
        "품목명": "product_name",
        "규격": "product_spec",
        "MC 대분류": "category_large",
        "MC 중분류": "category_middle",
        "MC 소분류": "category_small",
        "MC 세분류": "category_detail",
        "단가": "unit_price",
        "수량": "quantity",
        "공급가": "sales",
        "원가": "cost",
        "매출원가": "cost",
        "매출이익": "profit",
        "매출이익액": "profit",
        "매출총이익": "profit",
        "영업이익": "profit",
        "주문건수": "orders",
        "매출구분": "sales_type",
    }
    frame = frame.copy()
    frame.columns = (
        frame.columns.astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )
    rename_columns = {
        source: target
        for source, target in korean_column_map.items()
        if source in frame.columns and target not in frame.columns
    }
    frame = frame.rename(columns=rename_columns)

    if "product_name" in frame.columns and "product_spec" in frame.columns:
        frame["product_name"] = [
            clean_product_name(name, spec)
            for name, spec in zip(frame["product_name"], frame["product_spec"])
        ]

    dimension_columns = [
        "date",
        "channel",
        "account_name",
        "product_name",
        "category_large",
        "category_middle",
        "category_small",
        "category_detail",
    ]
    required_columns = set(dimension_columns + ["sales", "unit_price", "quantity"])
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(
            "원본 쿼리 결과에 집계용 필수 컬럼이 없습니다: " + ", ".join(missing)
        )

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    # 필터 선택지에서 NULL 차원이 빠지면서 원장 행 자체가 누락되지 않도록 보존합니다.
    text_dimensions = [column for column in dimension_columns if column != "date"]
    for column in text_dimensions:
        frame[column] = (
            frame[column]
            .fillna("(미분류)")
            .astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.strip()
            .replace("", "(미분류)")
        )
    for column in ("sales", "unit_price", "quantity"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    if "cost" in frame.columns:
        frame["cost"] = pd.to_numeric(frame["cost"], errors="coerce").fillna(0)
    else:
        frame["cost"] = 0.0

    if "profit" in frame.columns:
        frame["profit"] = pd.to_numeric(frame["profit"], errors="coerce").fillna(0)
    elif frame["cost"].ne(0).any():
        frame["profit"] = frame["sales"] - frame["cost"]
    else:
        frame["profit"] = 0.0

    if "sales_type" in frame.columns:
        sales_type = (
            frame["sales_type"]
            .fillna("")
            .astype(str)
            .str.replace("\u00a0", " ", regex=False)
            .str.strip()
            .str.replace(r"\s+", "", regex=True)
        )
        reversal_mask = sales_type.isin({
            "추가판매반품",
            "판매취소",
            "매출반품",
            "매출취소",
            "매출취소-매출이관(매장)",
            "매출취소-매출이관(상품)",
        })
        frame["orders"] = np.where(reversal_mask, -1, 1)
    elif "orders" in frame.columns:
        frame["orders"] = pd.to_numeric(frame["orders"], errors="coerce").fillna(0)
        reversal_mask = frame["orders"].lt(0)
    else:
        frame["orders"] = 1
        reversal_mask = pd.Series(False, index=frame.index)

    # 화면에서 주문건수 산식을 원장 행 기준으로 검산하기 위한 감사용 지표입니다.
    frame["source_rows"] = 1
    frame["reversal_rows"] = reversal_mask.astype(int)

    frame["weighted_unit_amount"] = frame["unit_price"] * frame["quantity"]
    metric_columns = [
        "sales", "cost", "profit", "orders", "source_rows", "reversal_rows",
        "quantity", "weighted_unit_amount",
    ]
    prepared = frame[dimension_columns + metric_columns].copy()
    aggregated = prepared.groupby(dimension_columns, as_index=False, dropna=False)[metric_columns].sum()
    aggregated["unit_price"] = np.where(
        aggregated["quantity"] == 0,
        0,
        aggregated["weighted_unit_amount"] / aggregated["quantity"],
    )
    return aggregated.drop(columns="weighted_unit_amount").sort_values("date")


@st.cache_data(ttl=600)
def make_sample_data() -> pd.DataFrame:
    """DB 연결 전 화면 확인용 샘플 데이터."""
    rng = np.random.default_rng(42)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=420, freq="D")
    channels = ["B2B", "KA", "온라인", "오프라인"]
    accounts_by_channel = {
        "B2B": ["삼성웰스토리", "아워홈", "CJ프레시웨이", "현대그린푸드"],
        "KA": ["GS리테일", "세븐일레븐", "이마트24", "롯데마트"],
        "온라인": ["쿠팡", "마켓컬리", "네이버 스마트스토어", "카카오 선물하기"],
        "오프라인": ["데르뜨 강남점", "데르뜨 성수점", "백화점 팝업", "플래그십 스토어"],
    }
    # 실제 MC 분류 기준을 축약한 샘플 마스터입니다.
    category_paths = [
        ("원재료가공식품", "유제품", "식물성크림", "식물성크림"),
        ("제품제과", "케익류", "생크림", "생크림"),
        ("제품제과", "케익류", "카스텔라", "카스텔라"),
        ("제품제과", "케익류", "롤", "롤"),
        ("제품제과", "케익류", "치즈", "치즈"),
        ("제품제과", "케익류", "무스", "무스"),
        ("제품제과", "구움과자류", "브라우니", "브라우니"),
        ("상품제과", "기타류", "기타", "기타"),
        ("상품제빵", "기타류", "기타", "기타"),
        ("제품제빵", "기타류", "기타", "기타"),
        ("제품제빵", "단과자빵류", "단과자", "단과자"),
        ("반제품제과", "케익류", "롤", "롤"),
        ("제품제과", "기타류", "기타", "기타"),
        ("제품제과", "구움과자류", "마들렌", "마들렌"),
        ("원재료가공식품", "향신료&식품첨가물", "액상류", "액상류"),
        ("제품제과", "구움과자류", "휘낭시에", "휘낭시에"),
        ("상품제과", "쿠키류", "쿠키", "쿠키"),
        ("제품제과", "케익류", "티라미스", "티라미스"),
        ("제품제빵", "식빵류", "식빵", "식빵"),
        ("반제품제빵", "유럽빵류", "기타", "기타"),
        ("상품제빵", "유럽빵류", "기타", "기타"),
        ("반제품제과", "케익류", "카스텔라", "카스텔라"),
        ("상품제과", "케익류", "치즈", "치즈"),
    ]
    rows: list[dict] = []

    for current_date in dates:
        weekday_factor = 1.18 if current_date.weekday() in (4, 5, 6) else 0.92
        season_factor = 1.22 if current_date.month in (2, 5, 12) else 1.0
        for channel in channels:
            orders = max(1, int(rng.normal({"B2B": 18, "KA": 25, "온라인": 58, "오프라인": 34}[channel], 7)))
            avg_price = {"B2B": 68_000, "KA": 52_000, "온라인": 29_000, "오프라인": 25_000}[channel]
            sales = orders * avg_price * weekday_factor * season_factor * rng.uniform(.86, 1.15)
            cost_ratio = {"B2B": .66, "KA": .69, "온라인": .58, "오프라인": .61}[channel]
            cost = sales * rng.uniform(cost_ratio - .03, cost_ratio + .03)
            category_large, category_middle, category_small, category_detail = category_paths[
                rng.choice(len(category_paths))
            ]
            rows.append(
                {
                    "date": current_date,
                    "channel": channel,
                    "account_name": rng.choice(accounts_by_channel[channel]),
                    "product_name": category_detail,
                    "category_large": category_large,
                    "category_middle": category_middle,
                    "category_small": category_small,
                    "category_detail": category_detail,
                    "unit_price": round(avg_price),
                    "quantity": orders,
                    "sales": round(sales),
                    "cost": round(cost),
                    "profit": round(sales - cost),
                    "orders": orders,
                    "source_rows": orders,
                    "reversal_rows": 0,
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def load_data_from_csv(
    data_version: tuple[tuple[str, int, int], ...],
    transform_version: int = 0,
) -> pd.DataFrame:
    """data 폴더의 모든 CSV를 병합해 대시보드 집계 구조로 변환합니다."""
    del data_version, transform_version  # 캐시 무효화를 위한 함수 인자
    data_dir = Path(__file__).resolve().parent / "data"
    csv_paths = sorted(data_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"CSV 파일이 없습니다: {data_dir}")

    frames: list[pd.DataFrame] = []
    for csv_path in csv_paths:
        try:
            frame = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
        except UnicodeDecodeError:
            frame = pd.read_csv(csv_path, encoding="cp949", low_memory=False)
        frames.append(frame)

    return aggregate_query_result(pd.concat(frames, ignore_index=True))


def style_figure(fig: go.Figure, height: int = 350) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=48, b=16),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", color="#413A4C", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#211A2F", font_color="white"),
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False)
    return fig


def aggregate_period(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    rules = {
        "일간": "D",
        "주간": "W-MON",
        "월간": "MS",
    }
    rule = rules.get(frequency, "W-MON")
    return (
        frame.set_index("date")
        .resample(rule)
        .agg(sales=("sales", "sum"), profit=("profit", "sum"), orders=("orders", "sum"))
        .reset_index()
    )


def render_channel_detail(frame: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
    st.markdown('<div class="brand">Channel Performance Lab</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="brand-sub">{start_date:%Y.%m.%d} — {end_date:%Y.%m.%d} · 채널과 매출처 성과를 교차 분석합니다.</div>',
        unsafe_allow_html=True,
    )

    channel_count = frame["channel"].nunique()
    account_count = frame["account_name"].nunique()
    total_sales = frame["sales"].sum()
    total_profit = frame["profit"].sum()
    total_margin = total_profit / total_sales * 100 if total_sales else 0
    summary_cols = st.columns(4)
    summary_cols[0].metric("분석 채널", f"{channel_count:,}개")
    summary_cols[1].metric("활성 매출처", f"{account_count:,}개")
    summary_cols[2].metric("총 매출", won(total_sales))
    summary_cols[3].metric(
        "매출이익률",
        f"{total_margin:.1f}%",
        help="매출이익률 = 매출이익 합계 ÷ 공급가 합계 × 100\n\n행별 이익률의 단순 평균이 아닙니다.",
    )

    daily_channel = frame.groupby(["date", "channel"], as_index=False)[["sales", "profit"]].sum()
    trend_fig = px.line(
        daily_channel,
        x="date",
        y="sales",
        color="channel",
        markers=True,
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"date": "일자", "sales": "매출", "channel": "채널"},
    )
    st.markdown('<div class="section-title">채널별 일간 매출 흐름</div>', unsafe_allow_html=True)
    st.plotly_chart(style_figure(trend_fig, 380), use_container_width=True)

    account_summary = frame.groupby(["channel", "account_name"], as_index=False).agg(
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        orders=("orders", "sum"),
        source_rows=("source_rows", "sum"),
        reversal_rows=("reversal_rows", "sum"),
        quantity=("quantity", "sum"),
    )
    account_summary["margin"] = np.where(
        account_summary["sales"] == 0, 0, account_summary["profit"] / account_summary["sales"] * 100
    )
    account_summary["bubble_size"] = account_summary["orders"].clip(lower=0)

    channel_sales = frame.groupby("channel", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
    leading_channel = channel_sales.iloc[0]
    leading_product = (
        frame.loc[frame["channel"] == leading_channel["channel"]]
        .groupby("product_name", as_index=False)["quantity"]
        .sum()
        .sort_values("quantity", ascending=False)
        .iloc[0]
    )
    st.markdown(
        f'<div class="insight-box">선택 기간 매출 1위 채널은 <b>{leading_channel["channel"]}</b>로 '
        f'<b>{won(leading_channel["sales"])}</b>을 기록했습니다. 이 채널에서 판매수량이 가장 많은 제품은 '
        f'<b>{leading_product["product_name"]}</b> ({leading_product["quantity"]:,.0f}개)입니다.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="section-title">매출처 매출 TOP 15</div>', unsafe_allow_html=True)
        top_accounts = account_summary.nlargest(15, "sales").sort_values("sales")
        rank_fig = px.bar(
            top_accounts,
            x="sales",
            y="account_name",
            color="channel",
            orientation="h",
            color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
            labels={"sales": "매출", "account_name": "", "channel": "채널"},
        )
        st.plotly_chart(style_figure(rank_fig, 430), use_container_width=True)

    with right:
        st.markdown('<div class="section-title">매출 규모 · 매출이익률 포지션</div>', unsafe_allow_html=True)
        scatter_fig = px.scatter(
            account_summary,
            x="sales",
            y="margin",
            size="bubble_size",
            color="channel",
            hover_name="account_name",
            hover_data={
                "source_rows": ":,.0f",
                "reversal_rows": ":,.0f",
                "orders": ":,.0f",
                "bubble_size": False,
            },
            color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
            labels={
                "sales": "매출",
                "margin": "매출이익률(%)",
                "bubble_size": "주문건수",
                "orders": "최종 주문건수",
                "source_rows": "원장 행 수",
                "reversal_rows": "취소·반품 행 수",
                "channel": "채널",
            },
            size_max=42,
        )
        st.plotly_chart(style_figure(scatter_fig, 430), use_container_width=True)

    st.markdown('<div class="section-title">채널별 판매수량 TOP 제품</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">각 채널에서 실제로 어떤 제품이 많이 움직였는지 판매수량 기준으로 비교합니다.</div>', unsafe_allow_html=True)
    channel_product = frame.groupby(["channel", "product_name"], as_index=False)["quantity"].sum()
    channel_product = (
        channel_product.sort_values(["channel", "quantity"], ascending=[True, False])
        .groupby("channel", as_index=False, group_keys=False)
        .head(5)
    )
    facet_rows = max(1, int(np.ceil(channel_count / 2)))
    channel_product_fig = px.bar(
        channel_product,
        x="quantity",
        y="product_name",
        color="channel",
        facet_col="channel",
        facet_col_wrap=2,
        orientation="h",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"quantity": "판매수량", "product_name": "", "channel": "채널"},
    )
    channel_product_fig.update_yaxes(matches=None, showticklabels=True)
    channel_product_fig.update_xaxes(matches=None)
    channel_product_fig.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
    st.plotly_chart(style_figure(channel_product_fig, 270 * facet_rows), use_container_width=True)

    st.markdown('<div class="section-title">채널별 MC 대분류 매출 비중</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">채널마다 어떤 제품군이 매출을 주도하는지 100% 구성비로 비교합니다.</div>', unsafe_allow_html=True)
    channel_category = frame.groupby(["channel", "category_large"], as_index=False)["sales"].sum()
    category_fig = px.bar(
        channel_category,
        x="channel",
        y="sales",
        color="category_large",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        labels={"channel": "채널", "sales": "매출 비중(%)", "category_large": "MC 대분류"},
    )
    category_fig.update_layout(barmode="stack", barnorm="percent")
    st.plotly_chart(style_figure(category_fig, 380), use_container_width=True)


def render_product_overview(frame: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
    st.markdown('<div class="brand">Product Sales Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="brand-sub">{start_date:%Y.%m.%d} — {end_date:%Y.%m.%d} · 제품과 카테고리의 매출 기여도를 분석합니다.</div>',
        unsafe_allow_html=True,
    )

    product_source = frame.copy()
    product_source["weighted_unit_amount"] = product_source["unit_price"] * product_source["quantity"]
    product_summary = product_source.groupby("product_name", as_index=False).agg(
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        quantity=("quantity", "sum"),
        orders=("orders", "sum"),
        weighted_unit_amount=("weighted_unit_amount", "sum"),
    )
    product_summary["margin"] = np.where(
        product_summary["sales"] == 0, 0, product_summary["profit"] / product_summary["sales"] * 100
    )
    product_summary["average_unit_price"] = np.where(
        product_summary["quantity"] == 0,
        0,
        product_summary["weighted_unit_amount"] / product_summary["quantity"],
    )
    product_summary["bubble_size"] = product_summary["quantity"].clip(lower=0)

    total_sales = product_summary["sales"].sum()
    total_profit = product_summary["profit"].sum()
    product_cols = st.columns(5)
    product_cols[0].metric("판매 제품", f"{product_summary['product_name'].nunique():,}개")
    product_cols[1].metric("총 매출", won(total_sales))
    product_cols[2].metric("매출이익", won(total_profit))
    product_cols[3].metric("판매 수량", f"{product_summary['quantity'].sum():,.0f}")
    product_cols[4].metric("평균 물품단가", won(weighted_unit_price(frame)))

    leading_product = product_summary.nlargest(1, "sales").iloc[0]
    large_category_sales = frame.groupby("category_large", as_index=False)["sales"].sum().nlargest(1, "sales").iloc[0]
    st.markdown(
        f'<div class="insight-box">매출 기여도가 가장 높은 제품은 <b>{leading_product["product_name"]}</b>로 '
        f'<b>{won(leading_product["sales"])}</b>을 기록했습니다. MC 대분류에서는 '
        f'<b>{large_category_sales["category_large"]}</b>가 전체 매출을 가장 크게 이끌고 있습니다.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1])
    with left:
        st.markdown('<div class="section-title">제품 매출 TOP 10</div>', unsafe_allow_html=True)
        top_products = product_summary.nlargest(10, "sales").sort_values("sales")
        product_fig = px.bar(
            top_products,
            x="sales",
            y="product_name",
            orientation="h",
            color="sales",
            color_continuous_scale=[[0, "#DDD6FE"], [1, COLORS["primary"]]],
            labels={"sales": "매출", "product_name": ""},
        )
        product_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(product_fig, 420), use_container_width=True)

    with right:
        st.markdown('<div class="section-title">카테고리 매출 구성</div>', unsafe_allow_html=True)
        category_sales = frame.groupby(
            ["category_large", "category_middle", "category_small", "category_detail"],
            as_index=False,
        )["sales"].sum()
        sunburst_fig = px.sunburst(
            category_sales,
            path=["category_large", "category_middle", "category_small", "category_detail"],
            values="sales",
            color="sales",
            color_continuous_scale=[[0, "#FCE7F3"], [1, COLORS["secondary"]]],
            labels={"sales": "매출"},
        )
        sunburst_fig.update_traces(
            textinfo="label+percent parent",
            hovertemplate="<b>%{label}</b><br>매출: ₩%{value:,.0f}<br>상위 분류 내 비중: %{percentParent:.1%}<extra></extra>",
        )
        sunburst_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(sunburst_fig, 420), use_container_width=True)

    st.markdown('<div class="section-title">제품별 매출 · 매출이익률 포지션</div>', unsafe_allow_html=True)
    product_scatter = px.scatter(
        product_summary,
        x="sales",
        y="margin",
        size="bubble_size",
        color="average_unit_price",
        hover_name="product_name",
        color_continuous_scale=[
            [0.0, "#2563EB"],
            [0.5, "#7C3AED"],
            [1.0, "#EC4899"],
        ],
        labels={"sales": "매출", "margin": "매출이익률(%)", "bubble_size": "판매수량", "average_unit_price": "평균 물품단가"},
        size_max=55,
    )
    product_scatter.update_traces(marker=dict(opacity=.9, line=dict(color="#FFFFFF", width=1.5)))
    st.plotly_chart(style_figure(product_scatter, 390), use_container_width=True)

    product_detail = product_summary.rename(
        columns={
            "product_name": "제품명", "sales": "매출", "profit": "매출이익",
            "margin": "매출이익률", "quantity": "판매수량", "orders": "주문건수",
            "average_unit_price": "평균물품단가",
        }
    )[["제품명", "매출", "매출이익", "매출이익률", "판매수량", "주문건수", "평균물품단가"]]
    st.markdown('<div class="section-title">제품 상세 실적</div>', unsafe_allow_html=True)
    st.dataframe(
        product_detail.sort_values("매출", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "매출": st.column_config.NumberColumn(format="₩ %,.0f"),
            "매출이익": st.column_config.NumberColumn(format="₩ %,.0f"),
            "매출이익률": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=50),
            "판매수량": st.column_config.NumberColumn(format="%,.0f"),
            "주문건수": st.column_config.NumberColumn(format="%,d"),
            "평균물품단가": st.column_config.NumberColumn(format="₩ %,.0f"),
        },
    )


data_dir = Path(__file__).resolve().parent / "data"
csv_paths = sorted(data_dir.glob("*.csv"))
data_version = tuple(
    (path.name, path.stat().st_mtime_ns, path.stat().st_size)
    for path in csv_paths
)
try:
    data = load_data_from_csv(data_version, DATA_TRANSFORM_VERSION)
except Exception as exc:
    st.error(f"CSV 데이터를 불러오지 못했습니다: {exc}")
    st.stop()

if data.empty:
    st.warning("CSV 파일에 표시할 데이터가 없습니다.")
    st.stop()

data["date"] = pd.to_datetime(data["date"])
data["profit_margin"] = np.where(data["sales"] == 0, 0, data["profit"] / data["sales"] * 100)
data_min_date = data["date"].min().date()
data_max_date = data["date"].max().date()


with st.sidebar:
    st.markdown('<div class="brand">데르뜨</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Dessert Sales Intelligence</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="nav-title">ANALYTICS MENU</div>', unsafe_allow_html=True)
    nav_labels = {
        "채널 Sales Overview": "01  채널 Sales Overview",
        "채널 상세 Sales 분석": "02  채널 상세 Sales 분석",
        "제품별 Sales Overview": "03  제품별 Sales Overview",
    }
    selected_page = st.radio(
        "분석 메뉴",
        list(nav_labels),
        format_func=nav_labels.get,
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("#### 조회 조건")
    default_end_date = data_max_date
    default_start_date = default_end_date.replace(day=1)
    selected_dates = st.date_input(
        "조회 기간",
        value=(default_start_date, default_end_date),
        min_value=data_min_date,
        max_value=data_max_date,
    )
    if selected_page == "채널 Sales Overview":
        frequency = st.segmented_control("집계 단위", ["일간", "주간", "월간"], default="일간")
    else:
        frequency = "주간"

if len(selected_dates) != 2:
    st.info("조회 시작일과 종료일을 선택해 주세요.")
    st.stop()

selected_start_date, selected_end_date = selected_dates
if selected_start_date > selected_end_date:
    st.error("조회 시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()
if (selected_end_date - selected_start_date).days > 365:
    st.error("조회 기간은 최대 1년까지만 선택할 수 있습니다.")
    st.stop()

with st.sidebar:
    st.markdown("---")
    st.markdown("#### 상세 필터")

    min_date = data["date"].min().date()
    max_date = data["date"].max().date()
    channel_options = sorted(data["channel"].dropna().unique())
    selected_channels = st.multiselect("채널", channel_options, default=channel_options)

    # 채널 선택에 따라 매출처 목록이 자동으로 달라지는 종속 필터입니다.
    account_options = sorted(
        data.loc[data["channel"].isin(selected_channels), "account_name"].dropna().unique()
    )
    selected_accounts = st.multiselect("매출처명", account_options, default=account_options)

    category_base = data[
        data["channel"].isin(selected_channels) & data["account_name"].isin(selected_accounts)
    ]
    if selected_page == "채널 Sales Overview":
        large_options = sorted(category_base["category_large"].dropna().unique())
        selected_large = st.multiselect("대분류", large_options, default=large_options)

        middle_options = sorted(
            category_base.loc[category_base["category_large"].isin(selected_large), "category_middle"].dropna().unique()
        )
        selected_middle = st.multiselect("중분류", middle_options, default=middle_options)

        small_options = sorted(
            category_base.loc[
                category_base["category_large"].isin(selected_large)
                & category_base["category_middle"].isin(selected_middle),
                "category_small",
            ].dropna().unique()
        )
        selected_small = st.multiselect("소분류", small_options, default=small_options)

        detail_options = sorted(
            category_base.loc[
                category_base["category_large"].isin(selected_large)
                & category_base["category_middle"].isin(selected_middle)
                & category_base["category_small"].isin(selected_small),
                "category_detail",
            ].dropna().unique()
        )
        selected_detail = st.multiselect("세분류", detail_options, default=detail_options)
    else:
        selected_large = sorted(category_base["category_large"].dropna().unique())
        selected_middle = sorted(category_base["category_middle"].dropna().unique())
        selected_small = sorted(category_base["category_small"].dropna().unique())
        selected_detail = sorted(category_base["category_detail"].dropna().unique())
        frequency = "주간"

    st.markdown("---")
    st.markdown('<span class="status-pill">● CSV 데이터</span>', unsafe_allow_html=True)
    st.caption(f"파일 {len(csv_paths):,}개")
    st.caption(f"최종 데이터: {max_date:%Y.%m.%d}")


start_date, end_date = map(pd.Timestamp, selected_dates)
filtered = data[
    data["date"].between(start_date, end_date)
    & data["channel"].isin(selected_channels)
    & data["account_name"].isin(selected_accounts)
    & data["category_large"].isin(selected_large)
    & data["category_middle"].isin(selected_middle)
    & data["category_small"].isin(selected_small)
    & data["category_detail"].isin(selected_detail)
].copy()

if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

comparison_labels = {
    "일간": "전일 대비",
    "주간": "전주 대비",
    "월간": "전월 대비",
}
comparison_label = comparison_labels.get(frequency or "주간", "전주 대비")
previous_start, previous_end = comparison_period(start_date, end_date, frequency or "주간")
previous = data[
    data["date"].between(previous_start, previous_end)
    & data["channel"].isin(selected_channels)
    & data["account_name"].isin(selected_accounts)
    & data["category_large"].isin(selected_large)
    & data["category_middle"].isin(selected_middle)
    & data["category_small"].isin(selected_small)
    & data["category_detail"].isin(selected_detail)
]

if selected_page == "채널 상세 Sales 분석":
    render_channel_detail(filtered, start_date, end_date)
    st.stop()

if selected_page == "제품별 Sales Overview":
    render_product_overview(filtered, start_date, end_date)
    st.stop()

st.markdown('<div class="brand">Channel Sales Overview</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="brand-sub">{start_date:%Y.%m.%d} — {end_date:%Y.%m.%d} · 데르뜨 매출 및 매출이익 현황</div>',
    unsafe_allow_html=True,
)

sales = filtered["sales"].sum()
profit = filtered["profit"].sum()
orders = filtered["orders"].sum()
source_rows = int(filtered["source_rows"].sum())
reversal_rows = int(filtered["reversal_rows"].sum())
average_unit_price = weighted_unit_price(filtered)
margin = profit / sales * 100 if sales else 0
prev_sales = previous["sales"].sum()
prev_profit = previous["profit"].sum()
prev_orders = previous["orders"].sum()
prev_average_unit_price = weighted_unit_price(previous)
prev_margin = previous["profit"].sum() / prev_sales * 100 if prev_sales else 0

kpi_cols = st.columns(5)
kpi_cols[0].metric("총 매출", won(sales), f"{percent_change(sales, prev_sales):+.1f}% · {comparison_label}")
kpi_cols[1].metric(
    "매출이익",
    won(profit),
    f"{percent_change(profit, prev_profit):+.1f}% · {comparison_label}",
    help="매출이익 = 공급가 − 매출원가\n\n부가세와 합계 금액은 매출이익 산출에서 제외합니다.",
)
kpi_cols[2].metric(
    "매출이익률",
    f"{margin:.1f}%",
    f"{margin - prev_margin:+.1f}%p · {comparison_label}",
    help="매출이익률 = 매출이익 합계 ÷ 공급가 합계 × 100\n\n행별 이익률의 단순 평균이 아닙니다.",
)
kpi_cols[3].metric("주문 건수", f"{orders:,.0f}건", f"{percent_change(orders, prev_orders):+.1f}% · {comparison_label}")
kpi_cols[4].metric(
    "평균 물품단가",
    won(average_unit_price),
    f"{percent_change(average_unit_price, prev_average_unit_price):+.1f}% · {comparison_label}",
    help=f"단가를 수량으로 가중평균한 값 · 비교 기간: {previous_start:%Y.%m.%d}~{previous_end:%Y.%m.%d}",
)
st.caption(
    f"{comparison_label} 기준 · 현재 {start_date:%Y.%m.%d}-{end_date:%Y.%m.%d} / "
    f"비교 {previous_start:%Y.%m.%d}-{previous_end:%Y.%m.%d}"
)
st.caption(
    f"주문건수 검산 · 원장 {source_rows:,}행 − 차감 대상 {reversal_rows:,}행 × 2 "
    f"= {orders:,.0f}건 (샘플 제품 제외)"# (매출반품·매출취소·취소 후 이관은 각 −1건)"
)

st.markdown('<div class="section-title">매출 · 매출이익 추이</div>', unsafe_allow_html=True)
st.markdown('<div class="section-sub">선택 기간을 주간 또는 월간 단위로 비교합니다.</div>', unsafe_allow_html=True)

trend = aggregate_period(filtered, frequency or "주간")
trend_fig = go.Figure()
trend_fig.add_trace(go.Bar(x=trend["date"], y=trend["sales"], name="매출", marker_color=COLORS["primary"], opacity=.88))
trend_fig.add_trace(go.Scatter(x=trend["date"], y=trend["profit"], name="매출이익", mode="lines+markers", line=dict(color=COLORS["secondary"], width=3), yaxis="y2"))
trend_fig.update_layout(
    yaxis=dict(title="매출", tickformat="~s"),
    yaxis2=dict(title="매출이익", tickformat="~s", overlaying="y", side="right", showgrid=False),
    hovermode="x unified",
)
st.plotly_chart(style_figure(trend_fig, 390), use_container_width=True)

left, right = st.columns([1.45, 1])
with left:
    st.markdown('<div class="section-title">채널별 성과</div>', unsafe_allow_html=True)
    channel_daily = filtered.groupby(["date", "channel"], as_index=False)["sales"].sum()
    channel_fig = px.area(
        channel_daily,
        x="date",
        y="sales",
        color="channel",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"date": "일자", "sales": "매출", "channel": "채널"},
    )
    channel_fig.update_traces(line=dict(width=2))
    st.plotly_chart(style_figure(channel_fig), use_container_width=True)

with right:
    st.markdown('<div class="section-title">채널 매출 구성</div>', unsafe_allow_html=True)
    channel_mix = filtered.groupby("channel", as_index=False)["sales"].sum()
    mix_fig = px.pie(
        channel_mix,
        names="channel",
        values="sales",
        hole=.62,
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
    )
    mix_fig.update_traces(textposition="outside", textinfo="label+percent", sort=False)
    mix_fig.add_annotation(text="채널<br>비중", x=.5, y=.5, showarrow=False, font=dict(size=15, color=COLORS["muted"]))
    st.plotly_chart(style_figure(mix_fig), use_container_width=True)

left, right = st.columns(2)
with left:
    st.markdown('<div class="section-title">매출처별 매출 TOP 5</div>', unsafe_allow_html=True)
    account_sales = filtered.groupby("account_name", as_index=False).agg(sales=("sales", "sum"), profit=("profit", "sum")).nlargest(5, "sales").sort_values("sales")
    account_fig = px.bar(
        account_sales,
        x="sales",
        y="account_name",
        orientation="h",
        color="sales",
        color_continuous_scale=[[0, "#DDD6FE"], [1, COLORS["primary"]]],
        labels={"sales": "매출", "account_name": ""},
    )
    account_fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style_figure(account_fig), use_container_width=True)

with right:
    st.markdown('<div class="section-title">채널 매출이익률 비교</div>', unsafe_allow_html=True)
    profitability = filtered.groupby("channel", as_index=False).agg(
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        orders=("orders", "sum"),
        source_rows=("source_rows", "sum"),
        reversal_rows=("reversal_rows", "sum"),
    )
    profitability["margin"] = profitability["profit"] / profitability["sales"] * 100
    profitability["bubble_size"] = profitability["orders"].clip(lower=0)
    bubble_fig = px.scatter(
        profitability,
        x="sales",
        y="margin",
        size="bubble_size",
        color="channel",
        text="channel",
        hover_data={
            "source_rows": ":,.0f",
            "reversal_rows": ":,.0f",
            "orders": ":,.0f",
            "bubble_size": False,
        },
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={
            "sales": "매출 규모",
            "margin": "매출이익률(%)",
            "orders": "최종 주문건수",
            "source_rows": "원장 행 수",
            "reversal_rows": "취소·반품 행 수",
        },
        size_max=48,
    )
    bubble_fig.update_traces(textposition="top center")
    st.plotly_chart(style_figure(bubble_fig), use_container_width=True)
    st.caption("버블에 마우스를 올리면 원장 행 수, 취소·반품 행 수, 최종 주문건수를 확인할 수 있습니다.")

st.markdown('<div class="section-title">매출처 상세 실적</div>', unsafe_allow_html=True)
st.markdown('<div class="section-sub">채널별 매출처의 핵심 지표를 내려받거나 운영 리포트에 활용할 수 있습니다.</div>', unsafe_allow_html=True)

detail_source = filtered.copy()
detail_source["weighted_unit_amount"] = detail_source["unit_price"] * detail_source["quantity"]
detail = detail_source.groupby(["channel", "account_name"], as_index=False).agg(
    매출=("sales", "sum"),
    매출이익=("profit", "sum"),
    주문건수=("orders", "sum"),
    판매수량=("quantity", "sum"),
    가중단가합계=("weighted_unit_amount", "sum"),
)
detail["매출이익률"] = detail["매출이익"] / detail["매출"] * 100
detail["평균물품단가"] = np.where(
    detail["판매수량"] == 0,
    0,
    detail["가중단가합계"] / detail["판매수량"],
)
detail = detail.rename(columns={"channel": "채널", "account_name": "매출처명"})
detail = detail.sort_values(["채널", "매출"], ascending=[True, False])
detail = detail[["채널", "매출처명", "매출", "매출이익", "주문건수", "매출이익률", "평균물품단가"]]

st.dataframe(
    detail,
    use_container_width=True,
    hide_index=True,
    column_config={
        "매출": st.column_config.NumberColumn(format="₩ %,.0f"),
        "매출이익": st.column_config.NumberColumn(format="₩ %,.0f"),
        "매출이익률": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=50),
        "평균물품단가": st.column_config.NumberColumn(format="₩ %,.0f"),
        "주문건수": st.column_config.NumberColumn(format="%,d"),
    },
)

csv = detail.to_csv(index=False).encode("utf-8-sig")
st.download_button("매출처 실적 CSV 다운로드", csv, f"dertte_account_sales_{date.today():%Y%m%d}.csv", "text/csv")
st.caption("© 데르뜨 · 매출이익과 매출이익률은 DB 조회 결과의 매출이익 값을 기준으로 계산합니다.")
