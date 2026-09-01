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
    page_title="Brand Sales Dashboard",
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
DATA_TRANSFORM_VERSION = 9


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
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] > div {
            color: #211A2F;
            font-size: clamp(1.05rem, 1.55vw, 1.65rem) !important;
            line-height: 1.25 !important;
            white-space: normal !important;
            overflow-wrap: anywhere;
            word-break: keep-all;
        }
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
    }
    frame = frame.copy()
    frame.columns = (
        frame.columns.astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )
    # 화면의 모든 판매수량은 EA 환산 수량을 우선 사용합니다.
    # 이전 형식의 CSV도 열 수 있도록 해당 컬럼이 없을 때만 기존 수량을 사용합니다.
    ea_quantity_column = next(
        (column for column in frame.columns if column.upper() == "SALES_QTY_EA"),
        None,
    )
    rename_columns = {
        source: target
        for source, target in korean_column_map.items()
        if source in frame.columns and target not in frame.columns
    }
    frame = frame.rename(columns=rename_columns)
    if ea_quantity_column is not None:
        frame["quantity"] = frame[ea_quantity_column]

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

    metric_columns = ["sales", "quantity"]
    prepared = frame[dimension_columns + metric_columns].copy()
    aggregated = prepared.groupby(dimension_columns, as_index=False, dropna=False)[metric_columns].sum()
    aggregated["unit_price"] = np.where(
        aggregated["quantity"] == 0,
        0,
        aggregated["sales"] / aggregated["quantity"],
    )
    return aggregated.sort_values("date")


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
                    "orders": orders,
                    "source_rows": orders,
                    "reversal_rows": 0,
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def load_data_from_csv(
    data_version: tuple[tuple[str, int, int], ...],
    data_folder: str,
    transform_version: int = 0,
) -> pd.DataFrame:
    """data 폴더의 모든 CSV를 병합해 대시보드 집계 구조로 변환합니다."""
    del data_version, transform_version  # 캐시 무효화를 위한 함수 인자
    data_dir = Path(__file__).resolve().parent / data_folder
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
        .agg(sales=("sales", "sum"), quantity=("quantity", "sum"))
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
    channel_sales = frame.groupby("channel", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
    leading_channel = channel_sales.iloc[0]
    average_accounts_per_channel = account_count / channel_count if channel_count else 0
    summary_cols = st.columns(4)
    summary_cols[0].metric("분석 채널", f"{channel_count:,}개")
    summary_cols[1].metric("활성 매출처", f"{account_count:,}개")
    summary_cols[2].metric(
        "매출 1위 채널",
        str(leading_channel["channel"]),
        help=f"선택 기간 매출액: {won(leading_channel['sales'])}",
    )
    summary_cols[3].metric("채널당 평균 매출처", f"{average_accounts_per_channel:,.1f}개")

    # 매출이 없는 날짜도 0으로 표시하기 위해 선택 기간의 날짜×채널 조합을 완성합니다.
    full_dates = pd.date_range(start=start_date.normalize(), end=end_date.normalize(), freq="D")
    active_channels = sorted(frame["channel"].dropna().unique())
    full_date_channel_index = pd.MultiIndex.from_product(
        [full_dates, active_channels],
        names=["date", "channel"],
    )
    daily_channel = (
        frame.groupby(["date", "channel"])["sales"]
        .sum()
        .reindex(full_date_channel_index, fill_value=0)
        .rename("sales")
        .reset_index()
    )
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
    with st.expander("일간 채널 집계 데이터 보기"):
        daily_channel_table = (
            daily_channel.pivot(index="date", columns="channel", values="sales")
            .fillna(0)
            .reset_index()
        )
        daily_channel_table["date"] = daily_channel_table["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            daily_channel_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                column: st.column_config.NumberColumn(format="₩ %,.0f")
                for column in active_channels
            },
        )
        daily_channel_csv = daily_channel_table.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "일간 채널 집계 CSV 다운로드",
            daily_channel_csv,
            f"dertte_daily_channel_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv",
            "text/csv",
        )

    account_summary = frame.groupby(["channel", "account_name"], as_index=False).agg(
        sales=("sales", "sum"),
        quantity=("quantity", "sum"),
    )
    account_summary["bubble_size"] = account_summary["quantity"].clip(lower=0)

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
        rank_fig.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(style_figure(rank_fig, 430), use_container_width=True)

    with right:
        st.markdown('<div class="section-title">매출처별 매출 · 판매수량 포지션</div>', unsafe_allow_html=True)
        scatter_fig = px.scatter(
            account_summary,
            x="sales",
            y="quantity",
            size="bubble_size",
            color="channel",
            hover_name="account_name",
            hover_data={"bubble_size": False},
            color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
            labels={
                "sales": "매출",
                "quantity": "판매수량",
                "bubble_size": "판매수량",
                "channel": "채널",
            },
            size_max=42,
        )
        st.plotly_chart(style_figure(scatter_fig, 430), use_container_width=True)

    st.markdown('<div class="section-title">요일별 채널 평균 일매출</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">매출이 없는 날짜도 0원으로 포함해 채널별 요일 판매 패턴을 비교합니다.</div>', unsafe_allow_html=True)
    weekday_order = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_map = dict(enumerate(weekday_order))
    weekday_channel = daily_channel.copy()
    weekday_channel["weekday"] = weekday_channel["date"].dt.dayofweek.map(weekday_map)
    weekday_channel = weekday_channel.groupby(["weekday", "channel"], as_index=False)["sales"].mean()
    weekday_channel["weekday"] = pd.Categorical(
        weekday_channel["weekday"],
        categories=weekday_order,
        ordered=True,
    )
    weekday_channel = weekday_channel.sort_values("weekday")
    weekday_fig = px.bar(
        weekday_channel,
        x="weekday",
        y="sales",
        color="channel",
        barmode="group",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"weekday": "요일", "sales": "평균 일매출", "channel": "채널"},
    )
    weekday_fig.update_xaxes(categoryorder="array", categoryarray=weekday_order)
    st.plotly_chart(style_figure(weekday_fig, 400), use_container_width=True)

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

    product_summary = frame.groupby("product_name", as_index=False).agg(
        sales=("sales", "sum"),
        quantity=("quantity", "sum"),
    )
    product_summary["average_unit_price"] = np.where(
        product_summary["quantity"] == 0,
        0,
        product_summary["sales"] / product_summary["quantity"],
    )
    product_summary["bubble_size"] = product_summary["quantity"].clip(lower=0)

    leading_product = product_summary.nlargest(1, "sales").iloc[0]
    leading_quantity_product = product_summary.nlargest(1, "quantity").iloc[0]
    active_large_categories = frame["category_large"].nunique()
    product_cols = st.columns(4)
    product_cols[0].metric("판매 제품", f"{product_summary['product_name'].nunique():,}개")
    product_cols[1].metric("활성 대분류", f"{active_large_categories:,}개")
    product_cols[2].metric(
        "매출 1위 제품",
        str(leading_product["product_name"]),
        help=f"선택 기간 매출액: {won(leading_product['sales'])}",
    )
    product_cols[3].metric(
        "판매수량 1위 제품",
        str(leading_quantity_product["product_name"]),
        help=f"선택 기간 판매수량: {leading_quantity_product['quantity']:,.0f}개",
    )

    large_category_sales = frame.groupby("category_large", as_index=False)["sales"].sum().nlargest(1, "sales").iloc[0]
    st.markdown(
        f'<div class="insight-box">매출 기여도가 가장 높은 제품은 <b>{leading_product["product_name"]}</b>로 '
        f'<b>{won(leading_product["sales"])}</b>을 기록했습니다. MC 대분류에서는 '
        f'<b>{large_category_sales["category_large"]}</b>가 전체 매출을 가장 크게 이끌고 있습니다.</div>',
        unsafe_allow_html=True,
    )
    total_product_quantity = product_summary["quantity"].sum()
    leading_quantity_share = (
        leading_quantity_product["quantity"] / total_product_quantity * 100
        if total_product_quantity != 0
        else 0
    )
    st.markdown(
        f'<div class="insight-box">판매수량이 가장 높은 제품은 <b>{leading_quantity_product["product_name"]}</b>로 '
        f'<b>{leading_quantity_product["quantity"]:,.0f} EA</b>가 판매되었습니다. '
        f'선택 기간 전체 판매수량의 <b>{leading_quantity_share:.1f}%</b>를 차지합니다.</div>',
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

    st.markdown('<div class="section-title">제품별 매출 · 판매수량 포지션</div>', unsafe_allow_html=True)
    product_scatter = px.scatter(
        product_summary,
        x="sales",
        y="quantity",
        size="bubble_size",
        color="average_unit_price",
        hover_name="product_name",
        color_continuous_scale=[
            [0.0, "#2563EB"],
            [0.5, "#7C3AED"],
            [1.0, "#EC4899"],
        ],
        labels={"sales": "매출", "quantity": "판매수량(EA)", "bubble_size": "판매수량(EA)", "average_unit_price": "평균 EA단가"},
        size_max=55,
    )
    product_scatter.update_traces(marker=dict(opacity=.9, line=dict(color="#FFFFFF", width=1.5)))
    st.plotly_chart(style_figure(product_scatter, 390), use_container_width=True)

    product_detail = product_summary.rename(
        columns={
            "product_name": "제품명", "sales": "매출", "quantity": "판매수량",
            "average_unit_price": "평균 EA단가",
        }
    )[["제품명", "매출", "판매수량", "평균 EA단가"]]
    st.markdown('<div class="section-title">제품 상세 실적</div>', unsafe_allow_html=True)
    st.dataframe(
        product_detail.sort_values("매출", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "매출": st.column_config.NumberColumn(format="₩ %,.0f"),
            "판매수량": st.column_config.NumberColumn(format="%,.0f"),
            "평균 EA단가": st.column_config.NumberColumn(format="₩ %,.0f"),
        },
    )


with st.sidebar:
    st.markdown('<div class="brand">Brand Sales</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Sales Intelligence Platform</div>', unsafe_allow_html=True)
    selected_brand = st.segmented_control("브랜드", ["데르뜨", "밀도"], default="데르뜨")

if selected_brand == "밀도":
    with st.sidebar:
        st.markdown("---")
        st.markdown('<span class="status-pill">● 밀도 데이터 준비 중</span>', unsafe_allow_html=True)

    st.markdown('<div class="brand">밀도 Store Sales Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-sub">매장 운영 데이터를 기반으로 한 밀도 전용 분석 화면을 준비하고 있습니다.</div>',
        unsafe_allow_html=True,
    )
    st.info("밀도 데이터와 컬럼 구조가 확정되면 이 화면에 매장·제품·시간대 분석을 연결합니다.")

    placeholder_cols = st.columns(3)
    placeholder_cols[0].metric("매장 Sales Overview", "준비 중")
    placeholder_cols[1].metric("매장 상세 분석", "준비 중")
    placeholder_cols[2].metric("제품·메뉴 분석", "준비 중")

    st.markdown('<div class="section-title">밀도 대시보드 구성 예정</div>', unsafe_allow_html=True)
    st.markdown(
        """
        - 매장별 매출 및 판매수량 비교
        - 일자·요일·시간대별 매출 흐름
        - 제품·메뉴별 판매 순위와 구성비
        - 매장별 제품 판매 현황
        - 데이터 구조에 맞춘 밀도 전용 필터
        """
    )
    st.caption("데이터 위치: data/mildo/")
    st.stop()


data_dir = Path(__file__).resolve().parent / "data" / "dertte"
csv_paths = sorted(data_dir.glob("*.csv"))
data_version = tuple(
    (path.name, path.stat().st_mtime_ns, path.stat().st_size)
    for path in csv_paths
)
try:
    data = load_data_from_csv(data_version, "data/dertte", DATA_TRANSFORM_VERSION)
except Exception as exc:
    st.error(f"CSV 데이터를 불러오지 못했습니다: {exc}")
    st.stop()

if data.empty:
    st.warning("CSV 파일에 표시할 데이터가 없습니다.")
    st.stop()

data["date"] = pd.to_datetime(data["date"])
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
    elif selected_page == "제품별 Sales Overview":
        large_options = sorted(category_base["category_large"].dropna().unique())
        selected_large = st.multiselect("MC 대분류", large_options, default=large_options)
        selected_category_base = category_base[
            category_base["category_large"].isin(selected_large)
        ]
        selected_middle = sorted(selected_category_base["category_middle"].dropna().unique())
        selected_small = sorted(selected_category_base["category_small"].dropna().unique())
        selected_detail = sorted(selected_category_base["category_detail"].dropna().unique())
        frequency = "주간"
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
    f'<div class="brand-sub">{start_date:%Y.%m.%d} — {end_date:%Y.%m.%d} · 데르뜨 채널별 매출 및 판매 현황</div>',
    unsafe_allow_html=True,
)

sales = filtered["sales"].sum()
quantity = filtered["quantity"].sum()
prev_sales = previous["sales"].sum()
prev_quantity = previous["quantity"].sum()

kpi_cols = st.columns(4)
kpi_cols[0].metric("총 매출", won(sales), f"{percent_change(sales, prev_sales):+.1f}% · {comparison_label}")
kpi_cols[1].metric("판매 수량", f"{quantity:,.0f}개", f"{percent_change(quantity, prev_quantity):+.1f}% · {comparison_label}")
kpi_cols[2].metric("활성 채널", f"{filtered['channel'].nunique():,}개")
kpi_cols[3].metric("판매 제품", f"{filtered['product_name'].nunique():,}개")
st.caption(
    f"{comparison_label} 기준 · 현재 {start_date:%Y.%m.%d}-{end_date:%Y.%m.%d} / "
    f"비교 {previous_start:%Y.%m.%d}-{previous_end:%Y.%m.%d}"
)

st.markdown('<div class="section-title">기간별 판매 추이</div>', unsafe_allow_html=True)
trend_metric_label = st.segmented_control("추이 기준", ["매출액", "판매수량"], default="매출액")
trend = aggregate_period(filtered, frequency or "일간")
trend_column = "sales" if trend_metric_label == "매출액" else "quantity"
trend_labels = {"date": "일자", "sales": "매출액", "quantity": "판매수량"}
trend_fig = px.bar(
    trend,
    x="date",
    y=trend_column,
    color_discrete_sequence=[COLORS["primary"]],
    labels=trend_labels,
)
trend_fig.update_traces(marker_line_width=0, opacity=.9)
trend_fig.update_layout(hovermode="x unified")
st.plotly_chart(style_figure(trend_fig, 390), use_container_width=True)

channel_summary = filtered.groupby("channel", as_index=False).agg(
    sales=("sales", "sum"),
    quantity=("quantity", "sum"),
)
left, right = st.columns(2)
with left:
    st.markdown('<div class="section-title">채널별 매출 집계</div>', unsafe_allow_html=True)
    channel_sales_fig = px.bar(
        channel_summary.sort_values("sales"), x="sales", y="channel", orientation="h", color="channel",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"sales": "매출액", "channel": ""},
    )
    channel_sales_fig.update_layout(showlegend=False)
    st.plotly_chart(style_figure(channel_sales_fig, 360), use_container_width=True)
with right:
    st.markdown('<div class="section-title">채널별 판매수량 집계</div>', unsafe_allow_html=True)
    channel_quantity_fig = px.bar(
        channel_summary.sort_values("quantity"), x="quantity", y="channel", orientation="h", color="channel",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"]],
        labels={"quantity": "판매수량", "channel": ""},
    )
    channel_quantity_fig.update_layout(showlegend=False)
    st.plotly_chart(style_figure(channel_quantity_fig, 360), use_container_width=True)

st.markdown('<div class="section-title">채널별 매출액 TOP 10 제품</div>', unsafe_allow_html=True)
channel_product = filtered.groupby(["channel", "product_name"], as_index=False)["sales"].sum()
channel_product = (
    channel_product.sort_values(["channel", "sales"], ascending=[True, False])
    .groupby("channel", group_keys=False)
    .head(10)
)
channel_names = sorted(channel_product["channel"].unique())
channel_tabs = st.tabs(channel_names)
for channel_tab, channel_name in zip(channel_tabs, channel_names):
    with channel_tab:
        channel_top_products = (
            channel_product.loc[channel_product["channel"] == channel_name]
            .sort_values("sales")
        )
        channel_product_fig = px.bar(
            channel_top_products,
            x="sales",
            y="product_name",
            orientation="h",
            color="sales",
            color_continuous_scale=[[0, "#DDD6FE"], [1, COLORS["primary"]]],
            labels={"sales": "매출액", "product_name": ""},
        )
        channel_product_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(channel_product_fig, 430), use_container_width=True)

st.markdown('<div class="section-title">카테고리별 판매 제품 TOP 10</div>', unsafe_allow_html=True)
category_levels = {
    "대분류": "category_large",
    "중분류": "category_middle",
    "소분류": "category_small",
    "세분류": "category_detail",
}
category_level_label = st.segmented_control("카테고리 단계", list(category_levels), default="대분류")
category_column = category_levels[category_level_label]
category_values = sorted(filtered[category_column].dropna().unique())
selected_category_value = st.selectbox(f"MC {category_level_label}", category_values)
category_products = (
    filtered.loc[filtered[category_column] == selected_category_value]
    .groupby("product_name", as_index=False)
    .agg(sales=("sales", "sum"), quantity=("quantity", "sum"))
    .nlargest(10, "quantity")
    .sort_values("quantity")
)
category_product_fig = px.bar(
    category_products, x="quantity", y="product_name", orientation="h", color="sales",
    color_continuous_scale=[[0, "#DDD6FE"], [1, COLORS["primary"]]],
    labels={"quantity": "판매수량", "product_name": "", "sales": "매출액"},
)
st.plotly_chart(style_figure(category_product_fig, 420), use_container_width=True)

st.markdown('<div class="section-title">매출처 상세 실적</div>', unsafe_allow_html=True)
st.markdown('<div class="section-sub">조회 종료일 기준 채널 합계와 매출처별 매출을 피벗 형태로 비교합니다. (단위: 백만원)</div>', unsafe_allow_html=True)

reference_date = end_date.normalize()
current_month_start = reference_date.replace(day=1)
_, previous_month_end = comparison_period(reference_date, reference_date, "월간")
previous_month_start = previous_month_end.replace(day=1)
previous_year_end = reference_date - pd.DateOffset(years=1)
if reference_date.is_month_end:
    previous_year_end = previous_year_end + pd.offsets.MonthEnd(0)
previous_year_start = previous_year_end.replace(day=1)

# 조회 기간과 별개로 비교 기간 전체가 필요하므로 날짜를 제외한 현재 필터만 적용합니다.
detail_history = data[
    data["channel"].isin(selected_channels)
    & data["account_name"].isin(selected_accounts)
    & data["category_large"].isin(selected_large)
    & data["category_middle"].isin(selected_middle)
    & data["category_small"].isin(selected_small)
    & data["category_detail"].isin(selected_detail)
].copy()

metric_specs = {
    "daily_sales": detail_history["date"].eq(reference_date),
    "current_month_sales": detail_history["date"].between(current_month_start, reference_date),
    "previous_month_sales": detail_history["date"].between(previous_month_start, previous_month_end),
    "previous_year_sales": detail_history["date"].between(previous_year_start, previous_year_end),
}
account_metrics = None
for metric_name, metric_mask in metric_specs.items():
    metric_values = (
        detail_history.loc[metric_mask]
        .groupby(["channel", "account_name"])["sales"]
        .sum()
        .rename(metric_name)
    )
    account_metrics = metric_values.to_frame() if account_metrics is None else account_metrics.join(metric_values, how="outer")

account_metrics = account_metrics.fillna(0).reset_index()
value_columns = list(metric_specs)
detail_rows: list[dict] = []

total_values = account_metrics[value_columns].sum()
detail_rows.append({
    "구분": "Total sum",
    "매출처": "",
    **{column: total_values[column] / 1_000_000 for column in value_columns},
    "monthly_plan": "-",
})

channel_order = (
    account_metrics.groupby("channel")["current_month_sales"]
    .sum()
    .sort_values(ascending=False)
    .index
)
for channel_name in channel_order:
    channel_accounts = account_metrics.loc[account_metrics["channel"] == channel_name].copy()
    channel_values = channel_accounts[value_columns].sum()
    detail_rows.append({
        "구분": channel_name,
        "매출처": "SUM",
        **{column: channel_values[column] / 1_000_000 for column in value_columns},
        "monthly_plan": "-",
    })

    ranked_accounts = channel_accounts.sort_values("current_month_sales", ascending=False)
    top_accounts = ranked_accounts.head(10)
    for _, account_row in top_accounts.iterrows():
        detail_rows.append({
            "구분": "",
            "매출처": account_row["account_name"],
            **{column: account_row[column] / 1_000_000 for column in value_columns},
            "monthly_plan": "-",
        })

    remaining_accounts = ranked_accounts.iloc[10:]
    if not remaining_accounts.empty:
        remaining_values = remaining_accounts[value_columns].sum()
        detail_rows.append({
            "구분": "",
            "매출처": "그외 기타",
            **{column: remaining_values[column] / 1_000_000 for column in value_columns},
            "monthly_plan": "-",
        })

daily_label = f"일매출({reference_date:%y/%m/%d})"
current_month_label = f"당월누적({reference_date.month}월)"
plan_label = f"당월계획({reference_date.month}월)"
previous_month_label = f"전월누적({previous_month_end.month}월)"
previous_year_label = f"전년동월누적({previous_year_end:%y년} {previous_year_end.month}월)"
detail = pd.DataFrame(detail_rows).rename(columns={
    "daily_sales": daily_label,
    "current_month_sales": current_month_label,
    "monthly_plan": plan_label,
    "previous_month_sales": previous_month_label,
    "previous_year_sales": previous_year_label,
})
detail = detail[["구분", "매출처", daily_label, current_month_label, plan_label, previous_month_label, previous_year_label]]

def style_pivot_row(row: pd.Series) -> list[str]:
    is_summary = row["구분"] == "Total sum" or row["매출처"] == "SUM"
    style = "font-weight: 700; background-color: #F5F3FF" if is_summary else ""
    return [style] * len(row)

styled_detail = detail.style.apply(style_pivot_row, axis=1)

st.dataframe(
    styled_detail,
    use_container_width=True,
    hide_index=True,
    column_config={
        daily_label: st.column_config.NumberColumn(format="%,.1f"),
        current_month_label: st.column_config.NumberColumn(format="%,.1f"),
        previous_month_label: st.column_config.NumberColumn(format="%,.1f"),
        previous_year_label: st.column_config.NumberColumn(format="%,.1f"),
    },
)

csv = detail.to_csv(index=False).encode("utf-8-sig")
st.download_button("매출처 실적 CSV 다운로드", csv, f"dertte_account_sales_{date.today():%Y%m%d}.csv", "text/csv")
st.caption("© 데르뜨 · 매출액과 판매수량은 선택한 기간 및 필터 기준입니다.")
