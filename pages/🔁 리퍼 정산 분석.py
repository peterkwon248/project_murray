import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import re

# 🔐 구글 시크릿 인증 처리
service_account_info = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credentials)

# 📥 구글 시트 불러오기
SPREADSHEET_ID = "1O1eIiuYXjpTBclv-4_RYKvmJELglr7cGUfQ18eWUeVE"
WORKSHEET_NAME = "배송및 정산대기중"
worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
records = worksheet.get_all_records()
df = pd.DataFrame(records)

# 🧼 데이터 정제
def clean_price(value):
    if isinstance(value, str):
        return int(re.sub(r"[^\d]", "", value)) if re.sub(r"[^\d]", "", value) else 0
    return int(value) if isinstance(value, (int, float)) else 0

df.fillna("", inplace=True)
for col in ["정산 금액", "수량"]:
    if col in df.columns:
        df[col] = df[col].apply(clean_price)

# ✅ Streamlit UI 설정
st.set_page_config(page_title="📦 리퍼제품 판매 대시보드", layout="wide")
st.title("📦 리퍼제품 판매 대시보드")

# 🔍 사이드바 필터
with st.sidebar:
    if "거래 상태" in df.columns:
        status_list = df["거래 상태"].dropna().unique().tolist()
        selected_status = st.multiselect("📌 거래 상태", status_list, default=status_list)
        df = df[df["거래 상태"].isin(selected_status)]

    if "모델명" in df.columns:
        model_list = df["모델명"].dropna().unique().tolist()
        selected_model = st.multiselect("📦 모델명", model_list, default=model_list)
        df = df[df["모델명"].isin(selected_model)]

    if "사이트" in df.columns:
        site_list = df["사이트"].dropna().unique().tolist()
        selected_site = st.multiselect("🌐 사이트", site_list, default=site_list)
        df = df[df["사이트"].isin(selected_site)]

    if "날짜" in df.columns:
        try:
            df["날짜"] = pd.to_datetime(df["날짜"], format="%y-%m-%d", errors="coerce")
            df = df[df["날짜"].notna()]
            min_date, max_date = df["날짜"].min(), df["날짜"].max()
            selected_range = st.slider("🗓️ 날짜 범위", min_value=min_date, max_value=max_date, value=(min_date, max_date))
            df = df[(df["날짜"] >= selected_range[0]) & (df["날짜"] <= selected_range[1])]
        except Exception:
            pass

# 📊 통계 요약
st.subheader("📊 통계 요약")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("총 거래 수", len(df))
if "정산 금액" in df.columns and not df["정산 금액"].empty:
    col2.metric("총 정산 금액", f"{df['정산 금액'].sum():,} 원")
    col3.metric("평균 정산 금액", f"{df['정산 금액'].mean():,.0f} 원")
    col4.metric("최대 정산 금액", f"{df['정산 금액'].max():,} 원")
    col5.metric("최소 정산 금액", f"{df['정산 금액'].min():,} 원")
else:
    col2.metric("총 정산 금액", "데이터 없음")
    col3.metric("평균 정산 금액", "데이터 없음")
    col4.metric("최대 정산 금액", "데이터 없음")
    col5.metric("최소 정산 금액", "데이터 없음")

# 🏷️ 최고/최저 정산 금액 모델명
if "정산 금액" in df.columns and "모델명" in df.columns and not df["정산 금액"].empty:
    max_amt = df["정산 금액"].max()
    min_amt = df["정산 금액"].min()
    max_models = ", ".join(df[df["정산 금액"] == max_amt]["모델명"].unique())
    min_models = ", ".join(df[df["정산 금액"] == min_amt]["모델명"].unique())

    st.markdown("### 🏷️ 최고/최저 정산 모델명")
    st.markdown(f"- 🏆 **최고 정산 금액 모델:** `{max_models}` (`{max_amt:,} 원`)")
    st.markdown(f"- 💤 **최저 정산 금액 모델:** `{min_models}` (`{min_amt:,} 원`)")
    st.markdown("---")

# 📈 거래 상태 비율
if "거래 상태" in df.columns:
    st.subheader("📈 거래 상태 비율")
    status_counts = df["거래 상태"].value_counts().reset_index()
    status_counts.columns = ["거래 상태", "건수"]
    fig1 = px.pie(status_counts, names="거래 상태", values="건수", title="거래 상태 비율")
    st.plotly_chart(fig1, use_container_width=True)

# 📉 날짜별 정산 금액 추이
if "날짜" in df.columns and "정산 금액" in df.columns:
    st.subheader("📉 날짜별 정산 금액 추이")
    df["정산 금액(만원)"] = df["정산 금액"] / 10000
    full_dates = pd.date_range(start=df["날짜"].min(), end=df["날짜"].max(), freq="D")
    trend = df.groupby("날짜")["정산 금액(만원)"].sum().reindex(full_dates, fill_value=0).reset_index()
    trend.columns = ["날짜", "정산 금액(만원)"]
    fig2 = px.line(trend, x="날짜", y="정산 금액(만원)", markers=True)
    fig2.update_traces(hovertemplate='날짜=%{x|%Y-%m-%d}<br>정산 금액=%{y:.1f}만원')
    fig2.update_layout(yaxis_title="정산 금액 (만원)", yaxis_tickformat=".1f")
    st.plotly_chart(fig2, use_container_width=True)

# 📈 날짜별 정산 수량 추이 (선 그래프)
if "날짜" in df.columns and "수량" in df.columns:
    st.subheader("📈 날짜별 정산 수량 추이")
    qty_trend = df.groupby("날짜")["수량"].sum().reindex(full_dates, fill_value=0).reset_index()
    qty_trend.columns = ["날짜", "정산 수량"]
    fig_qty = px.line(qty_trend, x="날짜", y="정산 수량", markers=True)
    fig_qty.update_traces(hovertemplate='날짜=%{x|%Y-%m-%d}<br>수량=%{y}')
    fig_qty.update_layout(yaxis_title="수량")
    st.plotly_chart(fig_qty, use_container_width=True)

# 📦 모델명별 정산 금액
if "모델명" in df.columns and "정산 금액" in df.columns:
    st.subheader("📦 모델명별 정산 금액")
    model_group = df.groupby("모델명")["정산 금액"].sum().reset_index()
    model_group["정산 금액(만원)"] = model_group["정산 금액"] / 10000
    model_group = model_group.sort_values(by="정산 금액(만원)", ascending=False)
    fig3 = px.bar(model_group, x="모델명", y="정산 금액(만원)")
    fig3.update_traces(hovertemplate='모델명=%{x}<br>정산 금액=%{y:.1f}만원')
    fig3.update_layout(yaxis_title="정산 금액 (만원)", yaxis_tickformat=".1f")
    st.plotly_chart(fig3, use_container_width=True)

# 📦 모델명별 정산 수량 (막대 차트)
if "모델명" in df.columns and "수량" in df.columns:
    st.subheader("📦 모델명별 정산 수량")
    qty_model = df.groupby("모델명")["수량"].sum().reset_index()
    qty_model = qty_model.sort_values(by="수량", ascending=False)
    fig_qty_model = px.bar(qty_model, x="모델명", y="수량")
    fig_qty_model.update_traces(hovertemplate='모델명=%{x}<br>수량=%{y}')
    fig_qty_model.update_layout(yaxis_title="수량")
    st.plotly_chart(fig_qty_model, use_container_width=True)

# 🌐 사이트별 거래 상태
if "사이트" in df.columns and "거래 상태" in df.columns:
    st.subheader("🌐 사이트별 거래 상태")
    cross = df.groupby(["사이트", "거래 상태"]).size().reset_index(name="건수")
    fig4 = px.bar(cross, x="사이트", y="건수", color="거래 상태", barmode="stack")
    st.plotly_chart(fig4, use_container_width=True)

# 📋 전체 거래 내역
st.subheader("📋 전체 거래 내역")
st.dataframe(df, use_container_width=True)

# ⬇️ 다운로드 버튼
st.download_button(
    label="📥 데이터 다운로드 (Excel)",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="refur_data.csv",
    mime="text/csv"
)
