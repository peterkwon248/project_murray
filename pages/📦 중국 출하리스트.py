import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_calendar import calendar
import os
import json

# ✅ 날짜 및 페이지 설정
today = datetime.now(ZoneInfo("Asia/Seoul")).date()
today_str = today.strftime("%Y-%m-%d")
st.set_page_config(page_title="중국 출하 리스트 (ETA 기준)", layout="wide")
st.title("📦 중국 출하 리스트 (📅 ETA+1 기준 미도착 필터링)")
st.markdown(f"### \u23f0 기준일: **{today_str} (KST)**")

# ✅ 구글 인증
if "gcp_service_account" in os.environ:
    SERVICE_ACCOUNT_INFO = json.loads(os.environ["gcp_service_account"])
else:
    SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]

credentials = Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
gc = gspread.authorize(credentials)

# ✅ 데이터 불러오기
SPREADSHEET_ID = "19xAdSPAXY-BYPylN5xRMf0d-sJ4u0RBGXpVJ5W82p04"
worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet("제품 발주 및 출하예정 차트")
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# ✅ 전처리
df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()
df["출하예정일"] = pd.to_datetime(df["출하예정일"], errors="coerce")
df["ETD배타는 날"] = pd.to_datetime(df["ETD배타는 날"], errors="coerce")
df["회사실제 도착일"] = pd.to_datetime(df["회사실제 도착일"], errors="coerce")
df["회사도착 예상일(=ETA+1)"] = pd.to_datetime(df["회사도착 예상일(=ETA+1)"], errors="coerce")

# ✅ 필터링 (지연 포함 + 도착 상태 기반)
filtered_df = df[
    (df["회사도착 예상일(=ETA+1)"].notna()) &
    (
        (df["회사도착 예상일(=ETA+1)"].dt.date >= today) |
        ((df["회사도착 예상일(=ETA+1)"].dt.date < today) & (df["상태"].str.strip() != "회사 도착"))
    )
].copy()

# ✅ 도착여부 (상태 기반)
filtered_df["도착여부"] = filtered_df.apply(
    lambda row: "도착 완료 ✅" if str(row["상태"]).strip() == "회사 도착" else "미도착 🔴",
    axis=1
)

# ✅ D-Day 계산
def classify_dday(row):
    eta = row["회사도착 예상일(=ETA+1)"]
    if pd.isna(eta):
        return "N/A"
    elif eta.date() < today and row["도착여부"] == "미도착 🔴":
        return f"D+{(today - eta.date()).days} ⚠️"
    elif eta.date() == today:
        return "Today"
    elif eta.date() > today:
        return f"D-{(eta.date() - today).days}"
    else:
        return "✅"

filtered_df["D-Day"] = filtered_df.apply(classify_dday, axis=1)

# ✅ 상태 이모지 변환
def status_emoji(status):
    status = str(status).strip()
    if status == "회사 도착":
        return "✅ 회사 도착"
    elif "지연" in status:
        return "⚠️ 지연됨"
    elif "생산" in status:
        return "⏳ 생산중"
    else:
        return f"🔍 {status}"

filtered_df["상태표시"] = filtered_df["상태"].apply(status_emoji)

# ✅ 테두리 색상
def get_border_color(d_day_str):
    if "D+" in d_day_str:
        return "#E74C3C"
    elif "D-DAY" in d_day_str or "Today" in d_day_str:
        return "#2ECC71"
    elif "D-1" in d_day_str or "D-2" in d_day_str:
        return "#F4D03F"
    else:
        return "#3498DB"

# ✅ 상단 요약
col1, col2, col3, col4 = st.columns(4)
col1.metric("전체 건수", len(filtered_df))
col2.metric("도착 완료", sum(filtered_df["도착여부"].str.contains("도착 완료")))
col3.metric("미도착", sum(filtered_df["도착여부"].str.contains("미도착")))
col4.metric("💼 지연 건", sum(filtered_df["D-Day"].str.contains("D\\+")))

# ✅ 캘린더 뷰
st.subheader("🗓 ETA 일정 캘린더 (달력 스타일 뷰)")
events = []
for _, row in filtered_df.iterrows():
    eta = row["회사도착 예상일(=ETA+1)"]
    if pd.isna(eta): continue
    product = row["PRODUCT"]
    status = row["상태표시"]
    color = "#2ECC71" if "도착" in status else "#E74C3C"
    events.append({
        "title": f"{product} - {status}",
        "start": eta.strftime("%Y-%m-%d"),
        "end": eta.strftime("%Y-%m-%d"),
        "color": color,
        "id": eta.strftime("%Y-%m-%d")
    })

calendar(events=events, options={
    "initialView": "dayGridMonth",
    "locale": "ko",
    "height": 600,
    "headerToolbar": {
        "start": "title", "center": "", "end": "today prev,next"
    }
}, key="calendar_view_only")

# ✅ 사이드바 필터
st.sidebar.markdown("## 🔎 날짜 및 모델명 필터")
selected_sidebar_date = st.sidebar.date_input("출하 예정일 선택", value=today)
search_term = st.sidebar.text_input("🔍 모델명 검색", "")
matched = filtered_df[filtered_df["회사도착 예상일(=ETA+1)"].dt.date == selected_sidebar_date]
if search_term:
    matched = matched[matched["PRODUCT"].str.contains(search_term, case=False, na=False)]

arrived = matched[matched["도착여부"] == "도착 완료 ✅"]
not_arrived = matched[matched["도착여부"] == "미도착 🔴"]

# ✅ 미도착 카드 뷰
if not not_arrived.empty:
    st.markdown("---")
    st.markdown(f"## 🔴 {selected_sidebar_date} 미도착 출하건")
    cols = st.columns(3)
    for i, (_, row) in enumerate(not_arrived.iterrows()):
        eta = row["회사도착 예상일(=ETA+1)"]
        d_day = row["D-Day"]
        border_color = get_border_color(d_day)
        with cols[i % 3]:
            st.markdown(f"""
            <div style=\"border:3px solid {border_color}; border-radius:14px; padding:20px; margin:10px; background-color:#fff0f0;\">
                <h4>📦 {row['PRODUCT']}</h4>
                <div style=\"font-size:16px; line-height:1.8;\">
                    🔢 발주수량: {row['발주수량']}개<br>
                    📝 주문상세: {row['주문상세']}<br>
                    📦 상태: {row['상태표시']}<br>
                    🗓 ETA+1: {eta.date() if pd.notna(eta) else "N/A"}<br>
                    🚚 도착여부: {row['도착여부']}<br>
                    📆 D-Day: {d_day}
                </div>
            </div>
            """, unsafe_allow_html=True)

# ✅ 도착 완료 카드 뷰
if not arrived.empty:
    st.markdown("---")
    st.markdown(f"## ✅ {selected_sidebar_date} 도착 완료 출하건")
    cols = st.columns(3)
    for i, (_, row) in enumerate(arrived.iterrows()):
        eta = row["회사도착 예상일(=ETA+1)"]
        d_day = row["D-Day"]
        border_color = get_border_color(d_day)
        with cols[i % 3]:
            st.markdown(f"""
            <div style=\"border:3px solid {border_color}; border-radius:14px; padding:20px; margin:10px; background-color:#f0fff0;\">
                <h4>📦 {row['PRODUCT']}</h4>
                <div style=\"font-size:16px; line-height:1.8;\">
                    🔢 발주수량: {row['발주수량']}개<br>
                    📝 주문상세: {row['주문상세']}<br>
                    📦 상태: {row['상태표시']}<br>
                    🗓 ETA+1: {eta.date() if pd.notna(eta) else "N/A"}<br>
                    🚚 도착여부: {row['도착여부']}<br>
                    📆 D-Day: {d_day}
                </div>
            </div>
            """, unsafe_allow_html=True)

# ✅ 개별 카드 뷰 (ETA+1 기준 전체 7일 이내)
st.subheader("📦 개별 출하 현황 (카드 뷰)")
sorted_df = filtered_df.sort_values(by="회사도착 예상일(=ETA+1)")
for _, row in sorted_df.iterrows():
    eta = row["회사도착 예상일(=ETA+1)"]
    d_day = row["D-Day"]
    days_to_eta = (eta.date() - today).days if pd.notna(eta) else None
    if days_to_eta is None or not (0 <= days_to_eta <= 7):
        continue
    d_day_display = {
        2: "🐢 D-2: 도착 임박",
        1: "🐇 D-1: 매우 임박!",
        0: "🚛 D-DAY: 오늘 도착!"
    }.get(days_to_eta, f"🗖 D-Day: {d_day}")
    border_color = get_border_color(d_day)
    st.markdown(f"""
    <div style=\"border:3px solid {border_color}; border-radius:14px; padding:26px; margin-bottom:22px; background-color:#fefefe;\">
        <h3>📦 {row['PRODUCT']}</h3>
        <div style=\"font-size:20px; font-weight:bold;\">{d_day_display}</div>
        <div style=\"line-height:2.1; font-size:18px; margin-top:16px;\">
            🔢 발주수량: {row['발주수량']}개<br>
            📝 주문상세: {row['주문상세']}<br>
            📦 상태: {row['상태표시']}<br>
            🗓 ETA+1: {eta.date() if pd.notna(eta) else "N/A"}<br>
            🚚 도착여부: {row['도착여부']}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ✅ 원본 표 보기
if st.checkbox("📄 원본 표 보기"):
    st.dataframe(filtered_df[[
        "PRODUCT", "발주수량", "주문상세", "AS불량건 요청수량",
        "실제 출하 수량", "출하예정일", "ETD배타는 날",
        "상태표시", "회사도착 예상일(=ETA+1)", "회사실제 도착일",
        "도착여부", "D-Day"
    ]], use_container_width=True)
