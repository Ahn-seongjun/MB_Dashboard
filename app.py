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
    "primary": "#194F95",
    "secondary": "#245FA3",
    "accent": "#3F78B8",
    "success": "#6697C8",
    "muted": "#617B98",
    "grid": "#D9E3EC",
}
BLUE_PALETTE = ["#143D75", "#194F95", "#245FA3", "#3F78B8", "#6697C8", "#91B1D7"]
# 로고 색상을 기준으로 한 고정 범례 색상입니다. 같은 항목은 모든 그래프에서 같은 색을 사용합니다.
CHANNEL_COLOR_MAP = {
    "B2B": "#12A6D4",
    "KA": "#B18455",
    "온라인": "#8F9194",
    "[미매핑]": "#D85C5C",
    "(미매핑)": "#D85C5C",
}
CATEGORY_COLOR_MAP = {
    "제품제과": "#12A6D4",
    "제품제빵": "#B18455",
    "상품제과": "#6C63B5",
    "상품제빵": "#4E8F72",
    "반제품제과": "#D66D45",
    "반제품제빵": "#5E78A8",
    "원재료가공식품": "#8F9194",
    "기타": "#B8B9BB",
}
BREAD_PRIMARY = "#7A4E2D"
BREAD_SECONDARY = "#A87347"
BREAD_ACCENT = "#C99A6B"
BREAD_CREAM = "#F7EBDD"
BREAD_PALETTE = ["#6B4226", "#8B5E3C", "#A87347", "#C99A6B", "#DFC09D", "#F1E1CF"]
BREAD_SCALE = [[0.0, "#FBF5EC"], [0.5, "#D9B58C"], [1.0, "#7A4E2D"]]
PAUL_PRIMARY = "#8E1738"
PAUL_DARK = "#241C1A"
PAUL_SECONDARY = "#5B3835"
PAUL_CREAM = "#F7F1EE"
PAUL_SCALE = [[0.0, "#FAF5F3"], [0.5, "#C88796"], [1.0, "#7B102F"]]
MEALDO_VAT_RATE = 0.10

# 집계 로직 변경 시 값을 올리면 기존 Streamlit 데이터 캐시를 즉시 폐기합니다.
DATA_TRANSFORM_VERSION = 9


st.markdown(
    """
    <style>
        .stApp { background: #FFFFFF; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #D9E3EC; }
        /* 대시보드에서 사용하지 않는 Streamlit 기본 Deploy 툴바와 빈 헤더 제거 */
        [data-testid="stHeader"],
        [data-testid="stToolbar"] { display: none !important; }
        .block-container { padding-top: .75rem; padding-bottom: 2rem; }
        .st-key-sticky_dashboard_header_dertte,
        .st-key-sticky_dashboard_header_mealdo {
            position: static;
        }
        [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_dertte),
        [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_mealdo) {
            position: sticky; top: 0; z-index: 900;
            background: rgba(255, 255, 255, .97);
            /* Streamlit wide 본문의 좌우 5rem 여백을 모두 상쇄해 헤더 띠를 전체 폭으로 확장 */
            width: calc(100% + 10rem) !important;
            min-width: calc(100% + 10rem) !important;
            max-width: none !important;
            box-sizing: border-box; overflow: visible;
            padding: .78rem 5rem .68rem;
            margin: -.8rem -5rem .7rem;
            border-bottom: 1px solid #DCE9F6;
            box-shadow: 0 8px 18px rgba(30, 64, 175, .06);
            backdrop-filter: blur(8px);
        }
        @media (max-width: 900px) {
            [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_dertte),
            [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_mealdo) {
                width: calc(100% + 2rem) !important;
                min-width: calc(100% + 2rem) !important;
                padding-left: 1rem; padding-right: 1rem;
                margin-left: -1rem; margin-right: -1rem;
            }
        }
        .st-key-sticky_dashboard_header_dertte .brand,
        .st-key-sticky_dashboard_header_mealdo .brand {
            font-size: 1.35rem; white-space: nowrap;
        }
        .st-key-sticky_dashboard_header_dertte .brand-sub,
        .st-key-sticky_dashboard_header_mealdo .brand-sub {
            font-size: .8rem; white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis;
        }
        .st-key-sticky_dashboard_header_dertte .header-title-block,
        .st-key-sticky_dashboard_header_mealdo .header-title-block {
            min-height: 3.25rem; display: flex; flex-direction: column;
            justify-content: center;
        }
        .st-key-sticky_dashboard_header_dertte .header-title-block .brand-sub,
        .st-key-sticky_dashboard_header_mealdo .header-title-block .brand-sub {
            margin-top: .12rem; line-height: 1.2;
        }
        /* 타이틀·조회기간·집계버튼이 들어 있는 최상위 행 전체를 헤더의 세로 중앙에 정렬 */
        .st-key-sticky_dashboard_header_dertte [data-testid="stHorizontalBlock"]:has(.header-title-block),
        .st-key-sticky_dashboard_header_mealdo [data-testid="stHorizontalBlock"]:has(.header-title-block) {
            align-items: center !important;
            transform: translateY(-.5rem);
        }
        .brand { font-size: 1.65rem; font-weight: 800; letter-spacing: -0.04em; color: #143D75; }
        .brand-sub { color: #617B98; font-size: .9rem; margin-top: -.25rem; }
        .section-title { font-size: 1.1rem; font-weight: 750; color: #143D75; margin: .4rem 0 .2rem; }
        .section-title-row { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: .4rem 0 .2rem; }
        .section-title-row .section-title { margin: 0; }
        .section-unit { color: #64748B; font-size: .76rem; font-weight: 500; white-space: nowrap; }
        .section-sub { color: #617B98; font-size: .84rem; margin-bottom: .8rem; }
        [data-testid="stMetric"] {
            background: #FFFFFF; border: 1px solid #DCE9F6; border-radius: 16px;
            padding: 18px 20px; box-shadow: 0 3px 14px rgba(42, 32, 60, .04);
        }
        [data-testid="stMetricLabel"] { color: #617B98; }
        [data-testid="stMetricValue"] { color: #143D75; }
        .st-key-dertte_overview_kpis [data-testid="stMetric"] {
            padding: 12px 15px; border-radius: 13px;
            min-height: 112px; box-sizing: border-box;
        }
        .st-key-dertte_overview_kpis [data-testid="stMetricLabel"] {
            font-size: .72rem;
        }
        .st-key-dertte_overview_kpis [data-testid="stMetricValue"] {
            font-size: 1.32rem;
        }
        .st-key-dertte_overview_kpis [data-testid="stMetricDelta"] {
            font-size: .66rem;
        }
        .st-key-dertte_current_month_metric [data-testid="stMetricDelta"] {
            visibility: hidden;
        }
        .st-key-mealdo_first_sale_metric [data-testid="stMetricValue"] {
            font-size: 1.35rem; white-space: nowrap;
        }
        div[data-testid="stPlotlyChart"] {
            background: transparent; border: 0; border-radius: 0;
            padding: 0; box-shadow: none;
        }
        .status-pill {
            display: inline-block; padding: 5px 10px; border-radius: 999px;
            background: #DCE9F6; color: #194F95; font-size: .78rem; font-weight: 700;
        }
        .nav-title { color: #617B98; font-size: .7rem; font-weight: 800; letter-spacing: .12em; margin: .2rem 0 .55rem; }
        [data-testid="stSidebar"] div[role="radiogroup"] { gap: .45rem; }
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            width: 100%; padding: .72rem .78rem; border: 1px solid #D9E3EC;
            border-radius: 12px; background: #F8FAFC; transition: all .15s ease;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            border-color: #91B1D7; background: #EAF2FA;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            border-color: #3F78B8; background: #DCE9F6;
            box-shadow: 0 4px 12px rgba(37, 99, 235, .10);
        }
        [data-testid="stSidebar"] div[role="radiogroup"] input { display: none; }
        [data-testid="stSidebar"] div[role="radiogroup"] p { font-weight: 700; color: #24496F; }
        .st-key-store_nav_mealdo [data-testid="stButton"] button,
        .st-key-store_nav_paul [data-testid="stButton"] button {
            width: 100%; justify-content: flex-start; min-height: 42px;
            padding: .55rem .72rem; border-radius: 10px; font-weight: 700;
        }
        .st-key-store_nav_mealdo [data-testid="stButton"],
        .st-key-store_nav_paul [data-testid="stButton"] { margin-bottom: .28rem; }
        [data-testid="stSidebar"] [data-testid="stExpander"] {
            margin-bottom: .58rem;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details {
            background: #FFFFFF; border: 1px solid #E2E6EC; border-radius: 12px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, .03); overflow: hidden;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details:hover {
            border-color: #CBD5E1; box-shadow: 0 3px 10px rgba(15, 23, 42, .05);
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary {
            min-height: 46px; padding: .15rem .7rem .15rem .85rem;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
            display: flex; align-items: center; width: 100%; margin: 0;
            color: #111827; font-size: .9rem; font-weight: 750;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary p span {
            margin-left: auto; margin-right: .35rem; padding: .16rem .52rem;
            border-radius: 999px; background: #E5EFF9 !important;
            color: #245FA3 !important; font-size: .76rem; font-weight: 800;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
            padding: .15rem .75rem .7rem;
            border-top: 1px solid #F1F5F9;
        }
        .insight-box {
            padding: 15px 18px; border-radius: 14px; background: linear-gradient(90deg, #EAF2FA, #F1F6FB);
            border: 1px solid #B8D0E8; color: #24496F; font-size: .92rem; margin: .7rem 0 1rem;
        }
        .insight-box b { color: #194F95; }
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


def million_won(value: float) -> str:
    """금액을 백만원 단위로 고정해 표시합니다."""
    return f"{value / 1_000_000:,.1f}백만원"


def million_won_integer(value: float) -> str:
    """금액을 백만원 단위 정수로 반올림해 표시합니다."""
    return f"{value / 1_000_000:,.0f}백만원"


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


def disposal_rate(sales_quantity: float, waste_quantity: float) -> float:
    """판매수량과 폐기수량 합계 중 폐기수량이 차지하는 비율입니다."""
    denominator = max(float(sales_quantity), 0.0) + max(float(waste_quantity), 0.0)
    return 0.0 if denominator == 0 else max(float(waste_quantity), 0.0) / denominator * 100


def mark_brand_navigation_changed() -> None:
    """조건부 브랜드 화면을 다음 실행에서 깨끗하게 다시 구성하도록 표시합니다."""
    st.session_state["_brand_navigation_changed"] = True


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


def apply_account_encoding(frame: pd.DataFrame, mapping_path: Path) -> pd.DataFrame:
    """원장 매출처명을 영업 기준 매출처와 2단계 채널 값으로 치환합니다."""
    source_key = "매출처명"
    mapping_key = "매출처명(원장기준)"
    mapped_account = "매출처명(영업기준)"
    channel_level_1 = "Channel1_1"
    channel_level_2 = "Channel1_2"
    required_mapping_columns = {
        mapping_key, mapped_account, channel_level_1, channel_level_2,
    }
    if source_key not in frame.columns:
        raise ValueError(f"원본 매출 데이터에 조인 키 '{source_key}' 컬럼이 없습니다.")
    if not mapping_path.exists():
        raise FileNotFoundError(f"매출처 인코딩 파일이 없습니다: {mapping_path}")

    mapping = pd.read_csv(mapping_path, encoding="utf-8-sig", low_memory=False)
    mapping.columns = mapping.columns.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    missing_mapping_columns = sorted(required_mapping_columns - set(mapping.columns))
    if missing_mapping_columns:
        raise ValueError(
            "매출처 인코딩 파일에 필수 컬럼이 없습니다: " + ", ".join(missing_mapping_columns)
        )

    mapping = mapping[[mapping_key, mapped_account, channel_level_1, channel_level_2]].copy()
    for column in mapping.columns:
        mapping[column] = mapping[column].fillna("").astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    mapping = mapping.loc[mapping[mapping_key].ne("")]
    duplicated_keys = mapping.loc[mapping[mapping_key].duplicated(keep=False), mapping_key].unique()
    if len(duplicated_keys):
        raise ValueError(
            "매출처 인코딩 파일의 원장기준 키가 중복되었습니다: "
            + ", ".join(map(str, duplicated_keys[:10]))
        )

    encoded = frame.copy()
    encoded[source_key] = encoded[source_key].fillna("").astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    # 기존 유통경로는 조인 결과로 대체하므로 원장에서 제거합니다.
    encoded = encoded.drop(columns=["유통경로"], errors="ignore")
    encoded = encoded.merge(
        mapping,
        how="left",
        left_on=source_key,
        right_on=mapping_key,
        validate="many_to_one",
    )
    unmatched = encoded[mapped_account].isna() | encoded[mapped_account].eq("")
    encoded.loc[unmatched, mapped_account] = "[미매핑] " + encoded.loc[unmatched, source_key]
    encoded.loc[unmatched, channel_level_1] = "(미매핑)"
    encoded.loc[unmatched, channel_level_2] = "(미매핑)"
    return encoded.drop(columns=[source_key, mapping_key], errors="ignore").rename(columns={
        mapped_account: "account_name",
        channel_level_1: "channel",
        channel_level_2: "channel_detail",
    })


def aggregate_query_result(frame: pd.DataFrame) -> pd.DataFrame:
    """원본 쿼리 결과를 대시보드 일별 집계 구조로 변환합니다."""
    korean_column_map = {
        "일자": "date",
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
        "channel_detail",
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

    frame["weighted_unit_amount"] = frame["unit_price"] * frame["quantity"]
    metric_columns = [
        "sales", "quantity", "weighted_unit_amount",
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
    mapping_path = data_dir / "매출처_인코딩.csv"
    csv_paths = sorted(path for path in data_dir.glob("*.csv") if path != mapping_path)
    if not csv_paths:
        raise FileNotFoundError(f"CSV 파일이 없습니다: {data_dir}")

    frames: list[pd.DataFrame] = []
    for csv_path in csv_paths:
        try:
            frame = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
        except UnicodeDecodeError:
            frame = pd.read_csv(csv_path, encoding="cp949", low_memory=False)
        frames.append(frame)

    encoded_frame = apply_account_encoding(pd.concat(frames, ignore_index=True), mapping_path)
    return aggregate_query_result(encoded_frame)


def style_figure(fig: go.Figure, height: int = 350) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=48, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", color="#334155", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#143D75", font_color="white"),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=COLORS["grid"],
        separatethousands=True,
        exponentformat="none",
        showexponent="none",
        showticklabels=True,
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor=COLORS["grid"],
        zeroline=False,
        separatethousands=True,
        exponentformat="none",
        showexponent="none",
        showticklabels=True,
        automargin=True,
    )
    numeric_axis_keywords = ("매출", "수량", "단가", "금액", "비중", "%")
    for axis in [*fig.select_xaxes(), *fig.select_yaxes()]:
        axis_title = axis.title.text or ""
        if any(keyword in axis_title for keyword in numeric_axis_keywords):
            axis.update(tickformat=",.1f", hoverformat=",.1f")
    fig.update_coloraxes(colorbar=dict(tickformat=",.1f"))
    return fig


def style_dertte_figure(fig: go.Figure, height: int = 350) -> go.Figure:
    """데르뜨 금액·수량 축을 소수점 없는 형식으로 표시합니다."""
    fig = style_figure(fig, height)
    numeric_axis_keywords = ("매출", "수량", "단가", "금액")
    for axis in [*fig.select_xaxes(), *fig.select_yaxes()]:
        axis_title = axis.title.text or ""
        if any(keyword in axis_title for keyword in numeric_axis_keywords):
            axis.update(tickformat=",.0f", hoverformat=",.0f")
    fig.update_coloraxes(colorbar=dict(tickformat=",.0f"))
    return fig


def section_title(title: str, unit: str) -> None:
    """그래프·표 제목 우측 상단에 단위를 일관된 형식으로 표시합니다."""
    st.markdown(
        f'<div class="section-title-row"><div class="section-title">{title}</div>'
        f'<div class="section-unit">(단위: {unit})</div></div>',
        unsafe_allow_html=True,
    )


def sidebar_filter_dropdown(label: str, options: list, key: str) -> list:
    """선택 개수를 표시하는 사이드바용 접이식 다중 선택 필터입니다."""
    normalized_options = list(options)
    options_state_key = f"{key}__available_options"
    current_options_signature = tuple(normalized_options)
    previous_options_signature = st.session_state.get(options_state_key)

    # 상위 필터 변경으로 선택지 구성이 달라지면 새 하위 목록은 전체 선택합니다.
    if key not in st.session_state or previous_options_signature != current_options_signature:
        st.session_state[key] = normalized_options
    else:
        st.session_state[key] = [
            value for value in st.session_state[key] if value in normalized_options
        ]
    st.session_state[options_state_key] = current_options_signature

    selected_count = len(st.session_state[key])
    with st.expander(f"**{label}** :blue-background[{selected_count}개]"):
        return st.multiselect(
            label,
            normalized_options,
            key=key,
            label_visibility="collapsed",
            placeholder=f"{label} 선택",
        )


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
    channel_count = frame["channel"].nunique()
    account_count = frame["account_name"].nunique()
    total_sales = frame["sales"].sum()
    total_quantity = frame["quantity"].sum()
    summary_cols = st.columns(4)
    summary_cols[0].metric("활성 채널", f"{channel_count:,}개", help="Channel1_1 컬럼의 고유값 개수입니다.")
    summary_cols[1].metric("활성 매출처", f"{account_count:,}개")
    summary_cols[2].metric("총 매출", million_won_integer(total_sales))
    summary_cols[3].metric("판매 수량", f"{total_quantity:,.0f}개")

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
    daily_channel["sales_million"] = (daily_channel["sales"] / 1_000_000).round(0)
    trend_fig = px.line(
        daily_channel,
        x="date",
        y="sales_million",
        color="channel",
        markers=True,
        color_discrete_map=CHANNEL_COLOR_MAP,
        labels={"date": "일자", "sales_million": "매출(백만원)", "channel": "채널"},
    )
    daily_tick_step = max(1, int(np.ceil(len(full_dates) / 12)))
    daily_tick_values = full_dates[::daily_tick_step].tolist()
    if daily_tick_values and daily_tick_values[-1] != full_dates[-1]:
        daily_tick_values.append(full_dates[-1])
    trend_fig.update_xaxes(
        tickmode="array",
        tickvals=daily_tick_values,
        ticktext=[pd.Timestamp(value).strftime("%Y-%m-%d") for value in daily_tick_values],
        tickangle=0,
    )
    trend_fig.update_traces(
        hovertemplate=(
            "일자: %{x|%Y-%m-%d}<br>"
            "매출: %{y:,.0f}백만원<extra>%{fullData.name}</extra>"
        )
    )
    section_title("채널별 일간 매출 흐름", "백만원")
    st.plotly_chart(style_dertte_figure(trend_fig, 380), use_container_width=True)
    with st.expander("일간 채널 집계 데이터 보기 (단위: 백만원)"):
        daily_channel_table = (
            daily_channel.pivot(index="date", columns="channel", values="sales_million")
            .fillna(0)
            .reset_index()
        )
        daily_channel_table["date"] = daily_channel_table["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            daily_channel_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                column: st.column_config.NumberColumn(format="%,.0f")
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
    account_summary["sales_million"] = (account_summary["sales"] / 1_000_000).round(0)
    account_summary["bubble_size"] = account_summary["quantity"].clip(lower=0)

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
        f'<b>{million_won_integer(leading_channel["sales"])}</b>을 기록했습니다. 이 채널에서 판매수량이 가장 많은 제품은 '
        f'<b>{leading_product["product_name"]}</b> ({leading_product["quantity"]:,.0f}개)입니다.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        section_title("매출처 매출 TOP 10", "백만원")
        top_accounts = account_summary.nlargest(10, "sales").sort_values("sales", ascending=False)
        account_rank_order = top_accounts["account_name"].tolist()
        rank_fig = px.bar(
            top_accounts,
            x="sales_million",
            y="account_name",
            color="channel",
            orientation="h",
            color_discrete_map=CHANNEL_COLOR_MAP,
            labels={"sales_million": "매출액", "account_name": "매출처명", "channel": "채널"},
        )
        rank_fig.update_yaxes(
            categoryorder="array",
            categoryarray=account_rank_order,
            autorange="reversed",
        )
        rank_fig.update_layout(legend_title_text="채널")
        st.plotly_chart(style_dertte_figure(rank_fig, 430), use_container_width=True)

    with right:
        section_title("매출처별 매출 · 판매수량 포지션", "백만원, EA")
        scatter_fig = px.scatter(
            account_summary,
            x="sales_million",
            y="quantity",
            size="bubble_size",
            color="channel",
            hover_name="account_name",
            hover_data={"bubble_size": False},
            color_discrete_map=CHANNEL_COLOR_MAP,
            labels={
                "sales_million": "매출액",
                "quantity": "판매수량(EA)",
                "bubble_size": "판매수량",
                "channel": "채널",
            },
            size_max=42,
        )
        st.plotly_chart(style_dertte_figure(scatter_fig, 430), use_container_width=True)

    section_title("채널별 판매수량 TOP 제품", "EA")
    st.markdown('<div class="section-sub">각 채널에서 실제로 어떤 제품이 많이 움직였는지 판매수량 기준으로 비교합니다.</div>', unsafe_allow_html=True)
    channel_product_source = frame.loc[
        ~frame["channel"].astype(str).str.contains("미매핑", na=False)
    ]
    channel_product = channel_product_source.groupby(
        ["channel", "product_name"], as_index=False
    )["quantity"].sum()
    channel_product = (
        channel_product.sort_values(["channel", "quantity"], ascending=[True, False])
        .groupby("channel", as_index=False, group_keys=False)
        .head(10)
        .sort_values(["channel", "quantity"], ascending=[True, True])
    )
    product_channel_count = channel_product["channel"].nunique()
    facet_rows = max(1, int(np.ceil(product_channel_count / 2)))
    channel_product_fig = px.bar(
        channel_product,
        x="quantity",
        y="product_name",
        color="channel",
        facet_col="channel",
        facet_col_wrap=2,
        orientation="h",
        color_discrete_map=CHANNEL_COLOR_MAP,
        labels={"quantity": "판매수량(EA)", "product_name": "제품명", "channel": "채널"},
    )
    channel_product_fig.update_yaxes(
        matches=None,
        showticklabels=True,
        categoryorder="total ascending",
    )
    channel_product_fig.update_xaxes(matches=None)
    channel_product_fig.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
    st.plotly_chart(style_dertte_figure(channel_product_fig, 270 * facet_rows), use_container_width=True)

    section_title("채널별 MC 대분류 매출 비중", "%")
    st.markdown('<div class="section-sub">채널마다 어떤 제품군이 매출을 주도하는지 100% 구성비로 비교합니다.</div>', unsafe_allow_html=True)
    channel_category = frame.groupby(["channel", "category_large"], as_index=False)["sales"].sum()
    category_fig = px.bar(
        channel_category,
        x="channel",
        y="sales",
        color="category_large",
        color_discrete_map=CATEGORY_COLOR_MAP,
        labels={"channel": "채널", "sales": "매출 비중(%)", "category_large": "MC 대분류"},
    )
    category_fig.update_layout(barmode="stack", barnorm="percent")
    st.plotly_chart(style_dertte_figure(category_fig, 380), use_container_width=True)


def render_product_overview(frame: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
    product_source = frame.copy()
    product_source["weighted_unit_amount"] = product_source["unit_price"] * product_source["quantity"]
    product_summary = product_source.groupby("product_name", as_index=False).agg(
        sales=("sales", "sum"),
        quantity=("quantity", "sum"),
        weighted_unit_amount=("weighted_unit_amount", "sum"),
    )
    product_summary["sales_million"] = (product_summary["sales"] / 1_000_000).round(0)
    product_summary["average_unit_price"] = np.where(
        product_summary["quantity"] == 0,
        0,
        product_summary["weighted_unit_amount"] / product_summary["quantity"],
    )
    product_summary["bubble_size"] = product_summary["quantity"].clip(lower=0)

    total_sales = product_summary["sales"].sum()
    product_cols = st.columns(4)
    product_cols[0].metric("판매 제품", f"{product_summary['product_name'].nunique():,}개")
    product_cols[1].metric("총 매출", million_won_integer(total_sales))
    product_cols[2].metric("판매 수량", f"{product_summary['quantity'].sum():,.0f}개")
    product_cols[3].metric("평균 물품단가", won(weighted_unit_price(frame)))

    leading_product = product_summary.nlargest(1, "sales").iloc[0]
    large_category_sales = frame.groupby("category_large", as_index=False)["sales"].sum().nlargest(1, "sales").iloc[0]
    st.markdown(
        f'<div class="insight-box">매출 기여도가 가장 높은 제품은 <b>{leading_product["product_name"]}</b>로 '
        f'<b>{million_won_integer(leading_product["sales"])}</b>을 기록했습니다. MC 대분류에서는 '
        f'<b>{large_category_sales["category_large"]}</b>가 전체 매출을 가장 크게 이끌고 있습니다.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1])
    with left:
        section_title("제품 매출 TOP 10", "백만원")
        top_products = product_summary.nlargest(10, "sales").sort_values("sales")
        product_fig = px.bar(
            top_products,
            x="sales_million",
            y="product_name",
            orientation="h",
            color="sales_million",
            color_continuous_scale=[[0, "#DCE9F6"], [1, COLORS["primary"]]],
            labels={"sales_million": "매출액", "product_name": "제품명"},
        )
        product_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_dertte_figure(product_fig, 420), use_container_width=True)

    with right:
        section_title("카테고리 매출 구성", "백만원, %")
        category_sales = frame.groupby(
            ["category_large", "category_middle", "category_small", "category_detail"],
            as_index=False,
        )["sales"].sum()
        category_sales["sales_million"] = (category_sales["sales"] / 1_000_000).round(0)
        sunburst_fig = px.sunburst(
            category_sales,
            path=["category_large", "category_middle", "category_small", "category_detail"],
            values="sales_million",
            color="sales_million",
            color_continuous_scale=[[0, "#D6E7F5"], [1, COLORS["secondary"]]],
            labels={"sales_million": "매출(백만원)"},
        )
        sunburst_fig.update_traces(
            textinfo="label+percent parent",
            hovertemplate="<b>%{label}</b><br>매출: %{value:,.0f}백만원<br>상위 분류 내 비중: %{percentParent:.1%}<extra></extra>",
        )
        sunburst_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_dertte_figure(sunburst_fig, 420), use_container_width=True)

    section_title("제품별 매출 · 판매수량 포지션", "백만원, EA, 원")
    product_scatter = px.scatter(
        product_summary,
        x="sales_million",
        y="quantity",
        size="bubble_size",
        color="average_unit_price",
        hover_name="product_name",
        color_continuous_scale=[
            [0.0, "#194F95"],
            [0.5, "#3F78B8"],
            [1.0, "#91B1D7"],
        ],
        labels={"sales_million": "매출액", "quantity": "판매수량(EA)", "bubble_size": "판매수량(EA)", "average_unit_price": "평균 물품단가(원)"},
        size_max=55,
    )
    product_scatter.update_traces(marker=dict(opacity=.9, line=dict(color="#FFFFFF", width=1.5)))
    st.plotly_chart(style_dertte_figure(product_scatter, 390), use_container_width=True)

    product_detail = product_summary.rename(
        columns={
            "product_name": "제품명", "sales_million": "매출(백만원)", "quantity": "판매수량",
            "average_unit_price": "평균물품단가",
        }
    )[["제품명", "매출(백만원)", "판매수량", "평균물품단가"]]
    section_title("제품 상세 실적", "백만원, EA, 원")
    st.dataframe(
        product_detail.sort_values("매출(백만원)", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "매출(백만원)": st.column_config.NumberColumn(format="%,.0f"),
            "판매수량": st.column_config.NumberColumn(format="%,.0f"),
            "평균물품단가": st.column_config.NumberColumn(format="₩ %,.0f"),
        },
    )


@st.cache_data(ttl=600)
def load_store_sales_data(
    data_version: tuple[tuple[str, int, int], ...],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """밀도 매출·폐기 및 폴바셋 CSV를 각 데이터 구조에 맞춰 정규화합니다."""
    del data_version
    data_dir = Path(__file__).resolve().parent / "data" / "mealdo"
    mealdo_frames: list[pd.DataFrame] = []
    mealdo_waste_frames: list[pd.DataFrame] = []
    paul_frames: list[pd.DataFrame] = []

    dashboard_files = (
        data_dir / "밀도_일별매출_통합.csv",
        data_dir / "밀도_폐기데이터_통합.csv",
        data_dir / "폴바셋_일별매출_통합.csv",
    )
    for csv_path in dashboard_files:
        if not csv_path.exists():
            raise FileNotFoundError(
                f"대시보드용 통합 파일이 없습니다: {csv_path.name}. "
                "merge_mealdo_monthly_data.py를 먼저 실행해 주세요."
            )
        try:
            frame = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
        except UnicodeDecodeError:
            frame = pd.read_csv(csv_path, encoding="cp949", low_memory=False)

        if {"기준일", "매장명", "품목명", "실매출"}.issubset(frame.columns):
            mealdo_frames.append(frame)
        elif {"기준일", "매장명", "품목코드", "폐기수량", "폐기금액"}.issubset(frame.columns):
            mealdo_waste_frames.append(frame)
        elif {"기준일", "매장명", "매출액_원"}.issubset(frame.columns):
            paul_frames.append(frame)

    mealdo = pd.concat(mealdo_frames, ignore_index=True) if mealdo_frames else pd.DataFrame()
    mealdo_waste = pd.concat(mealdo_waste_frames, ignore_index=True) if mealdo_waste_frames else pd.DataFrame()
    paul = pd.concat(paul_frames, ignore_index=True) if paul_frames else pd.DataFrame()

    if not mealdo.empty:
        mealdo = mealdo.rename(columns={
            "기준일": "date", "매장명": "store", "대분류명": "category_large",
            "중분류명": "category_middle", "품목코드": "product_code",
            "품목명": "product_name", "수량": "quantity", "총매출": "gross_sales",
            "실매출": "sales_vat_included",
        })
        mealdo["date"] = pd.to_datetime(mealdo["date"], errors="coerce")
        for column in ("quantity", "gross_sales", "sales_vat_included"):
            mealdo[column] = pd.to_numeric(mealdo[column], errors="coerce").fillna(0)
        # 밀도 실매출은 부가세 포함 금액이므로 모든 매출 분석은 공급가액 기준 순매출을 사용합니다.
        mealdo["sales"] = mealdo["sales_vat_included"] / (1 + MEALDO_VAT_RATE)
        mealdo["product_code"] = mealdo["product_code"].fillna("").astype(str).str.strip()
        mealdo = mealdo.dropna(subset=["date"])

    if not mealdo_waste.empty:
        mealdo_waste = mealdo_waste.rename(columns={
            "기준일": "date", "브랜드": "brand", "매장명": "store",
            "폐기유형": "waste_type", "폐기사유": "waste_reason",
            "중분류명": "category_middle", "품목코드": "product_code",
            "품목명": "product_name", "폐기수량": "waste_quantity",
            "단가": "unit_price", "폐기금액": "waste_amount",
        })
        mealdo_waste["date"] = pd.to_datetime(mealdo_waste["date"], errors="coerce")
        for column in ("waste_quantity", "unit_price", "waste_amount"):
            mealdo_waste[column] = pd.to_numeric(mealdo_waste[column], errors="coerce").fillna(0)
        mealdo_waste["product_code"] = mealdo_waste["product_code"].fillna("").astype(str).str.strip()
        mealdo_waste = mealdo_waste.dropna(subset=["date"])

    if not paul.empty:
        paul = paul.rename(columns={
            "기준일": "date", "브랜드": "brand", "매장명": "store",
            "매출액_원": "sales", "원본매출_만원": "source_sales_manwon",
        })
        paul["date"] = pd.to_datetime(paul["date"], errors="coerce")
        paul["sales"] = pd.to_numeric(paul["sales"], errors="coerce").fillna(0)
        paul = paul.dropna(subset=["date"])

    return mealdo, paul, mealdo_waste


def render_mealdo_store_dashboard(frame: pd.DataFrame, waste: pd.DataFrame) -> None:
    start_date, end_date = frame["date"].min(), frame["date"].max()
    total_sales = frame["sales"].sum()
    total_quantity = frame["quantity"].sum()
    store_sales = frame.groupby("store", as_index=False)["sales"].sum()
    store_sales["sales_million"] = (store_sales["sales"] / 1_000_000).round(1)
    product_sales = frame.groupby("product_name", as_index=False).agg(
        sales=("sales", "sum"), quantity=("quantity", "sum")
    )
    product_sales["sales_million"] = (product_sales["sales"] / 1_000_000).round(1)

    cols = st.columns(4)
    cols[0].metric("순매출", million_won(total_sales), help="부가세 포함 실매출 ÷ 1.1")
    cols[1].metric("판매수량", f"{total_quantity:,.0f} EA")
    cols[2].metric("운영 매장", f"{frame['store'].nunique():,}개 지점")
    cols[3].metric("판매 제품", f"{frame['product_name'].nunique():,}종")

    total_waste_quantity = waste["waste_quantity"].sum() if not waste.empty else 0
    total_waste_amount = waste["waste_amount"].sum() if not waste.empty else 0
    waste_cols = st.columns(4)
    waste_cols[0].metric("폐기수량", f"{total_waste_quantity:,.0f} EA")
    waste_cols[1].metric("폐기비용", million_won(total_waste_amount))
    waste_cols[2].metric("폐기율", f"{disposal_rate(total_quantity, total_waste_quantity):,.1f}%",
                         help="폐기수량 ÷ (판매수량 + 폐기수량) × 100")
    waste_cols[3].metric("폐기 제품", f"{waste['product_code'].nunique() if not waste.empty else 0:,}종")

    top_store = store_sales.nlargest(1, "sales").iloc[0]
    top_product = product_sales.nlargest(1, "sales").iloc[0]
    st.markdown(
        f'<div class="insight-box">선택 기간 순매출 1위 매장은 <b>{top_store["store"]}</b>이며 '
        f'<b>{million_won(top_store["sales"])}</b>을 기록했습니다. 제품 순매출은 '
        f'<b>{top_product["product_name"]}</b>이 가장 높습니다.</div>', unsafe_allow_html=True,
    )

    store_quantity = frame.groupby("store")["quantity"].sum().rename("sales_quantity")
    store_waste = (
        waste.groupby("store").agg(
            waste_quantity=("waste_quantity", "sum"),
            waste_amount=("waste_amount", "sum"),
        )
        if not waste.empty else pd.DataFrame(columns=["waste_quantity", "waste_amount"])
    )
    store_waste_summary = (
        pd.concat([store_quantity, store_waste], axis=1)
        .fillna(0)
        .reset_index()
    )
    store_waste_summary["waste_rate"] = np.where(
        store_waste_summary["sales_quantity"] + store_waste_summary["waste_quantity"] == 0,
        0,
        store_waste_summary["waste_quantity"]
        / (store_waste_summary["sales_quantity"] + store_waste_summary["waste_quantity"]) * 100,
    )
    stores_with_waste = store_waste_summary.loc[store_waste_summary["waste_quantity"] > 0]
    if not stores_with_waste.empty:
        top_waste_store = stores_with_waste.sort_values(
            ["waste_rate", "waste_quantity"], ascending=False
        ).iloc[0]
        st.markdown(
            f'<div class="insight-box">선택 기간 폐기율 1위 매장은 '
            f'<b>{top_waste_store["store"]}</b>이며 폐기율은 '
            f'<b>{top_waste_store["waste_rate"]:,.1f}%</b>, 폐기수량은 '
            f'<b>{top_waste_store["waste_quantity"]:,.0f} EA</b>, 폐기비용은 '
            f'<b>{million_won(top_waste_store["waste_amount"])}</b>입니다.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="insight-box">선택 기간에 집계된 매장 폐기수량이 없습니다.</div>',
            unsafe_allow_html=True,
        )

    daily = frame.groupby("date", as_index=False).agg(sales=("sales", "sum"), quantity=("quantity", "sum"))
    daily["sales_million"] = (daily["sales"] / 1_000_000).round(1)
    left, right = st.columns([1.25, 1])
    with left:
        section_title("일별 순매출 흐름", "백만원")
        fig = px.bar(daily, x="date", y="sales_million", color_discrete_sequence=[BREAD_PRIMARY],
                     labels={"date": "일자", "sales_million": "순매출(백만원)"})
        st.plotly_chart(style_figure(fig, 370), use_container_width=True)
    with right:
        section_title("매장 순매출 TOP 10", "백만원")
        top_stores = store_sales.nlargest(10, "sales").sort_values("sales")
        fig = px.bar(top_stores, x="sales_million", y="store", orientation="h", color="sales_million",
                     color_continuous_scale=[[0, BREAD_CREAM], [1, BREAD_PRIMARY]],
                     labels={"sales_million": "순매출", "store": "매장명"})
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(fig, 370), use_container_width=True)

    left, right = st.columns(2)
    with left:
        section_title("제품 순매출 TOP 10", "백만원, EA")
        top_products = product_sales.nlargest(10, "sales").sort_values("sales")
        fig = px.bar(top_products, x="sales_million", y="product_name", orientation="h", color="quantity",
                     color_continuous_scale=[[0, BREAD_CREAM], [1, BREAD_SECONDARY]],
                     labels={"sales_million": "순매출", "product_name": "제품명", "quantity": "판매수량(EA)"})
        st.plotly_chart(style_figure(fig, 410), use_container_width=True)
    with right:
        section_title("카테고리 순매출 구성", "백만원, %")
        category = frame.groupby(["category_large", "category_middle"], as_index=False)["sales"].sum()
        category["sales_million"] = (category["sales"] / 1_000_000).round(1)
        fig = px.sunburst(category, path=["category_large", "category_middle"], values="sales_million", color="sales_million",
                          color_continuous_scale=[[0, BREAD_CREAM], [1, BREAD_ACCENT]], labels={"sales_million": "순매출(백만원)"})
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(fig, 410), use_container_width=True)

    section_title("매장 × 주요 제품 순매출 분포", "백만원")
    top_store_names = store_sales.nlargest(10, "sales")["store"]
    top_product_names = product_sales.nlargest(10, "sales")["product_name"]
    heat = frame[frame["store"].isin(top_store_names) & frame["product_name"].isin(top_product_names)].pivot_table(
        index="store", columns="product_name", values="sales", aggfunc="sum", fill_value=0
    ).div(1_000_000).round(1)
    heat_fig = px.imshow(heat, aspect="auto", color_continuous_scale=BREAD_SCALE,
                         labels={"x": "제품", "y": "매장", "color": "순매출(백만원)"})
    st.plotly_chart(style_figure(heat_fig, 450), use_container_width=True)


def render_mealdo_store_sales_dashboard(frame: pd.DataFrame, previous: pd.DataFrame) -> None:
    """매장별 매출 규모, 비중, 증감 및 제품 구성을 분석합니다."""
    has_previous = not previous.empty
    store_summary = frame.groupby("store", as_index=False).agg(
        sales=("sales", "sum"), quantity=("quantity", "sum"), products=("product_name", "nunique")
    )
    previous_sales = previous.groupby("store")["sales"].sum().rename("previous_sales")
    store_summary = store_summary.join(previous_sales, on="store").fillna({"previous_sales": 0})
    store_summary["sales_million"] = (store_summary["sales"] / 1_000_000).round(1)
    store_summary["previous_sales_million"] = (store_summary["previous_sales"] / 1_000_000).round(1)
    store_summary["change_million"] = ((store_summary["sales"] - store_summary["previous_sales"]) / 1_000_000).round(1)
    total_sales = store_summary["sales"].sum()
    store_summary["sales_share"] = np.where(
        total_sales == 0, 0, store_summary["sales"] / total_sales * 100
    ).round(1)
    store_summary["average_item_price"] = np.where(
        store_summary["quantity"] == 0, 0, store_summary["sales"] / store_summary["quantity"]
    ).round(1)

    top_store = store_summary.nlargest(1, "sales").iloc[0]
    growth_store_count = int((store_summary["sales"] > store_summary["previous_sales"]).sum()) if has_previous else 0
    cols = st.columns(4)
    cols[0].metric("총 순매출", million_won(total_sales), help="부가세 포함 실매출 ÷ 1.1")
    cols[1].metric("매장당 평균 순매출", million_won(store_summary["sales"].mean()))
    cols[2].metric(
        "최고 매장 순매출", million_won(top_store["sales"]), top_store["store"],
        delta_color="off", help=f"순매출 1위 매장: {top_store['store']}",
    )
    cols[3].metric(
        "순매출 증가 매장", f"{growth_store_count:,}개" if has_previous else "비교 데이터 없음",
        help="선택 기간과 동일한 길이의 직전 기간보다 순매출이 증가한 매장 수입니다.",
    )

    left, right = st.columns(2)
    with left:
        section_title("매장별 순매출액 및 비중", "백만원, %")
        rank = store_summary.sort_values("sales")
        rank_fig = px.bar(
            rank, x="sales_million", y="store", orientation="h", color="sales_million",
            custom_data=["sales_share", "quantity"],
            labels={"sales_million": "순매출액", "store": "매장명", "sales_share": "순매출 비중",
                    "quantity": "판매수량(EA)"},
            color_continuous_scale=[[0, BREAD_CREAM], [1, BREAD_PRIMARY]],
        )
        rank_fig.update_traces(
            texttemplate="%{x:,.1f} (%{customdata[0]:.1f}%)", textposition="outside", cliponaxis=False,
            hovertemplate=("매장: %{y}<br>순매출액: %{x:,.1f}백만원<br>순매출 비중: %{customdata[0]:.1f}%"
                           "<br>판매수량: %{customdata[1]:,.0f} EA<extra></extra>"),
        )
        rank_fig.update_layout(coloraxis_showscale=False, margin=dict(l=18, r=105, t=48, b=16))
        st.plotly_chart(style_figure(rank_fig, 500), use_container_width=True)

    with right:
        section_title("매장별 직전 기간 대비 순매출 증감", "백만원")
        if has_previous:
            change = store_summary.sort_values("change_million")
            change["direction"] = np.where(change["change_million"] >= 0, "증가", "감소")
            change_fig = px.bar(
                change, x="change_million", y="store", orientation="h", color="direction",
                labels={"change_million": "순매출 증감액", "store": "매장명", "direction": "구분"},
                color_discrete_map={"증가": BREAD_PRIMARY, "감소": "#D95C5C"},
            )
            change_fig.update_traces(texttemplate="%{x:,.1f}", textposition="outside", cliponaxis=False)
            change_fig.update_layout(showlegend=False, margin=dict(l=18, r=70, t=48, b=16))
            st.plotly_chart(style_figure(change_fig, 500), use_container_width=True)
        else:
            st.info("선택 기간과 동일한 길이의 직전 기간 데이터가 없어 증감액을 계산할 수 없습니다.")

    store_order = store_summary.sort_values("sales", ascending=False)["store"].tolist()
    default_trend_stores = store_order[: min(5, len(store_order))]
    trend_stores = st.multiselect(
        "일별 흐름 비교 매장", store_order, default=default_trend_stores,
        key="mealdo_store_sales_trend_stores",
    )
    section_title("선택 매장 일별 순매출 흐름", "백만원")
    daily_store = (
        frame.loc[frame["store"].isin(trend_stores)]
        .groupby(["date", "store"], as_index=False)["sales"].sum()
    )
    daily_store["sales_million"] = (daily_store["sales"] / 1_000_000).round(1)
    trend_fig = px.line(
        daily_store, x="date", y="sales_million", color="store", markers=True,
        labels={"date": "일자", "sales_million": "순매출액", "store": "매장명"},
        color_discrete_sequence=BREAD_PALETTE,
    )
    trend_fig.update_traces(
        hovertemplate="%{x|%Y-%m-%d}<br>순매출액: %{y:,.1f}백만원<extra>%{fullData.name}</extra>"
    )
    st.plotly_chart(style_figure(trend_fig, 420), use_container_width=True)

    selected_store = st.selectbox("제품 구성 분석 매장", store_order, key="mealdo_store_sales_product_store")
    store_products = (
        frame.loc[frame["store"] == selected_store]
        .groupby("product_name", as_index=False).agg(sales=("sales", "sum"), quantity=("quantity", "sum"))
        .nlargest(10, "sales").sort_values("sales")
    )
    store_products["sales_million"] = (store_products["sales"] / 1_000_000).round(1)
    section_title(f"{selected_store} 순매출 TOP 10 제품", "백만원, EA")
    product_fig = px.bar(
        store_products, x="sales_million", y="product_name", orientation="h", color="quantity",
        labels={"sales_million": "순매출액", "product_name": "제품명", "quantity": "판매수량(EA)"},
        color_continuous_scale=[[0, BREAD_CREAM], [1, BREAD_PRIMARY]],
    )
    st.plotly_chart(style_figure(product_fig, 430), use_container_width=True)

    detail = store_summary.rename(columns={
        "store": "매장명", "sales_million": "당기순매출(백만원)",
        "previous_sales_million": "직전기간순매출(백만원)",
        "sales_share": "순매출비중", "quantity": "판매수량", "products": "판매제품수",
        "average_item_price": "평균제품단가",
    })[["매장명", "당기순매출(백만원)", "직전기간순매출(백만원)", "순매출비중", "판매수량", "판매제품수", "평균제품단가"]]
    section_title("매장 상세 실적", "백만원, 원, EA, 종, %")
    st.dataframe(
        detail.sort_values("당기순매출(백만원)", ascending=False), hide_index=True, use_container_width=True,
        column_config={
            "당기순매출(백만원)": st.column_config.NumberColumn(format="%,.1f"),
            "직전기간순매출(백만원)": st.column_config.NumberColumn(format="%,.1f"),
            "순매출비중": st.column_config.NumberColumn(format="%,.1f%%"),
            "판매수량": st.column_config.NumberColumn(format="%,.0f"),
            "판매제품수": st.column_config.NumberColumn(format="%,.0f"),
            "평균제품단가": st.column_config.NumberColumn(format="₩ %,.1f"),
        },
    )


def render_mealdo_lifecycle_dashboard(frame: pd.DataFrame, waste: pd.DataFrame) -> None:
    """제품 출시 이후 판매 흐름과 지속성을 살펴보는 밀도 제품 화면입니다."""
    products = sorted(frame["product_name"].dropna().unique())
    selected_product = st.selectbox("분석 제품", products, key="mealdo_lifecycle_product")
    product_frame = frame.loc[frame["product_name"] == selected_product].copy()
    product_codes = set(product_frame["product_code"])
    product_waste = waste.loc[waste["product_code"].isin(product_codes)].copy() if not waste.empty else waste.copy()
    # 원장 행의 존재가 아니라 실제 양수 판매수량이 발생한 날짜만 판매일로 봅니다.
    sales_activity = product_frame.loc[product_frame["quantity"] > 0]
    if sales_activity.empty:
        sales_activity = product_frame.loc[product_frame["sales"] > 0]
    if sales_activity.empty:
        sales_activity = product_frame
    first_sale_date = sales_activity["date"].min()
    last_sale_date = sales_activity["date"].max()
    elapsed_days = max(1, (last_sale_date - first_sale_date).days + 1)
    active_days = sales_activity["date"].nunique()
    product_waste_quantity = product_waste["waste_quantity"].sum() if not product_waste.empty else 0
    product_waste_amount = product_waste["waste_amount"].sum() if not product_waste.empty else 0
    product_disposal_rate = disposal_rate(product_frame["quantity"].sum(), product_waste_quantity)

    cols = st.columns(5)
    with cols[0]:
        with st.container(key="mealdo_first_sale_metric"):
            st.metric("최초 판매일", first_sale_date.strftime("%Y.%m.%d"),
                      help=f"조회 데이터 기준 최초 판매일: {first_sale_date:%Y-%m-%d}")
    cols[1].metric("판매 발생일", f"{active_days:,}일", help="판매수량이 0보다 큰 날짜 수입니다.")
    cols[2].metric("누적 판매수량", f"{product_frame['quantity'].sum():,.0f} EA")
    cols[3].metric("판매 매장", f"{product_frame['store'].nunique():,}개")
    cols[4].metric("폐기율", f"{product_disposal_rate:,.1f}%",
                   help="폐기수량 ÷ (판매수량 + 폐기수량) × 100")

    st.markdown(
        f'<div class="insight-box"><b>{selected_product}</b>은 조회 데이터 기준 '
        f'최초 판매일부터 최종 판매일까지 <b>{elapsed_days:,}일</b>의 기간 중 '
        f'실제로 판매수량이 발생한 날은 <b>{active_days:,}일</b>입니다. 실제 출시일 컬럼이 추가되면 '
        'D+7·D+14·D+30 기준 제품 간 비교가 가능해집니다.</div>',
        unsafe_allow_html=True,
    )

    daily = product_frame.groupby("date", as_index=False).agg(
        sales=("sales", "sum"), quantity=("quantity", "sum")
    ).set_index("date")
    full_dates = pd.date_range(product_frame["date"].min(), product_frame["date"].max(), freq="D")
    daily = daily.reindex(full_dates, fill_value=0).rename_axis("date").reset_index()
    daily["sales_million"] = (daily["sales"] / 1_000_000).round(1)
    daily["quantity_ma7"] = daily["quantity"].rolling(7, min_periods=1).mean().round(1)
    if not product_waste.empty:
        daily_waste = product_waste.groupby("date")["waste_quantity"].sum()
        daily["waste_quantity"] = daily["date"].map(daily_waste).fillna(0)
    else:
        daily["waste_quantity"] = 0
    daily["waste_rate"] = np.where(
        daily["quantity"] + daily["waste_quantity"] == 0,
        0,
        daily["waste_quantity"] / (daily["quantity"] + daily["waste_quantity"]) * 100,
    ).round(1)

    section_title("제품 판매 Lifecycle", "EA, 백만원")
    lifecycle_fig = go.Figure()
    lifecycle_fig.add_bar(
        x=daily["date"], y=daily["waste_quantity"], name="폐기수량",
        marker_color="#D95C5C", hovertemplate="%{x|%Y-%m-%d}<br>폐기수량: %{y:,.1f} EA<extra></extra>",
    )
    lifecycle_fig.add_bar(
        x=daily["date"], y=daily["quantity"], name="판매수량",
        marker_color=BREAD_PRIMARY, hovertemplate="%{x|%Y-%m-%d}<br>판매수량: %{y:,.1f} EA<extra></extra>",
    )
    lifecycle_fig.add_scatter(
        x=daily["date"], y=daily["quantity_ma7"], name="7일 이동평균",
        mode="lines", line=dict(color=BREAD_ACCENT, width=3),
        hovertemplate="%{x|%Y-%m-%d}<br>7일 평균: %{y:,.1f} EA<extra></extra>",
    )
    lifecycle_fig.update_xaxes(title_text="일자")
    lifecycle_fig.update_yaxes(title_text="판매수량(EA)")
    lifecycle_fig.update_layout(barmode="group")
    st.plotly_chart(style_figure(lifecycle_fig, 410), use_container_width=True)

    left, right = st.columns(2)
    with left:
        section_title("매장별 누적 판매수량", "EA")
        store_quantity = product_frame.groupby("store", as_index=False)["quantity"].sum().nlargest(15, "quantity").sort_values("quantity")
        fig = px.bar(store_quantity, x="quantity", y="store", orientation="h",
                     labels={"quantity": "판매수량(EA)", "store": "매장명"},
                     color_discrete_sequence=[BREAD_PRIMARY])
        st.plotly_chart(style_figure(fig, 400), use_container_width=True)
    with right:
        section_title("일별 폐기율 추이", "%")
        waste_rate_fig = px.line(
            daily, x="date", y="waste_rate", markers=True,
            labels={"date": "일자", "waste_rate": "폐기율(%)"},
            color_discrete_sequence=["#D95C5C"],
        )
        waste_rate_fig.update_traces(hovertemplate="%{x|%Y-%m-%d}<br>폐기율: %{y:,.1f}%<extra></extra>")
        st.plotly_chart(style_figure(waste_rate_fig, 400), use_container_width=True)

    if not product_waste.empty:
        section_title("제품 폐기 사유", "EA, 백만원")
        reason_detail = (
            product_waste.groupby("waste_reason", as_index=False)
            .agg(폐기수량=("waste_quantity", "sum"), 폐기비용=("waste_amount", "sum"))
            .rename(columns={"waste_reason": "폐기사유"})
            .sort_values("폐기수량", ascending=False)
        )
        reason_detail["폐기비용"] = reason_detail["폐기비용"] / 1_000_000
        st.dataframe(
            reason_detail, hide_index=True, use_container_width=True,
            column_config={
                "폐기수량": st.column_config.NumberColumn(format="%,.0f"),
                "폐기비용": st.column_config.NumberColumn(format="%,.1f"),
            },
        )


def render_mealdo_store_diagnostic_dashboard(frame: pd.DataFrame, waste: pd.DataFrame) -> None:
    """선택 매장의 제품별 판매와 폐기 현황을 진단합니다."""
    stores = sorted(frame["store"].dropna().unique())
    selected_store = st.selectbox("분석 매장", stores, key="mealdo_diagnostic_store")
    store_frame = frame.loc[frame["store"] == selected_store].copy()
    store_waste = waste.loc[waste["store"] == selected_store].copy() if not waste.empty else waste.copy()

    product_summary = store_frame.groupby(["product_code", "product_name"], as_index=False).agg(
        sales=("sales", "sum"), sales_quantity=("quantity", "sum"), sales_days=("date", "nunique")
    )
    if not store_waste.empty:
        waste_summary = store_waste.groupby("product_code", as_index=False).agg(
            waste_quantity=("waste_quantity", "sum"), waste_amount=("waste_amount", "sum")
        )
        product_summary = product_summary.merge(waste_summary, on="product_code", how="left")
    else:
        product_summary["waste_quantity"] = 0
        product_summary["waste_amount"] = 0
    product_summary[["waste_quantity", "waste_amount"]] = product_summary[["waste_quantity", "waste_amount"]].fillna(0)
    product_summary["waste_rate"] = np.where(
        product_summary["sales_quantity"] + product_summary["waste_quantity"] == 0,
        0,
        product_summary["waste_quantity"]
        / (product_summary["sales_quantity"] + product_summary["waste_quantity"]) * 100,
    ).round(1)
    product_summary["sales_million"] = (product_summary["sales"] / 1_000_000).round(1)

    total_sales_quantity = product_summary["sales_quantity"].sum()
    total_waste_quantity = product_summary["waste_quantity"].sum()
    total_waste_amount = product_summary["waste_amount"].sum()
    cols = st.columns(4)
    cols[0].metric("매장 순매출", million_won(product_summary["sales"].sum()), help="부가세 포함 실매출 ÷ 1.1")
    cols[1].metric("판매수량", f"{total_sales_quantity:,.0f} EA")
    cols[2].metric("폐기비용", million_won(total_waste_amount))
    cols[3].metric("폐기율", f"{disposal_rate(total_sales_quantity, total_waste_quantity):,.1f}%",
                   help="폐기수량 ÷ (판매수량 + 폐기수량) × 100")

    waste_products = product_summary.loc[product_summary["waste_quantity"] > 0]
    if not waste_products.empty:
        highest_waste_product = waste_products.sort_values(
            ["waste_rate", "waste_quantity"], ascending=False
        ).iloc[0]
        st.markdown(
            f'<div class="insight-box"><b>{selected_store}</b>에서 폐기율이 가장 높은 제품은 '
            f'<b>{highest_waste_product["product_name"]}</b>이며, 폐기율 '
            f'<b>{highest_waste_product["waste_rate"]:,.1f}%</b>, 폐기수량 '
            f'<b>{highest_waste_product["waste_quantity"]:,.0f} EA</b>입니다.</div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns(2)
    with left:
        section_title("제품별 폐기율 TOP 10", "%, EA")
        waste_top = product_summary.loc[product_summary["waste_quantity"] > 0].nlargest(
            10, "waste_rate"
        ).sort_values("waste_rate")
        waste_rate_fig = px.bar(
            waste_top, x="waste_rate", y="product_name", orientation="h",
            color="waste_rate", hover_data={"waste_quantity": ":,.0f", "sales_quantity": ":,.0f"},
            labels={"waste_rate": "폐기율(%)", "product_name": "제품명",
                    "waste_quantity": "폐기수량(EA)", "sales_quantity": "판매수량(EA)"},
            color_continuous_scale=[[0, "#F8D7D7"], [1, "#D95C5C"]],
        )
        waste_rate_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(waste_rate_fig, 420), use_container_width=True)
    with right:
        section_title("제품 판매수량 TOP 10", "EA")
        sales_top = product_summary.nlargest(10, "sales_quantity").sort_values("sales_quantity")
        sales_fig = px.bar(
            sales_top, x="sales_quantity", y="product_name", orientation="h",
            labels={"sales_quantity": "판매수량(EA)", "product_name": "제품명"},
            color_discrete_sequence=[BREAD_PRIMARY],
        )
        st.plotly_chart(style_figure(sales_fig, 420), use_container_width=True)

    # 조회기간의 모든 날짜를 포함해 매출·폐기가 없었던 날도 0으로 반영합니다.
    weekday_order = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_map = dict(enumerate(weekday_order))
    full_date_index = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D")
    store_sales_by_date = store_frame.groupby("date")["quantity"].sum().rename("sales_quantity")
    store_waste_by_date = (
        store_waste.groupby("date")["waste_quantity"].sum().rename("waste_quantity")
        if not store_waste.empty else pd.Series(dtype=float, name="waste_quantity")
    )
    weekday_daily = (
        pd.concat([store_sales_by_date, store_waste_by_date], axis=1)
        .reindex(full_date_index, fill_value=0)
        .fillna(0)
        .rename_axis("date")
        .reset_index()
    )
    weekday_daily["weekday"] = weekday_daily["date"].dt.dayofweek.map(weekday_map)
    weekday_summary = (
        weekday_daily.groupby("weekday", as_index=False)
        .agg(
            days=("date", "size"),
            sales_quantity=("sales_quantity", "sum"),
            waste_quantity=("waste_quantity", "sum"),
            average_sales_quantity=("sales_quantity", "mean"),
            average_waste_quantity=("waste_quantity", "mean"),
        )
        .set_index("weekday")
        .reindex(weekday_order)
        .fillna(0)
        .reset_index()
    )
    weekday_summary["waste_rate"] = np.where(
        weekday_summary["sales_quantity"] + weekday_summary["waste_quantity"] == 0,
        0,
        weekday_summary["waste_quantity"]
        / (weekday_summary["sales_quantity"] + weekday_summary["waste_quantity"]) * 100,
    ).round(1)

    section_title("요일별 판매 · 폐기 분석", "EA/일, %")
    weekday_left, weekday_right = st.columns([1.35, 1])
    with weekday_left:
        weekday_quantity_fig = go.Figure()
        weekday_quantity_fig.add_bar(
            x=weekday_summary["weekday"], y=weekday_summary["average_sales_quantity"],
            name="일평균 판매수량", marker_color=BREAD_PRIMARY,
            text=weekday_summary["average_sales_quantity"].map(lambda value: f"{value:,.1f}"),
            textposition="outside",
            hovertemplate="%{x}요일<br>일평균 판매: %{y:,.1f} EA<extra></extra>",
        )
        weekday_quantity_fig.add_bar(
            x=weekday_summary["weekday"], y=weekday_summary["average_waste_quantity"],
            name="일평균 폐기수량", marker_color="#D95C5C",
            text=weekday_summary["average_waste_quantity"].map(lambda value: f"{value:,.1f}"),
            textposition="outside",
            hovertemplate="%{x}요일<br>일평균 폐기: %{y:,.1f} EA<extra></extra>",
        )
        weekday_quantity_fig.update_layout(barmode="group")
        weekday_quantity_fig.update_xaxes(title_text="요일", categoryorder="array", categoryarray=weekday_order)
        weekday_quantity_fig.update_yaxes(title_text="일평균 수량(EA)")
        st.plotly_chart(style_figure(weekday_quantity_fig, 390), use_container_width=True)
    with weekday_right:
        weekday_rate_fig = px.bar(
            weekday_summary, x="weekday", y="waste_rate", color="waste_rate",
            text="waste_rate", labels={"weekday": "요일", "waste_rate": "폐기율(%)"},
            color_continuous_scale=[[0, "#F8D7D7"], [1, "#D95C5C"]],
            category_orders={"weekday": weekday_order},
        )
        weekday_rate_fig.update_traces(
            texttemplate="%{text:,.1f}%", textposition="outside",
            hovertemplate="%{x}요일<br>폐기율: %{y:,.1f}%<extra></extra>",
        )
        weekday_rate_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(weekday_rate_fig, 390), use_container_width=True)

    peak_sales_weekday = weekday_summary.nlargest(1, "average_sales_quantity").iloc[0]
    peak_waste_weekday = weekday_summary.nlargest(1, "waste_rate").iloc[0]
    st.markdown(
        f'<div class="insight-box"><b>{selected_store}</b>의 일평균 판매수량은 '
        f'<b>{peak_sales_weekday["weekday"]}요일</b>이 '
        f'<b>{peak_sales_weekday["average_sales_quantity"]:,.1f} EA</b>로 가장 높습니다. '
        f'폐기율은 <b>{peak_waste_weekday["weekday"]}요일</b>이 '
        f'<b>{peak_waste_weekday["waste_rate"]:,.1f}%</b>로 가장 높습니다.</div>',
        unsafe_allow_html=True,
    )

    product_options = product_summary.sort_values("waste_rate", ascending=False)["product_name"].tolist()
    selected_product = st.selectbox("추이 분석 제품", product_options, key="mealdo_diagnostic_product")
    selected_codes = set(product_summary.loc[product_summary["product_name"] == selected_product, "product_code"])
    product_sales_daily = (
        store_frame.loc[store_frame["product_code"].isin(selected_codes)]
        .groupby("date")["quantity"].sum().rename("sales_quantity")
    )
    product_waste_daily = (
        store_waste.loc[store_waste["product_code"].isin(selected_codes)]
        .groupby("date")["waste_quantity"].sum().rename("waste_quantity")
        if not store_waste.empty else pd.Series(dtype=float, name="waste_quantity")
    )
    daily_index = pd.date_range(store_frame["date"].min(), store_frame["date"].max(), freq="D")
    daily_product = pd.concat([product_sales_daily, product_waste_daily], axis=1).reindex(daily_index, fill_value=0).fillna(0)
    daily_product.index.name = "date"
    daily_product = daily_product.reset_index()
    daily_product["sales_ma7"] = daily_product["sales_quantity"].rolling(7, min_periods=1).mean().round(1)

    section_title(f"{selected_product} 판매 · 폐기 추이", "EA")
    trend_fig = go.Figure()
    trend_fig.add_bar(x=daily_product["date"], y=daily_product["sales_quantity"], name="판매수량",
                      marker_color=BREAD_PRIMARY, hovertemplate="%{x|%Y-%m-%d}<br>판매: %{y:,.1f} EA<extra></extra>")
    trend_fig.add_bar(x=daily_product["date"], y=daily_product["waste_quantity"], name="폐기수량",
                      marker_color="#D95C5C", hovertemplate="%{x|%Y-%m-%d}<br>폐기: %{y:,.1f} EA<extra></extra>")
    trend_fig.add_scatter(x=daily_product["date"], y=daily_product["sales_ma7"], name="판매 7일 이동평균",
                          mode="lines", line=dict(color=BREAD_ACCENT, width=3),
                          hovertemplate="%{x|%Y-%m-%d}<br>7일 평균: %{y:,.1f} EA<extra></extra>")
    trend_fig.update_layout(barmode="group")
    trend_fig.update_xaxes(title_text="일자")
    trend_fig.update_yaxes(title_text="수량(EA)")
    st.plotly_chart(style_figure(trend_fig, 420), use_container_width=True)

    if not store_waste.empty:
        section_title("매장 폐기 사유 구성", "EA, 백만원")
        reason_summary = store_waste.groupby("waste_reason", as_index=False).agg(
            폐기수량=("waste_quantity", "sum"), 폐기비용=("waste_amount", "sum")
        ).rename(columns={"waste_reason": "폐기사유"}).sort_values("폐기수량", ascending=False)
        reason_summary["폐기비용"] = reason_summary["폐기비용"] / 1_000_000
        st.dataframe(
            reason_summary, hide_index=True, use_container_width=True,
            column_config={
                "폐기수량": st.column_config.NumberColumn(format="%,.0f"),
                "폐기비용": st.column_config.NumberColumn(format="%,.1f"),
            },
        )

    detail = product_summary.rename(columns={
        "product_name": "제품명", "sales_million": "순매출(백만원)", "sales_quantity": "판매수량",
        "waste_quantity": "폐기수량", "waste_amount": "폐기비용(백만원)", "waste_rate": "폐기율",
    })[["제품명", "순매출(백만원)", "판매수량", "폐기수량", "폐기비용(백만원)", "폐기율"]]
    detail["폐기비용(백만원)"] = detail["폐기비용(백만원)"] / 1_000_000
    section_title("매장 제품 상세 실적", "EA, 백만원, %")
    st.dataframe(
        detail.sort_values(["폐기율", "폐기수량"], ascending=False), hide_index=True, use_container_width=True,
        column_config={
            "순매출(백만원)": st.column_config.NumberColumn(format="%,.1f"),
            "판매수량": st.column_config.NumberColumn(format="%,.0f"),
            "폐기수량": st.column_config.NumberColumn(format="%,.0f"),
            "폐기비용(백만원)": st.column_config.NumberColumn(format="%,.1f"),
            "폐기율": st.column_config.NumberColumn(format="%,.1f%%"),
        },
    )


def render_mealdo_store_product_dashboard(frame: pd.DataFrame, waste: pd.DataFrame) -> None:
    """제품별 매장 운영 성과와 향후 폐기 분석 위치를 제공하는 화면입니다."""
    products = sorted(frame["product_name"].dropna().unique())
    selected_product = st.selectbox("분석 제품", products, key="mealdo_store_product")
    product_frame = frame.loc[frame["product_name"] == selected_product]
    product_codes = set(product_frame["product_code"])
    product_waste = waste.loc[waste["product_code"].isin(product_codes)].copy() if not waste.empty else waste.copy()
    store_summary = product_frame.groupby("store", as_index=False).agg(
        sales=("sales", "sum"), quantity=("quantity", "sum"), active_days=("date", "nunique")
    )
    store_summary["sales_million"] = (store_summary["sales"] / 1_000_000).round(1)
    store_summary["daily_quantity"] = np.where(
        store_summary["active_days"] == 0, 0, store_summary["quantity"] / store_summary["active_days"]
    ).round(1)
    if not product_waste.empty:
        waste_by_store = product_waste.groupby("store", as_index=False).agg(
            waste_quantity=("waste_quantity", "sum"), waste_amount=("waste_amount", "sum")
        )
        store_summary = store_summary.merge(waste_by_store, on="store", how="left")
    else:
        store_summary["waste_quantity"] = 0
        store_summary["waste_amount"] = 0
    store_summary[["waste_quantity", "waste_amount"]] = store_summary[["waste_quantity", "waste_amount"]].fillna(0)
    store_summary["waste_rate"] = np.where(
        store_summary["quantity"] + store_summary["waste_quantity"] == 0,
        0,
        store_summary["waste_quantity"] / (store_summary["quantity"] + store_summary["waste_quantity"]) * 100,
    ).round(1)

    cols = st.columns(4)
    cols[0].metric("취급 매장", f"{store_summary['store'].nunique():,}개")
    cols[1].metric("누적 판매수량", f"{store_summary['quantity'].sum():,.0f} EA")
    cols[2].metric("매장당 평균수량", f"{store_summary['quantity'].mean():,.1f} EA")
    cols[3].metric("폐기율", f"{disposal_rate(store_summary['quantity'].sum(), store_summary['waste_quantity'].sum()):,.1f}%",
                   help="폐기수량 ÷ (판매수량 + 폐기수량) × 100")

    section_title("매장별 판매량 × 폐기율 포지션", "EA/일, %")
    fig = px.scatter(
        store_summary, x="daily_quantity", y="waste_rate", size="quantity", color="waste_rate", hover_name="store",
        hover_data={"sales_million": ":,.1f", "waste_quantity": ":,.0f"},
        labels={"daily_quantity": "일평균 판매수량(EA)", "waste_rate": "폐기율(%)",
                "quantity": "누적 판매수량", "sales_million": "순매출액(백만원)", "waste_quantity": "폐기수량(EA)"},
        color_continuous_scale=[[0, BREAD_CREAM], [1, "#D95C5C"]], size_max=48,
    )
    st.plotly_chart(style_figure(fig, 430), use_container_width=True)

    left, right = st.columns(2)
    with left:
        section_title("매장별 제품 판매 순위", "EA")
        rank = store_summary.nlargest(15, "quantity").sort_values("quantity")
        rank_fig = px.bar(rank, x="quantity", y="store", orientation="h",
                          labels={"quantity": "누적 판매수량(EA)", "store": "매장명"},
                          color_discrete_sequence=[BREAD_PRIMARY])
        st.plotly_chart(style_figure(rank_fig, 410), use_container_width=True)
    with right:
        section_title("매장별 폐기율 TOP 15", "%")
        waste_rank = store_summary.nlargest(15, "waste_rate").sort_values("waste_rate")
        waste_fig = px.bar(
            waste_rank, x="waste_rate", y="store", orientation="h",
            labels={"waste_rate": "폐기율(%)", "store": "매장명"},
            color="waste_rate", color_continuous_scale=[[0, "#F8D7D7"], [1, "#D95C5C"]],
        )
        waste_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(waste_fig, 410), use_container_width=True)


def render_paul_store_dashboard(frame: pd.DataFrame) -> None:
    start_date, end_date = frame["date"].min(), frame["date"].max()
    store_sales = frame.groupby("store", as_index=False)["sales"].sum()
    store_sales["sales_million"] = (store_sales["sales"] / 1_000_000).round(1)
    daily = frame.groupby("date", as_index=False)["sales"].sum()
    daily["sales_million"] = (daily["sales"] / 1_000_000).round(1)
    active_store_count = store_sales.loc[store_sales["sales"] != 0, "store"].nunique()

    cols = st.columns(4)
    cols[0].metric("총 매출", won(frame["sales"].sum()))
    cols[1].metric("전체 매장", f"{frame['store'].nunique():,}개")
    cols[2].metric("매출 발생 매장", f"{active_store_count:,}개")
    cols[3].metric("매장당 평균 매출", won(store_sales["sales"].mean()))

    top_store = store_sales.nlargest(1, "sales").iloc[0]
    st.markdown(
        f'<div class="insight-box">선택 기간 매출 1위 매장은 <b>{top_store["store"]}</b>로 '
        f'<b>{won(top_store["sales"])}</b>을 기록했으며, 전체 매출의 '
        f'<b>{top_store["sales"] / frame["sales"].sum() * 100 if frame["sales"].sum() else 0:.1f}%</b>를 차지합니다.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.2, 1])
    with left:
        section_title("일별 매출 흐름", "백만원")
        fig = px.bar(daily, x="date", y="sales_million", color_discrete_sequence=[PAUL_PRIMARY],
                     labels={"date": "일자", "sales_million": "매출(백만원)"})
        st.plotly_chart(style_figure(fig, 390), use_container_width=True)
    with right:
        section_title("매장 매출 TOP 15", "백만원")
        top_stores = store_sales.nlargest(15, "sales").sort_values("sales")
        fig = px.bar(top_stores, x="sales_million", y="store", orientation="h", color="sales_million",
                     color_continuous_scale=[[0, PAUL_CREAM], [1, PAUL_PRIMARY]],
                     labels={"sales_million": "매출액", "store": "매장명"})
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_figure(fig, 390), use_container_width=True)

    section_title("상위 매장 일별 매출 히트맵", "백만원")
    top_store_names = store_sales.nlargest(15, "sales")["store"]
    heat = frame[frame["store"].isin(top_store_names)].pivot_table(
        index="store", columns="date", values="sales", aggfunc="sum", fill_value=0
    ).div(1_000_000).round(1)
    heat.columns = [date_value.strftime("%m/%d") for date_value in heat.columns]
    heat_fig = px.imshow(heat, aspect="auto", color_continuous_scale=PAUL_SCALE,
                         labels={"x": "일자", "y": "매장", "color": "매출(백만원)"})
    st.plotly_chart(style_figure(heat_fig, 480), use_container_width=True)

    detail = store_sales.sort_values("sales", ascending=False).rename(columns={"store": "매장명", "sales": "매출"})
    section_title("매장 상세 실적", "원")
    st.dataframe(detail, hide_index=True, use_container_width=True,
                 column_config={"매출": st.column_config.NumberColumn(format="₩ %,.0f")})


with st.sidebar:
    st.markdown('<div class="brand">Brand Sales</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Sales Intelligence Platform</div>', unsafe_allow_html=True)
    selected_brand = st.segmented_control(
        "브랜드", ["데르뜨", "밀도"], default="데르뜨", key="brand_navigation",
        on_change=mark_brand_navigation_changed,
    )

if st.session_state.pop("_brand_navigation_changed", False):
    st.rerun()

if selected_brand == "밀도":
    store_data_dir = Path(__file__).resolve().parent / "data" / "mealdo"
    store_csv_paths = [
        store_data_dir / "밀도_일별매출_통합.csv",
        store_data_dir / "밀도_폐기데이터_통합.csv",
        store_data_dir / "폴바셋_일별매출_통합.csv",
    ]
    store_data_version = tuple(
        (path.name, path.stat().st_mtime_ns, path.stat().st_size)
        for path in store_csv_paths if path.exists()
    )
    try:
        mealdo_data, paul_data, mealdo_waste_data = load_store_sales_data(store_data_version)
    except Exception as exc:
        st.error(f"매장 데이터를 불러오지 못했습니다: {exc}")
        st.stop()

    mealdo_nav_labels = {
        "밀도 Sales Overview": "01  종합 Sales Overview",
        "밀도 매장 Sales 분석": "02  매장 Sales 분석",
        "밀도 제품 Lifecycle": "03  제품 Lifecycle 분석",
        "밀도 매장 상세 분석": "04  매장 폐기·판매 분석",
        "밀도 매장×제품 분석": "05  매장 × 제품 운영 분석",
    }
    paul_nav_labels = {"폴바셋 Sales Overview": "01  Sales Overview"}
    valid_store_pages = set(mealdo_nav_labels) | set(paul_nav_labels)
    if st.session_state.get("store_selected_page") not in valid_store_pages:
        st.session_state["store_selected_page"] = "밀도 Sales Overview"
    selected_store_page = st.session_state["store_selected_page"]
    sidebar_store_brand = "밀도" if selected_store_page in mealdo_nav_labels else "폴바셋"
    sidebar_store_subtitle = (
        "Store Sales Intelligence"
        if selected_store_page in mealdo_nav_labels
        else "Cafe Sales Intelligence"
    )

    with st.sidebar:
        st.markdown(f'<div class="brand">{sidebar_store_brand}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="brand-sub">{sidebar_store_subtitle}</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown('<div class="nav-title">STORE ANALYTICS</div>', unsafe_allow_html=True)
        with st.expander(
            "밀도 Sales Analytics",
            expanded=selected_store_page in mealdo_nav_labels,
        ):
            with st.container(key="store_nav_mealdo"):
                for page_name, page_label in mealdo_nav_labels.items():
                    if st.button(
                        page_label,
                        key=f"store_nav_{page_name}",
                        type="primary" if selected_store_page == page_name else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state["store_selected_page"] = page_name
                        st.rerun()

        with st.expander(
            "폴바셋 Sales Analytics",
            expanded=selected_store_page in paul_nav_labels,
        ):
            with st.container(key="store_nav_paul"):
                for page_name, page_label in paul_nav_labels.items():
                    if st.button(
                        page_label,
                        key=f"store_nav_{page_name}",
                        type="primary" if selected_store_page == page_name else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state["store_selected_page"] = page_name
                        st.rerun()

    is_mealdo_page = selected_store_page.startswith("밀도")
    if is_mealdo_page:
        st.markdown(
            """
            <div class="mealdo-theme-marker"></div>
            <style>
                .mealdo-theme-marker { display: none; }
                .stApp:has(.mealdo-theme-marker) { background: #FFFCF7; }
                .stApp:has(.mealdo-theme-marker) .brand,
                .stApp:has(.mealdo-theme-marker) .section-title,
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetricValue"] {
                    color: #6B4226;
                }
                .stApp:has(.mealdo-theme-marker) .brand-sub,
                .stApp:has(.mealdo-theme-marker) .section-sub,
                .stApp:has(.mealdo-theme-marker) .section-unit,
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetricLabel"] {
                    color: #8A6A50;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetric"] {
                    background: #FFFFFF; border-color: #E8D6C3;
                    box-shadow: 0 3px 14px rgba(122, 78, 45, .06);
                    padding: 12px 15px; border-radius: 13px;
                    min-height: 112px; box-sizing: border-box;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetricLabel"] {
                    font-size: .78rem;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetricValue"] {
                    font-size: 1.55rem;
                }
                .stApp:has(.mealdo-theme-marker) .st-key-mealdo_first_sale_metric [data-testid="stMetricValue"] {
                    font-size: clamp(1.15rem, 1.3vw, 1.35rem);
                    white-space: nowrap;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stMetricDelta"] {
                    font-size: .72rem;
                }
                .stApp:has(.mealdo-theme-marker) .insight-box {
                    background: linear-gradient(90deg, #F7EBDD, #FFF9F1);
                    border-color: #DFC09D; color: #6B4B33;
                }
                .stApp:has(.mealdo-theme-marker) .insight-box b { color: #7A4E2D; }
                .stApp:has(.mealdo-theme-marker)
                [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_mealdo) {
                    background: rgba(255, 253, 249, .97);
                    border-bottom-color: #E4CFB8;
                    box-shadow: 0 8px 18px rgba(122, 78, 45, .07);
                }
                .stApp:has(.mealdo-theme-marker) .st-key-brand_navigation button[aria-pressed="true"],
                .stApp:has(.mealdo-theme-marker) .st-key-brand_navigation [data-testid="stBaseButton-segmented_controlActive"] {
                    background: #7A4E2D !important; border-color: #7A4E2D !important;
                    color: #FFFFFF !important;
                }
                .stApp:has(.mealdo-theme-marker) .st-key-brand_navigation button[aria-pressed="true"] p,
                .stApp:has(.mealdo-theme-marker) .st-key-brand_navigation [data-testid="stBaseButton-segmented_controlActive"] p {
                    color: #FFFFFF !important;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_mealdo) details {
                    border-color: #D9B995; background: #FFFDF9;
                    box-shadow: 0 3px 10px rgba(122, 78, 45, .07);
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_mealdo) summary {
                    background: #F7EBDD;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_mealdo) summary p {
                    color: #6B4226;
                }
                .stApp:has(.mealdo-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_mealdo) summary p span {
                    background: #E8D2BA !important; color: #7A4E2D !important;
                }
                .stApp:has(.mealdo-theme-marker) .st-key-store_nav_mealdo [data-testid="stBaseButton-primary"] {
                    background: #7A4E2D; border-color: #7A4E2D; color: #FFFFFF;
                }
                .stApp:has(.mealdo-theme-marker) .st-key-store_nav_mealdo [data-testid="stBaseButton-secondary"] {
                    background: #FFFFFF; border-color: #DFC09D; color: #6B4B33;
                }
                .stApp:has(.mealdo-theme-marker) .st-key-store_nav_mealdo [data-testid="stBaseButton-secondary"]:hover {
                    background: #F7EBDD; border-color: #B18455; color: #6B4226;
                }
                .stApp:has(.mealdo-theme-marker) .status-pill {
                    background: #F1E1CF; color: #7A4E2D;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="paul-theme-marker"></div>
            <style>
                .paul-theme-marker { display: none; }
                .stApp:has(.paul-theme-marker) { background: #FCFAF9; }
                .stApp:has(.paul-theme-marker) .brand,
                .stApp:has(.paul-theme-marker) .section-title,
                .stApp:has(.paul-theme-marker) [data-testid="stMetricValue"] {
                    color: #241C1A;
                }
                .stApp:has(.paul-theme-marker) .brand-sub,
                .stApp:has(.paul-theme-marker) .section-sub,
                .stApp:has(.paul-theme-marker) .section-unit,
                .stApp:has(.paul-theme-marker) [data-testid="stMetricLabel"] {
                    color: #765A56;
                }
                .stApp:has(.paul-theme-marker) [data-testid="stMetric"] {
                    background: #FFFFFF; border-color: #E2D2D4;
                    box-shadow: 0 3px 14px rgba(76, 24, 38, .06);
                }
                .stApp:has(.paul-theme-marker) .insight-box {
                    background: linear-gradient(90deg, #F7EAED, #FCF8F6);
                    border-color: #D8B5BE; color: #422C2D;
                }
                .stApp:has(.paul-theme-marker) .insight-box b { color: #8E1738; }
                .stApp:has(.paul-theme-marker)
                [data-testid="stLayoutWrapper"]:has(> .st-key-sticky_dashboard_header_mealdo) {
                    background: rgba(252, 250, 249, .97);
                    border-bottom-color: #D9C4C8;
                    box-shadow: 0 8px 18px rgba(76, 24, 38, .07);
                }
                .stApp:has(.paul-theme-marker) .st-key-brand_navigation button[aria-pressed="true"],
                .stApp:has(.paul-theme-marker) .st-key-brand_navigation [data-testid="stBaseButton-segmented_controlActive"] {
                    background: #8E1738 !important; border-color: #8E1738 !important;
                    color: #FFFFFF !important;
                }
                .stApp:has(.paul-theme-marker) .st-key-brand_navigation button[aria-pressed="true"] p,
                .stApp:has(.paul-theme-marker) .st-key-brand_navigation [data-testid="stBaseButton-segmented_controlActive"] p {
                    color: #FFFFFF !important;
                }
                .stApp:has(.paul-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_paul) details {
                    border-color: #CDA6AF; background: #FFFCFC;
                    box-shadow: 0 3px 10px rgba(76, 24, 38, .07);
                }
                .stApp:has(.paul-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_paul) summary {
                    background: #F7EAED;
                }
                .stApp:has(.paul-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_paul) summary p {
                    color: #4A242D;
                }
                .stApp:has(.paul-theme-marker) [data-testid="stExpander"]:has(.st-key-store_nav_paul) summary p span {
                    background: #E9CDD4 !important; color: #8E1738 !important;
                }
                .stApp:has(.paul-theme-marker) .st-key-store_nav_paul [data-testid="stBaseButton-primary"] {
                    background: #8E1738; border-color: #8E1738; color: #FFFFFF;
                }
                .stApp:has(.paul-theme-marker) .st-key-store_nav_paul [data-testid="stBaseButton-secondary"] {
                    background: #FFFFFF; border-color: #D8B5BE; color: #422C2D;
                }
                .stApp:has(.paul-theme-marker) .st-key-store_nav_paul [data-testid="stBaseButton-secondary"]:hover {
                    background: #F7EAED; border-color: #8E1738; color: #8E1738;
                }
                .stApp:has(.paul-theme-marker) .status-pill {
                    background: #E9CDD4; color: #8E1738;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
    source_data = mealdo_data if is_mealdo_page else paul_data
    if source_data.empty:
        st.warning(f"{selected_store_page}에 사용할 CSV 데이터가 없습니다.")
        st.stop()

    min_store_date = source_data["date"].min().date()
    max_store_date = source_data["date"].max().date()

    store_header_title = {
        "밀도 Sales Overview": "밀도 Store Sales Overview",
        "밀도 매장 Sales 분석": "밀도 Store Sales Analytics",
        "밀도 제품 Lifecycle": "밀도 Product Lifecycle",
        "밀도 매장 상세 분석": "밀도 Store Waste & Sales Diagnostics",
        "밀도 매장×제품 분석": "밀도 Store × Product Performance",
        "폴바셋 Sales Overview": "Paul Bassett Store Sales Overview",
    }[selected_store_page]
    store_header_description = {
        "밀도 Sales Overview": "매장과 제품 판매 흐름을 한눈에 확인합니다.",
        "밀도 매장 Sales 분석": "매장별 매출 규모와 비중, 직전 기간 대비 변화를 분석합니다.",
        "밀도 제품 Lifecycle": "제품 출시 이후 판매 추이와 생명주기를 분석합니다.",
        "밀도 매장 상세 분석": "매장별 제품 판매와 폐기 현황을 진단합니다.",
        "밀도 매장×제품 분석": "제품별 매장 성과와 운영 방향을 탐색합니다.",
        "폴바셋 Sales Overview": "폴바셋 매장별 일매출 성과를 분석합니다.",
    }[selected_store_page]
    with st.container(key="sticky_dashboard_header_mealdo"):
        store_header_left, store_header_right = st.columns([1, 1.35], vertical_alignment="center")
        with store_header_right:
            # 데르뜨 헤더와 동일한 위치에 조회 기간을 배치하고 우측 제어 영역은 비워 둡니다.
            store_date_columns = st.columns([1.3, 1])
            with store_date_columns[0]:
                selected_store_dates = st.date_input(
                    "조회 기간",
                    value=(min_store_date, max_store_date),
                    min_value=min_store_date,
                    max_value=max_store_date,
                    format="YYYY/MM/DD",
                    label_visibility="collapsed",
                    key="store_date_range",
                )
        with store_header_left:
            store_header_start = selected_store_dates[0] if len(selected_store_dates) >= 1 else min_store_date
            store_header_end = selected_store_dates[1] if len(selected_store_dates) >= 2 else store_header_start
            st.markdown(
                f'<div class="header-title-block">'
                f'<div class="brand">{store_header_title}</div>'
                f'<div class="brand-sub">{store_header_start:%Y.%m.%d} — {store_header_end:%Y.%m.%d} · '
                f'{store_header_description}</div></div>',
                unsafe_allow_html=True,
            )

    with st.sidebar:
        st.markdown("---")
        st.markdown("#### 상세 필터")
        store_options = sorted(source_data["store"].dropna().unique())
        store_filter_key = (
            "mealdo_filter_stores"
            if is_mealdo_page
            else "paul_filter_stores"
        )
        selected_stores = sidebar_filter_dropdown(
            "매장명", store_options, store_filter_key
        )

        if is_mealdo_page:
            category_options = sorted(source_data["category_large"].dropna().unique())
            selected_store_categories = sidebar_filter_dropdown(
                "대분류", category_options, "mealdo_filter_categories"
            )
        else:
            selected_store_categories = []

        st.markdown("---")
        st.markdown('<span class="status-pill">● CSV 데이터</span>', unsafe_allow_html=True)
        st.caption(f"통합 파일 {len(store_data_version):,}개 · 최종 데이터 {max_store_date:%Y.%m.%d}")

    if len(selected_store_dates) != 2:
        st.info("조회 시작일과 종료일을 선택해 주세요.")
        st.stop()
    store_start, store_end = map(pd.Timestamp, selected_store_dates)
    store_filtered = source_data[
        source_data["date"].between(store_start, store_end)
        & source_data["store"].isin(selected_stores)
    ].copy()
    if is_mealdo_page:
        store_filtered = store_filtered[
            store_filtered["category_large"].isin(selected_store_categories)
        ]

    previous_store_end = store_start - pd.Timedelta(days=1)
    previous_store_start = previous_store_end - (store_end - store_start)
    store_previous = source_data[
        source_data["date"].between(previous_store_start, previous_store_end)
        & source_data["store"].isin(selected_stores)
    ].copy()
    if is_mealdo_page:
        store_previous = store_previous[
            store_previous["category_large"].isin(selected_store_categories)
        ]

    if store_filtered.empty:
        st.warning("선택한 조건에 해당하는 매장 데이터가 없습니다.")
        st.stop()

    mealdo_product_pages = {
        "밀도 제품 Lifecycle",
        "밀도 매장 상세 분석",
        "밀도 매장×제품 분석",
    }
    if selected_store_page in mealdo_product_pages:
        store_filtered = store_filtered.loc[
            store_filtered["category_large"].astype(str).str.strip().ne("기타")
        ].copy()
        if store_filtered.empty:
            st.warning("대분류 '기타'를 제외하면 선택 조건에 해당하는 제품 데이터가 없습니다.")
            st.stop()

    if is_mealdo_page and not mealdo_waste_data.empty:
        selected_product_codes = set(store_filtered["product_code"])
        mealdo_waste_filtered = mealdo_waste_data[
            mealdo_waste_data["date"].between(store_start, store_end)
            & mealdo_waste_data["store"].isin(selected_stores)
            & mealdo_waste_data["product_code"].isin(selected_product_codes)
        ].copy()
    else:
        mealdo_waste_filtered = mealdo_waste_data.iloc[0:0].copy()

    if selected_store_page == "밀도 Sales Overview":
        render_mealdo_store_dashboard(store_filtered, mealdo_waste_filtered)
    elif selected_store_page == "밀도 매장 Sales 분석":
        render_mealdo_store_sales_dashboard(store_filtered, store_previous)
    elif selected_store_page == "밀도 제품 Lifecycle":
        render_mealdo_lifecycle_dashboard(store_filtered, mealdo_waste_filtered)
    elif selected_store_page == "밀도 매장 상세 분석":
        render_mealdo_store_diagnostic_dashboard(store_filtered, mealdo_waste_filtered)
    elif selected_store_page == "밀도 매장×제품 분석":
        render_mealdo_store_product_dashboard(store_filtered, mealdo_waste_filtered)
    else:
        render_paul_store_dashboard(store_filtered)
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
        key="dertte_navigation",
    )

default_end_date = data_max_date
default_start_date = default_end_date.replace(day=1)
available_months = sorted(data["date"].dt.to_period("M").unique())
header_title = {
    "채널 Sales Overview": "Channel Sales Overview",
    "채널 상세 Sales 분석": "Channel Performance Lab",
    "제품별 Sales Overview": "Product Sales Intelligence",
}[selected_page]
header_description = {
    "채널 Sales Overview": "데르뜨 채널별 매출 및 판매 현황",
    "채널 상세 Sales 분석": "채널과 매출처 성과를 교차 분석합니다.",
    "제품별 Sales Overview": "제품과 카테고리의 매출 기여도를 분석합니다.",
}[selected_page]

with st.container(key="sticky_dashboard_header_dertte"):
    header_left, header_right = st.columns([1, 1.35], vertical_alignment="center")
    with header_right:
        query_columns = st.columns([1.3, 1])
        if selected_page == "채널 Sales Overview":
            with query_columns[1]:
                frequency = st.segmented_control(
                    "집계 단위",
                    ["일간", "월간"],
                    default="일간",
                    label_visibility="collapsed",
                    key="dertte_frequency",
                )
        else:
            frequency = "일간"

        with query_columns[0]:
            if selected_page == "채널 Sales Overview" and frequency == "월간":
                selected_month = st.selectbox(
                    "조회 월",
                    available_months,
                    index=len(available_months) - 1,
                    format_func=lambda value: f"{value.year}년 {value.month:02d}월",
                    label_visibility="collapsed",
                    key="dertte_month",
                )
                selected_dates = (
                    max(selected_month.start_time.date(), data_min_date),
                    min(selected_month.end_time.date(), data_max_date),
                )
            else:
                selected_dates = st.date_input(
                    "조회 기간",
                    value=(default_start_date, default_end_date),
                    min_value=data_min_date,
                    max_value=data_max_date,
                    format="YYYY/MM/DD",
                    label_visibility="collapsed",
                    key="dertte_date_range",
                )

    with header_left:
        selected_header_start = selected_dates[0] if len(selected_dates) >= 1 else default_start_date
        selected_header_end = selected_dates[1] if len(selected_dates) >= 2 else selected_header_start
        st.markdown(
            f'<div class="header-title-block">'
            f'<div class="brand">{header_title}</div>'
            f'<div class="brand-sub">{selected_header_start:%Y.%m.%d} — {selected_header_end:%Y.%m.%d} · '
            f'{header_description}</div></div>',
            unsafe_allow_html=True,
        )

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
    selected_channels = sidebar_filter_dropdown(
        "Channel1_1", channel_options, "dertte_filter_channels"
    )

    channel_detail_options = sorted(
        data.loc[data["channel"].isin(selected_channels), "channel_detail"].dropna().unique()
    )
    selected_channel_details = sidebar_filter_dropdown(
        "Channel1_2", channel_detail_options, "dertte_filter_channel_details"
    )

    # 1차·2차 채널 선택에 따라 영업 기준 매출처 목록이 자동으로 달라집니다.
    account_options = sorted(
        data.loc[
            data["channel"].isin(selected_channels)
            & data["channel_detail"].isin(selected_channel_details),
            "account_name",
        ].dropna().unique()
    )
    selected_accounts = sidebar_filter_dropdown(
        "매출처명(영업기준)", account_options, "dertte_filter_accounts"
    )

    category_base = data[
        data["channel"].isin(selected_channels)
        & data["channel_detail"].isin(selected_channel_details)
        & data["account_name"].isin(selected_accounts)
    ]
    if selected_page == "채널 Sales Overview":
        large_options = sorted(category_base["category_large"].dropna().unique())
        selected_large = sidebar_filter_dropdown(
            "대분류", large_options, "dertte_filter_large"
        )

        middle_options = sorted(
            category_base.loc[category_base["category_large"].isin(selected_large), "category_middle"].dropna().unique()
        )
        selected_middle = sidebar_filter_dropdown(
            "중분류", middle_options, "dertte_filter_middle"
        )

        small_options = sorted(
            category_base.loc[
                category_base["category_large"].isin(selected_large)
                & category_base["category_middle"].isin(selected_middle),
                "category_small",
            ].dropna().unique()
        )
        selected_small = sidebar_filter_dropdown(
            "소분류", small_options, "dertte_filter_small"
        )

        detail_options = sorted(
            category_base.loc[
                category_base["category_large"].isin(selected_large)
                & category_base["category_middle"].isin(selected_middle)
                & category_base["category_small"].isin(selected_small),
                "category_detail",
            ].dropna().unique()
        )
        selected_detail = sidebar_filter_dropdown(
            "세분류", detail_options, "dertte_filter_detail"
        )
    elif selected_page == "제품별 Sales Overview":
        large_options = sorted(category_base["category_large"].dropna().unique())
        selected_large = sidebar_filter_dropdown(
            "MC 대분류", large_options, "dertte_filter_large"
        )
        selected_category_base = category_base[
            category_base["category_large"].isin(selected_large)
        ]
        selected_middle = sorted(selected_category_base["category_middle"].dropna().unique())
        selected_small = sorted(selected_category_base["category_small"].dropna().unique())
        selected_detail = sorted(selected_category_base["category_detail"].dropna().unique())
        frequency = "일간"
    else:
        selected_large = sorted(category_base["category_large"].dropna().unique())
        selected_middle = sorted(category_base["category_middle"].dropna().unique())
        selected_small = sorted(category_base["category_small"].dropna().unique())
        selected_detail = sorted(category_base["category_detail"].dropna().unique())
        frequency = "일간"

    st.markdown("---")
    st.markdown('<span class="status-pill">● CSV 데이터</span>', unsafe_allow_html=True)
    sales_csv_count = sum(path.name != "매출처_인코딩.csv" for path in csv_paths)
    unmatched_account_count = data.loc[data["channel"].eq("(미매핑)"), "account_name"].nunique()
    st.caption(f"매출 데이터 {sales_csv_count:,}개 · 매출처 매핑 1개")
    if unmatched_account_count:
        st.caption(f"⚠ 미매핑 매출처 {unmatched_account_count:,}개")
    st.caption(f"최종 데이터: {max_date:%Y.%m.%d}")


start_date, end_date = map(pd.Timestamp, selected_dates)
filtered = data[
    data["date"].between(start_date, end_date)
    & data["channel"].isin(selected_channels)
    & data["channel_detail"].isin(selected_channel_details)
    & data["account_name"].isin(selected_accounts)
    & data["category_large"].isin(selected_large)
    & data["category_middle"].isin(selected_middle)
    & data["category_small"].isin(selected_small)
    & data["category_detail"].isin(selected_detail)
].copy()

if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 조회기간과 별개로 누계 비교에 필요한 전체 이력을 현재 상세 필터로 제한합니다.
detail_history = data[
    data["channel"].isin(selected_channels)
    & data["channel_detail"].isin(selected_channel_details)
    & data["account_name"].isin(selected_accounts)
    & data["category_large"].isin(selected_large)
    & data["category_middle"].isin(selected_middle)
    & data["category_small"].isin(selected_small)
    & data["category_detail"].isin(selected_detail)
].copy()

reference_date = end_date.normalize()
current_month_start = reference_date.replace(day=1)
_, previous_month_end = comparison_period(reference_date, reference_date, "월간")
previous_month_start = previous_month_end.replace(day=1)
previous_year_end = reference_date - pd.DateOffset(years=1)
if reference_date.is_month_end:
    previous_year_end = previous_year_end + pd.offsets.MonthEnd(0)
previous_year_month_start = previous_year_end.replace(day=1)
previous_year_ytd_start = pd.Timestamp(year=previous_year_end.year, month=1, day=1)
current_year_ytd_start = pd.Timestamp(year=reference_date.year, month=1, day=1)

def sales_between(period_start: pd.Timestamp, period_end: pd.Timestamp) -> float:
    return float(detail_history.loc[
        detail_history["date"].between(period_start, period_end), "sales"
    ].sum())

daily_sales = sales_between(reference_date, reference_date)
previous_day = reference_date - pd.DateOffset(days=1)
previous_day_sales = sales_between(previous_day, previous_day)
current_month_sales = sales_between(current_month_start, reference_date)
previous_month_sales = sales_between(previous_month_start, previous_month_end)
previous_year_month_sales = sales_between(previous_year_month_start, previous_year_end)
current_year_ytd_sales = sales_between(current_year_ytd_start, reference_date)
previous_year_ytd_sales = sales_between(previous_year_ytd_start, previous_year_end)

def period_delta(current_value: float, comparison_value: float, label: str) -> str:
    if comparison_value == 0:
        return f"비교 데이터 없음 · {label}"
    return f"{percent_change(current_value, comparison_value):+.1f}% · {label}"

if selected_page == "채널 상세 Sales 분석":
    render_channel_detail(filtered, start_date, end_date)
    st.stop()

if selected_page == "제품별 Sales Overview":
    render_product_overview(filtered, start_date, end_date)
    st.stop()

with st.container(key="dertte_overview_kpis"):
    kpi_cols = st.columns(4)
    if frequency == "일간":
        kpi_cols[0].metric(
            f"일매출 {reference_date:%m/%d}", million_won_integer(daily_sales),
            period_delta(daily_sales, previous_day_sales, "전일 대비"),
            help=(
                f"{reference_date:%Y.%m.%d} 일매출을 {previous_day:%Y.%m.%d} 일매출과 비교합니다."
            ),
        )
        with kpi_cols[1].container(key="dertte_current_month_metric"):
            st.metric(
                f"당월 누계 {reference_date.month}월", million_won_integer(current_month_sales),
                "높이 맞춤",
                delta_color="off",
            )
        kpi_cols[2].metric(
            f"전월 누계 {previous_month_end.month}월", million_won_integer(previous_month_sales),
            period_delta(current_month_sales, previous_month_sales, "전월 대비"),
            help=(
                f"표시 금액은 {previous_month_start:%Y.%m.%d}-{previous_month_end:%Y.%m.%d} 누계입니다. "
                f"증감률은 당월 누계({current_month_start:%Y.%m.%d}-{reference_date:%Y.%m.%d})가 "
                "전월 누계보다 얼마나 증감했는지 계산합니다."
            ),
        )
        kpi_cols[3].metric(
            f"전년 동월 누계 {previous_year_end:%y년 %m월}", million_won_integer(previous_year_month_sales),
            period_delta(current_month_sales, previous_year_month_sales, "전년 대비"),
            help=(
                f"표시 금액은 {previous_year_month_start:%Y.%m.%d}-{previous_year_end:%Y.%m.%d} 누계입니다. "
                f"증감률은 당월 누계({current_month_start:%Y.%m.%d}-{reference_date:%Y.%m.%d})가 "
                "전년 동월 누계보다 얼마나 증감했는지 계산합니다."
            ),
        )
    else:
        kpi_cols[0].metric(
            f"월 매출 {reference_date.month}월", million_won_integer(current_month_sales),
            period_delta(current_month_sales, previous_month_sales, "전월 대비"),
        )
        kpi_cols[1].metric(
            f"당해 누계 매출 {reference_date.year}년", million_won_integer(current_year_ytd_sales),
            period_delta(current_year_ytd_sales, previous_year_ytd_sales, "전년 대비"),
        )
        kpi_cols[2].metric(
            f"전년 동월 매출 {previous_year_end:%y년 %m월}", million_won_integer(previous_year_month_sales),
            period_delta(
                current_month_sales,
                previous_year_month_sales,
                "전년 대비",
            ),
            help=(
                f"표시 금액은 {previous_year_month_start:%Y.%m.%d}-{previous_year_end:%Y.%m.%d} 매출입니다. "
                f"증감률은 당월({current_month_start:%Y.%m.%d}-{reference_date:%Y.%m.%d}) 매출이 "
                "전년 동월보다 얼마나 증감했는지 계산합니다."
            ),
        )
        kpi_cols[3].metric(
            f"전년 누계 매출 {previous_year_end.year}년", million_won_integer(previous_year_ytd_sales),
            period_delta(current_year_ytd_sales, previous_year_ytd_sales, "전년 대비"),
            help=(
                f"표시 금액은 {previous_year_ytd_start:%Y.%m.%d}-{previous_year_end:%Y.%m.%d} 누계입니다. "
                f"증감률은 당해 누계({current_year_ytd_start:%Y.%m.%d}-{reference_date:%Y.%m.%d})가 "
                "전년 같은 기간보다 얼마나 증감했는지 계산합니다."
            ),
        )

st.caption(
    f"누계 기준 · 당월 {current_month_start:%Y.%m.%d}-{reference_date:%Y.%m.%d} / "
    f"전월 {previous_month_start:%Y.%m.%d}-{previous_month_end:%Y.%m.%d} / "
    f"전년 동월 {previous_year_month_start:%Y.%m.%d}-{previous_year_end:%Y.%m.%d}"
)

section_title("기간별 판매 추이", "백만원")
trend_value_label = "매출액(백만원)"

# 누계 KPI·피벗은 선택일과 대응되는 동기간을 비교하지만, 추이 그래프의
# 전월·전년 동월 선은 이미 확정된 각 비교월의 말일까지 모두 보여줍니다.
previous_month_trend_end = previous_month_start + pd.offsets.MonthEnd(0)
previous_year_month_trend_end = previous_year_month_start + pd.offsets.MonthEnd(0)
previous_year_trend_end = pd.Timestamp(year=previous_year_end.year, month=12, day=31)
daily_trend_day_count = max(
    reference_date.days_in_month,
    previous_month_trend_end.days_in_month,
    previous_year_month_trend_end.days_in_month,
)


def comparison_trend_series(start, end, axis_kind, series_name, source_frame=None):
    """비교 기간의 실적을 일/월 번호 축에 맞춰 반환합니다."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    trend_source = detail_history if source_frame is None else source_frame
    period_rows = trend_source[
        trend_source["date"].between(start, end)
    ].copy()
    axis_values = (
        range(1, daily_trend_day_count + 1)
        if axis_kind == "day"
        else range(1, 13)
    )
    date_part = period_rows["date"].dt.day if axis_kind == "day" else period_rows["date"].dt.month
    values = period_rows.groupby(date_part)["sales"].sum().reindex(axis_values)

    # 판매가 없는 유효 기간은 0, 아직 도래하지 않았거나 존재하지 않는 날짜는 공백으로 둡니다.
    valid_until = end.day if axis_kind == "day" else end.month
    values.loc[values.index <= valid_until] = values.loc[values.index <= valid_until].fillna(0)
    values.loc[values.index > valid_until] = np.nan
    values = values / 1_000_000
    return pd.DataFrame({"axis_value": list(axis_values), "구분": series_name, "value": values.values})


if frequency == "월간":
    trend = pd.concat(
        [
            comparison_trend_series(
                current_year_ytd_start, reference_date, "month", f"당해 ({reference_date.year}년)"
            ),
            comparison_trend_series(
                previous_year_ytd_start,
                previous_year_trend_end,
                "month",
                f"전년 ({previous_year_end.year}년)",
            ),
        ],
        ignore_index=True,
    )
    trend_ticks = list(range(1, 13))
    trend_tick_text = [f"{month}월" for month in trend_ticks]
    trend_axis_label = "월"
else:
    trend = pd.concat(
        [
            comparison_trend_series(current_month_start, reference_date, "day", "당월"),
            comparison_trend_series(previous_month_start, previous_month_trend_end, "day", "전월"),
            comparison_trend_series(
                previous_year_month_start,
                previous_year_month_trend_end,
                "day",
                "전년 동월",
            ),
        ],
        ignore_index=True,
    )
    trend_ticks = list(range(1, daily_trend_day_count + 1))
    trend_tick_text = [f"{day}일" for day in trend_ticks]
    trend_axis_label = "일"

trend_fig = px.line(
    trend,
    x="axis_value",
    y="value",
    color="구분",
    symbol="구분",
    line_dash="구분",
    markers=True,
    color_discrete_sequence=["#0B3D91", "#2F80ED", "#7B61FF"],
    symbol_sequence=["circle", "square", "diamond"],
    line_dash_sequence=["solid", "dash", "dot"],
    labels={"axis_value": trend_axis_label, "value": trend_value_label},
)
trend_fig.update_traces(
    connectgaps=False,
    line_width=3,
    marker_size=8,
    marker_line_width=1.5,
    marker_line_color="#FFFFFF",
    hovertemplate=f"%{{fullData.name}}<br>{trend_axis_label} %{{x}}<br>{trend_value_label} %{{y:,.0f}}<extra></extra>",
)
trend_fig.update_layout(hovermode="x unified", legend_title_text="비교 기간")
trend_fig.update_xaxes(
    tickmode="array",
    tickvals=trend_ticks,
    ticktext=trend_tick_text,
    tickangle=0,
    range=[0.5, len(trend_ticks) + 0.5],
)
st.plotly_chart(style_dertte_figure(trend_fig, 390), use_container_width=True)

# 상세 실적은 아래에서 계산하지만 채널별 그래프보다 먼저 렌더링합니다.
account_detail_placeholder = st.container()

# 선택한 채널의 기간별 매출 흐름을 비교합니다.
section_title("채널별 매출 추이", "백만원")
channel_options = sorted(
    channel
    for channel in detail_history["channel"].dropna().unique()
    if "미매핑" not in str(channel)
)
channel_trend_widget_key = "dertte_overview_trend_channel"
if (
    channel_trend_widget_key in st.session_state
    and st.session_state[channel_trend_widget_key] not in channel_options
):
    del st.session_state[channel_trend_widget_key]
selected_trend_channel = st.segmented_control(
    "채널 선택",
    channel_options,
    default=channel_options[0],
    key=channel_trend_widget_key,
)
channel_history = detail_history.loc[
    detail_history["channel"] == selected_trend_channel
]
if frequency == "월간":
    channel_trend = pd.concat([
        comparison_trend_series(
            current_year_ytd_start, reference_date, "month", f"당해 {reference_date.year}년", channel_history
        ),
        comparison_trend_series(
            previous_year_ytd_start,
            previous_year_trend_end,
            "month",
            f"전년 {previous_year_end.year}년",
            channel_history,
        ),
    ], ignore_index=True)
    channel_axis_values = list(range(1, 13))
    channel_axis_text = [f"{month}월" for month in channel_axis_values]
    channel_axis_label = "월"
else:
    channel_trend = pd.concat([
        comparison_trend_series(current_month_start, reference_date, "day", "당월", channel_history),
        comparison_trend_series(
            previous_month_start,
            previous_month_trend_end,
            "day",
            "전월",
            channel_history,
        ),
        comparison_trend_series(
            previous_year_month_start,
            previous_year_month_trend_end,
            "day",
            "전년 동월",
            channel_history,
        ),
    ], ignore_index=True)
    channel_axis_values = list(range(1, daily_trend_day_count + 1))
    channel_axis_text = [f"{day}일" for day in channel_axis_values]
    channel_axis_label = "일"

channel_trend_fig = px.line(
    channel_trend,
    x="axis_value",
    y="value",
    color="구분",
    symbol="구분",
    line_dash="구분",
    markers=True,
    color_discrete_sequence=["#0B3D91", "#2F80ED", "#7B61FF"],
    symbol_sequence=["circle", "square", "diamond"],
    line_dash_sequence=["solid", "dash", "dot"],
    labels={
        "axis_value": channel_axis_label,
        "value": "매출액(백만원)",
    },
)
channel_trend_fig.update_traces(
    connectgaps=False,
    line_width=3,
    marker_size=8,
    marker_line_width=1.5,
    marker_line_color="#FFFFFF",
    hovertemplate=(
        f"%{{fullData.name}}<br>{channel_axis_label} %{{x}}"
        "<br>매출액(백만원) %{y:,.0f}<extra></extra>"
    ),
)
channel_trend_fig.update_layout(
    hovermode="x unified",
    legend_title_text=f"{selected_trend_channel} 비교 기간",
)
channel_trend_fig.update_xaxes(
    tickmode="array",
    tickvals=channel_axis_values,
    ticktext=channel_axis_text,
    tickangle=0,
    range=[0.5, len(channel_axis_values) + 0.5],
)
channel_trend_fig = style_dertte_figure(channel_trend_fig, 390)
channel_trend_fig.update_layout(margin=dict(l=18, r=18, t=48, b=0))
st.plotly_chart(channel_trend_fig, use_container_width=True)

section_title("채널별 매출액 TOP 10 제품", "백만원")
channel_product_source = filtered.loc[
    ~filtered["channel"].astype(str).str.contains("미매핑", na=False)
]
channel_product = channel_product_source.groupby(
    ["channel", "product_name"], as_index=False
)["sales"].sum()
channel_product["sales_million"] = (channel_product["sales"] / 1_000_000).round(0)
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
            x="sales_million",
            y="product_name",
            orientation="h",
            color="sales_million",
            color_continuous_scale=[[0, "#DCE9F6"], [1, COLORS["primary"]]],
            labels={"sales_million": "매출액", "product_name": "제품명"},
        )
        channel_product_fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_dertte_figure(channel_product_fig, 430), use_container_width=True)

section_title("카테고리별 판매 제품 TOP 10", "EA, 백만원")
category_levels = {
    "대분류": "category_large",
    "중분류": "category_middle",
    "소분류": "category_small",
    "세분류": "category_detail",
}
category_level_label = (
    st.segmented_control("카테고리 단계", list(category_levels), default="대분류")
    or "대분류"
)

def category_drilldown_value(label: str, options: list, key: str, show_widget: bool) -> object:
    """분류 단계별 선택을 기억하고 상위 선택에 맞지 않는 값은 첫 항목으로 초기화합니다."""
    if not options:
        return None
    value_key = f"{key}_value"
    widget_key = f"{key}_widget"
    if st.session_state.get(value_key) not in options:
        st.session_state[value_key] = options[0]
    if show_widget:
        # 화면에서 사라지는 위젯 키와 계속 보존할 선택값 키를 분리합니다.
        if widget_key in st.session_state and st.session_state[widget_key] not in options:
            del st.session_state[widget_key]
        selected_value = st.selectbox(
            f"MC {label}",
            options,
            index=options.index(st.session_state[value_key]),
            key=widget_key,
        )
        st.session_state[value_key] = selected_value
        return selected_value
    return st.session_state[value_key]

large_values = sorted(filtered["category_large"].dropna().unique())
selected_drill_large = category_drilldown_value(
    "대분류", large_values, "category_drill_large", category_level_label == "대분류"
)
category_scope = filtered.loc[filtered["category_large"] == selected_drill_large]

selected_drill_middle = None
selected_drill_small = None
selected_drill_detail = None
if category_level_label in ("중분류", "소분류", "세분류"):
    middle_values = sorted(category_scope["category_middle"].dropna().unique())
    selected_drill_middle = category_drilldown_value(
        "중분류", middle_values, "category_drill_middle", category_level_label == "중분류"
    )
    category_scope = category_scope.loc[
        category_scope["category_middle"] == selected_drill_middle
    ]

if category_level_label in ("소분류", "세분류"):
    small_values = sorted(category_scope["category_small"].dropna().unique())
    selected_drill_small = category_drilldown_value(
        "소분류", small_values, "category_drill_small", category_level_label == "소분류"
    )
    category_scope = category_scope.loc[
        category_scope["category_small"] == selected_drill_small
    ]

if category_level_label == "세분류":
    detail_values = sorted(category_scope["category_detail"].dropna().unique())
    selected_drill_detail = category_drilldown_value(
        "세분류", detail_values, "category_drill_detail", True
    )
    category_scope = category_scope.loc[
        category_scope["category_detail"] == selected_drill_detail
    ]

breadcrumb_values = [
    value
    for value in (
        selected_drill_large,
        selected_drill_middle,
        selected_drill_small,
        selected_drill_detail,
    )
    if value is not None
]
st.caption("선택 분류: " + " 〉 ".join(map(str, breadcrumb_values)))
category_products = (
    category_scope
    .groupby("product_name", as_index=False)
    .agg(sales=("sales", "sum"), quantity=("quantity", "sum"))
    .nlargest(10, "quantity")
    .sort_values("quantity")
)
category_products["sales_million"] = (category_products["sales"] / 1_000_000).round(0)
category_product_fig = px.bar(
    category_products, x="quantity", y="product_name", orientation="h", color="sales_million",
    color_continuous_scale=[[0, "#DCE9F6"], [1, COLORS["primary"]]],
    labels={"quantity": "판매수량(EA)", "product_name": "제품명", "sales_million": "매출액(백만원)"},
)
st.plotly_chart(style_dertte_figure(category_product_fig, 420), use_container_width=True)

metric_specs = {
    "daily_sales": detail_history["date"].eq(reference_date),
    "current_month_sales": detail_history["date"].between(current_month_start, reference_date),
    "current_year_ytd_sales": detail_history["date"].between(current_year_ytd_start, reference_date),
    "previous_month_sales": detail_history["date"].between(previous_month_start, previous_month_end),
    "previous_year_ytd_sales": detail_history["date"].between(previous_year_ytd_start, previous_year_end),
    "previous_year_month_sales": detail_history["date"].between(previous_year_month_start, previous_year_end),
}
channel_metrics = None
for metric_name, metric_mask in metric_specs.items():
    metric_values = (
        detail_history.loc[metric_mask]
        .groupby("channel")["sales"]
        .sum()
        .rename(metric_name)
    )
    channel_metrics = metric_values.to_frame() if channel_metrics is None else channel_metrics.join(metric_values, how="outer")

channel_metrics = channel_metrics.fillna(0).reset_index()
channel_metrics["previous_month_change_rate"] = np.where(
    channel_metrics["previous_month_sales"] == 0,
    np.nan,
    (channel_metrics["current_month_sales"] - channel_metrics["previous_month_sales"])
    / channel_metrics["previous_month_sales"].abs() * 100,
)
channel_metrics["previous_year_month_change_rate"] = np.where(
    channel_metrics["previous_year_month_sales"] == 0,
    np.nan,
    (channel_metrics["current_month_sales"] - channel_metrics["previous_year_month_sales"])
    / channel_metrics["previous_year_month_sales"].abs() * 100,
)
channel_metrics["previous_year_ytd_change_rate"] = np.where(
    channel_metrics["previous_year_ytd_sales"] == 0,
    np.nan,
    (channel_metrics["current_year_ytd_sales"] - channel_metrics["previous_year_ytd_sales"])
    / channel_metrics["previous_year_ytd_sales"].abs() * 100,
)
value_columns = list(metric_specs)
detail_rows: list[dict] = []

total_values = channel_metrics[value_columns].sum()
detail_rows.append({
    "Channel1_1": "Total sum",
    **{column: total_values[column] / 1_000_000 for column in value_columns},
})
detail_rows[0]["previous_month_change_rate"] = (
    np.nan if total_values["previous_month_sales"] == 0 else
    (total_values["current_month_sales"] - total_values["previous_month_sales"])
    / abs(total_values["previous_month_sales"]) * 100
)
detail_rows[0]["previous_year_month_change_rate"] = (
    np.nan if total_values["previous_year_month_sales"] == 0 else
    (total_values["current_month_sales"] - total_values["previous_year_month_sales"])
    / abs(total_values["previous_year_month_sales"]) * 100
)
detail_rows[0]["previous_year_ytd_change_rate"] = (
    np.nan if total_values["previous_year_ytd_sales"] == 0 else
    (total_values["current_year_ytd_sales"] - total_values["previous_year_ytd_sales"])
    / abs(total_values["previous_year_ytd_sales"]) * 100
)

for _, channel_row in channel_metrics.sort_values("current_month_sales", ascending=False).iterrows():
    detail_rows.append({
        "Channel1_1": channel_row["channel"],
        **{column: channel_row[column] / 1_000_000 for column in value_columns},
        "previous_month_change_rate": channel_row["previous_month_change_rate"],
        "previous_year_month_change_rate": channel_row["previous_year_month_change_rate"],
        "previous_year_ytd_change_rate": channel_row["previous_year_ytd_change_rate"],
    })

daily_label = f"Daily {reference_date:%y/%m/%d} ⓘ"
current_month_label = (
    f"MTD {reference_date.month}월 ⓘ"
)
current_year_ytd_label = f"YTD {reference_date.year} ⓘ"
previous_month_label = f"PMTD {previous_month_end.month}월 ⓘ"
previous_month_change_label = "MoM % ⓘ"
previous_year_ytd_label = f"LY YTD {previous_year_end.year} ⓘ"
previous_year_month_label = f"LY MTD {previous_year_end:%y/%m} ⓘ"
previous_year_change_label = "YoY % ⓘ"
previous_year_ytd_change_label = "YTD YoY % ⓘ"
detail = pd.DataFrame(detail_rows).rename(columns={
    "daily_sales": daily_label,
    "current_month_sales": current_month_label,
    "current_year_ytd_sales": current_year_ytd_label,
    "previous_month_sales": previous_month_label,
    "previous_month_change_rate": previous_month_change_label,
    "previous_year_ytd_sales": previous_year_ytd_label,
    "previous_year_month_sales": previous_year_month_label,
    "previous_year_month_change_rate": previous_year_change_label,
    "previous_year_ytd_change_rate": previous_year_ytd_change_label,
})
if frequency == "월간":
    pivot_metric_columns = [
        current_month_label,
        current_year_ytd_label,
        previous_month_label,
        previous_year_month_label,
        previous_month_change_label,
        previous_year_change_label,
        previous_year_ytd_label,
        previous_year_ytd_change_label,
    ]
else:
    pivot_metric_columns = [
        daily_label,
        current_month_label,
        previous_month_label,
        previous_year_month_label,
        previous_month_change_label,
        previous_year_change_label,
    ]
pivot_rate_columns = {
    previous_month_change_label,
    previous_year_change_label,
    previous_year_ytd_change_label,
}
pivot_amount_columns = [
    column for column in pivot_metric_columns if column not in pivot_rate_columns
]
detail = detail[["Channel1_1", *pivot_metric_columns]]
detail = detail.rename(columns={"Channel1_1": "채널"})
detail = detail.loc[
    detail[pivot_amount_columns].fillna(0).ne(0).any(axis=1)
].reset_index(drop=True)

# 기존 Channel1_1 → Channel1_2 → 매출처 구조는 접이식 상세표로 유지합니다.
account_metrics = None
for metric_name, metric_mask in metric_specs.items():
    metric_values = (
        detail_history.loc[metric_mask]
        .groupby(["channel", "channel_detail", "account_name"])["sales"]
        .sum()
        .rename(metric_name)
    )
    account_metrics = (
        metric_values.to_frame()
        if account_metrics is None
        else account_metrics.join(metric_values, how="outer")
    )
account_metrics = account_metrics.fillna(0).reset_index()

def period_change_rate(current_value: float, comparison_value: float) -> float:
    return (
        np.nan if comparison_value == 0
        else (current_value - comparison_value) / abs(comparison_value) * 100
    )

def account_pivot_row(
    channel_value: str,
    channel_detail_value: str,
    account_value: str,
    values: pd.Series,
) -> dict:
    return {
        "Channel1_1": channel_value,
        "Channel1_2": channel_detail_value,
        "매출처": account_value,
        **{column: values[column] / 1_000_000 for column in value_columns},
        "previous_month_change_rate": period_change_rate(
            values["current_month_sales"], values["previous_month_sales"]
        ),
        "previous_year_month_change_rate": period_change_rate(
            values["current_month_sales"], values["previous_year_month_sales"]
        ),
        "previous_year_ytd_change_rate": period_change_rate(
            values["current_year_ytd_sales"], values["previous_year_ytd_sales"]
        ),
    }

account_detail_rows = [account_pivot_row("Total sum", "", "", account_metrics[value_columns].sum())]
channel_order = (
    account_metrics.groupby("channel")["current_month_sales"].sum()
    .sort_values(ascending=False).index
)
for channel_name in channel_order:
    level_1 = account_metrics.loc[account_metrics["channel"] == channel_name]
    account_detail_rows.append(
        account_pivot_row(channel_name, "SUM", "", level_1[value_columns].sum())
    )
    channel_detail_order = (
        level_1.groupby("channel_detail")["current_month_sales"].sum()
        .sort_values(ascending=False).index
    )
    for channel_detail_name in channel_detail_order:
        level_2 = level_1.loc[level_1["channel_detail"] == channel_detail_name]
        account_detail_rows.append(
            account_pivot_row("", channel_detail_name, "SUM", level_2[value_columns].sum())
        )
        for _, account_row in level_2.sort_values("current_month_sales", ascending=False).iterrows():
            account_detail_rows.append(
                account_pivot_row("", "", account_row["account_name"], account_row)
            )

account_detail = pd.DataFrame(account_detail_rows).rename(columns={
    "daily_sales": daily_label,
    "current_month_sales": current_month_label,
    "current_year_ytd_sales": current_year_ytd_label,
    "previous_month_sales": previous_month_label,
    "previous_month_change_rate": previous_month_change_label,
    "previous_year_ytd_sales": previous_year_ytd_label,
    "previous_year_month_sales": previous_year_month_label,
    "previous_year_month_change_rate": previous_year_change_label,
    "previous_year_ytd_change_rate": previous_year_ytd_change_label,
})
account_detail = account_detail[[
    "Channel1_1", "Channel1_2", "매출처", *pivot_metric_columns,
]]
account_detail = account_detail.rename(columns={
    "Channel1_1": "채널",
    "Channel1_2": "상세 채널",
})
account_detail = account_detail.loc[
    account_detail[pivot_amount_columns].fillna(0).ne(0).any(axis=1)
].reset_index(drop=True)

def style_pivot_row(row: pd.Series) -> list[str]:
    is_summary = row["채널"] == "Total sum"
    style = "font-weight: 700; background-color: #EAF2FA" if is_summary else ""
    return [style] * len(row)

def highlight_negative_daily(value: object) -> str:
    """음수 일매출을 붉은 계열로 강조합니다."""
    if isinstance(value, (int, float, np.integer, np.floating)) and value < 0:
        return "color: #B91C1C; background-color: #FEE2E2; font-weight: 700"
    return ""

styled_detail = detail.style.apply(style_pivot_row, axis=1)
if daily_label in detail.columns:
    styled_detail = styled_detail.map(highlight_negative_daily, subset=[daily_label])

def style_account_pivot_row(row: pd.Series) -> list[str]:
    is_summary = (
        row["채널"] == "Total sum"
        or row["상세 채널"] == "SUM"
        or row["매출처"] == "SUM"
    )
    style = "font-weight: 700; background-color: #EAF2FA" if is_summary else ""
    return [style] * len(row)

styled_account_detail = account_detail.style.apply(style_account_pivot_row, axis=1)
if daily_label in account_detail.columns:
    styled_account_detail = styled_account_detail.map(
        highlight_negative_daily, subset=[daily_label]
    )

account_csv_frame = account_detail.copy()
for column in pivot_amount_columns:
    account_csv_frame[column] = account_csv_frame[column].map(
        lambda value: "" if pd.isna(value) else f"{value:,.0f}"
    )
for column in pivot_rate_columns.intersection(account_csv_frame.columns):
    account_csv_frame[column] = account_csv_frame[column].map(
        lambda value: "" if pd.isna(value) else f"{value:,.1f}%"
    )
account_csv = account_csv_frame.to_csv(index=False).encode("utf-8-sig")
pivot_column_help = {
    daily_label: f"Daily: {reference_date:%Y.%m.%d} 하루의 매출입니다.",
    current_month_label: (
        f"MTD (Month-to-Date): {current_month_start:%Y.%m.%d}부터 "
        f"{reference_date:%Y.%m.%d}까지의 당월 누계입니다."
    ),
    current_year_ytd_label: (
        f"YTD (Year-to-Date): {current_year_ytd_start:%Y.%m.%d}부터 "
        f"{reference_date:%Y.%m.%d}까지의 당해 누계입니다."
    ),
    previous_month_label: (
        f"PMTD (Previous Month-to-Date): {previous_month_start:%Y.%m.%d}부터 "
        f"{previous_month_end:%Y.%m.%d}까지의 전월 대응 누계입니다."
    ),
    previous_year_month_label: (
        f"LY MTD (Last Year Month-to-Date): {previous_year_month_start:%Y.%m.%d}부터 "
        f"{previous_year_end:%Y.%m.%d}까지의 전년 동월 누계입니다."
    ),
    previous_month_change_label: "MoM (Month-over-Month): 당월 MTD가 전월 PMTD보다 증감한 비율입니다.",
    previous_year_change_label: "YoY (Year-over-Year): 당월 MTD가 전년 동월 LY MTD보다 증감한 비율입니다.",
    previous_year_ytd_label: (
        f"LY YTD (Last Year Year-to-Date): {previous_year_ytd_start:%Y.%m.%d}부터 "
        f"{previous_year_end:%Y.%m.%d}까지의 전년 누계입니다."
    ),
    previous_year_ytd_change_label: "YTD YoY: 당해 YTD가 전년 LY YTD보다 증감한 비율입니다.",
}
percentage_columns = pivot_rate_columns
number_columns = {
    column: st.column_config.NumberColumn(
        format="%,.1f%%" if column in percentage_columns else "%,.0f",
        help=pivot_column_help.get(column),
    )
    for column in pivot_metric_columns
}
with account_detail_placeholder:
    st.markdown(
        '<div style="text-align:right; color:#617B98; font-size:.78rem; margin:-.35rem .2rem .2rem 0;">(단위: 백만원, %)</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        styled_detail,
        use_container_width=True,
        hide_index=True,
        column_config=number_columns,
    )
    with st.expander("매출처 상세보기", expanded=False):
        section_title("매출처 상세 실적", "백만원, %")
        st.markdown(
            '<div class="section-sub">Channel1_1 → Channel1_2 → 매출처 순서의 상세 피벗입니다.</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            styled_account_detail,
            use_container_width=True,
            hide_index=True,
            column_config=number_columns,
        )
        st.download_button(
            "매출처 실적 CSV 다운로드",
            account_csv,
            f"dertte_account_sales_{date.today():%Y%m%d}.csv",
            "text/csv",
        )
st.caption("© 데르뜨 · 매출액과 판매수량은 선택한 기간 및 필터 기준입니다.")
