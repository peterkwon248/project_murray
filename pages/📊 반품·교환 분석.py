import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import os
import json

# 🔐 Railway 환경변수 기반 인증 처리
service_account_info = json.loads(os.environ["GOOGLE_CREDS"])
scoped_credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(scoped_credentials)

# ✅ 고정된 시트 URL → sheet_id만 추출
sheet_url = "https://docs.google.com/spreadsheets/d/1GZCJuWRcYQgCU7iWMW-fg6tUhJ0WXbcDPb4yKi7Tx_M/edit?usp=sharing"
sheet_id = sheet_url.split("/d/")[1].split("/")[0]

# 설정
st.set_page_config(page_title="📊 고정 시트 대시보드", layout="wide")
st.title("📊 구글 시트 대시보드")

try:
    # 구글 시트 열기
    sh = gc.open_by_key(sheet_id)
    sheet_names = [ws.title for ws in sh.worksheets()]
    selected_sheets = st.multiselect("📄 병합할 시트를 선택하세요:", sheet_names, default=["통합 요약"])

    # 시트 병합
    df_list = []
    for name in selected_sheets:
        ws = sh.worksheet(name)
        temp_df = pd.DataFrame(ws.get_all_records())
        temp_df["시트이름"] = name
        df_list.append(temp_df)

    if df_list:
        df = pd.concat(df_list, ignore_index=True)

        # 🔍 필터 UI
        with st.expander("🔍 필터 열기/닫기"):
            if "처리방식" in df.columns:
                처리방식_선택 = st.multiselect("처리방식 필터", df["처리방식"].unique(), default=df["처리방식"].unique())
                df = df[df["처리방식"].isin(처리방식_선택)]

            if "모델명" in df.columns:
                고유모델명 = sorted(df["모델명"].dropna().unique())
                선택된모델 = st.selectbox("🔍 모델명 자동완성 선택:", options=["(전체 보기)"] + 고유모델명)
                if 선택된모델 != "(전체 보기)":
                    df = df[df["모델명"] == 선택된모델]

        # 📊 통계 요약
        with st.expander("📊 통계 요약"):
            total_qty = df["수량"].sum() if "수량" in df else 0
            avg_qty = df["수량"].mean() if "수량" in df else 0
            max_qty = df["수량"].max() if "수량" in df else 0
            row_count = len(df)
            unique_models = df["모델명"].nunique() if "모델명" in df else 0
            unique_methods = df["처리방식"].nunique() if "처리방식" in df else 0

            st.metric("총 수량", f"{total_qty:,}")
            st.metric("평균 수량", f"{avg_qty:.2f}")
            st.metric("최대 수량", f"{max_qty:,}")
            st.metric("총 건수", f"{row_count}건")
            st.metric("고유 모델 수", f"{unique_models}개")
            st.metric("처리방식 수", f"{unique_methods}개")

        # 📂 시트별 보기
        for 시트이름 in df["시트이름"].unique():
            with st.expander(f"📂 {시트이름}"):
                partial_df = df[df["시트이름"] == 시트이름]
                st.dataframe(partial_df, use_container_width=True)

        # 📊 고급 차트
        if "수량" in df.columns and pd.api.types.is_numeric_dtype(df["수량"]):
            st.markdown("### 📊 시트별 처리방식 수량")
            chart_data = df.groupby(["시트이름", "처리방식"])["수량"].sum().reset_index()
            fig = px.bar(chart_data, x="처리방식", y="수량", color="시트이름", barmode="group", title="시트별 처리방식별 수량")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### 📦 수량 기준 Top 10 모델")
            top_models = df.groupby("모델명")["수량"].sum().nlargest(10).reset_index()
            fig_top = px.bar(top_models, x="모델명", y="수량", title="Top 10 모델명 by 수량")
            st.plotly_chart(fig_top, use_container_width=True)

            st.markdown("### 🥧 처리방식별 비율 비교")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("✅ 수량 기준 비율")
                pie_data_qty = df.groupby("처리방식")["수량"].sum().reset_index()
                fig_pie_qty = px.pie(pie_data_qty, values="수량", names="처리방식", title="수량 기준 비율")
                st.plotly_chart(fig_pie_qty, use_container_width=True)

            with col2:
                st.subheader("✅ 건수 기준 비율")
                pie_data_count = df["처리방식"].value_counts().reset_index()
                pie_data_count.columns = ["처리방식", "건수"]
                fig_pie_count = px.pie(pie_data_count, values="건수", names="처리방식", title="건수 기준 비율")
                st.plotly_chart(fig_pie_count, use_container_width=True)

            st.markdown("### 🔥 시트별 처리방식별 수량 Heatmap")
            pivot = df.pivot_table(index="처리방식", columns="시트이름", values="수량", aggfunc="sum").fillna(0)
            fig_heat = px.imshow(pivot, text_auto=True, title="시트-처리방식별 수량 Heatmap")
            st.plotly_chart(fig_heat, use_container_width=True)

except Exception as e:
    st.error(f"❌ 오류 발생: {e}")
