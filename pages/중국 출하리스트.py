import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import plotly.express as px

# 📊 대시보드 설정
st.set_page_config(page_title="📦 중국 실시간 출하리스트", layout="wide")
st.title("📦 중국 실시간 출하리스트")

# 🔐 서비스 계정 인증
service_account_info = json.loads(st.secrets["gcp_service_account"])
credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credentials)

# 📥 구글 시트 불러오기
SHEET_ID = "19xAdSPAXY-BYPylN5xRMf0d-sJ4u0RBGXpVJ5W82p04"
worksheet = gc.open_by_key(SHEET_ID).worksheet("제품 발주 및 출하예정 자료")
records = worksheet.get_all_records()
df = pd.DataFrame(records)

# 🧼 날짜 처리
date_cols = ["발주일", "회사 도착예정일", "회사 실제 도착일", "ETD 배타임"]
for col in date_cols:
    df[col] = pd.to_datetime(df[col], errors="coerce")

# 📋 데이터 정렬
df = df.sort_values("발주일", ascending=False)

# 📅 날짜 필터
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📆 시작일", value=pd.Timestamp.today() - pd.Timedelta(days=30))
with col2:
    end_date = st.date_input("📆 종료일", value=pd.Timestamp.today())

filtered_df = df[
    (df["발주일"] >= pd.to_datetime(start_date)) &
    (df["발주일"] <= pd.to_datetime(end_date))
]

# 📌 상태 필터
if "상태" in filtered_df.columns:
    status_list = filtered_df["상태"].dropna().unique().tolist()
    selected_status = st.multiselect("상태 필터", options=status_list, default=status_list)
    if selected_status:
        filtered_df = filtered_df[filtered_df["상태"].isin(selected_status)]

# 📈 출하 예정일 시각화
if not filtered_df.empty:
    st.subheader("📈 도착 예정일 분포")
    chart = px.histogram(filtered_df, x="회사 도착예정일", nbins=20)
    st.plotly_chart(chart, use_container_width=True)

    st.subheader("📋 필터링된 출하리스트")
    st.info(f"총 {len(filtered_df)}건의 데이터가 필터링되었습니다.")

    # 날짜 컬럼 포맷 정리
    for col in date_cols:
        if col in filtered_df.columns:
            filtered_df[col] = filtered_df[col].dt.date

    st.dataframe(filtered_df)
else:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
