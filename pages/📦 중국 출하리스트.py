# ✅ 중국 출하리스트 전체 필터 대시보드 (도착 여부와 관계없이 모델명 다중 검색 가능)
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
st.title("📦 중국 출하 리스트 (📅 ETA+1 기준 전체 검색 포함)")
st.markdown(f"### ⏰ 기준일: **{today_str} (KST)**")

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

# ✅ 도착여부 (상태 기반)
df["도착여부"] = df["상태"].apply(lambda x: "도착 완료 ✅" if str(x).strip() == "회사 도착" else "미도착 🔴")

# ✅ D-Day 계산
def classify_dday(row):
    eta = row["회사도착 예상일(=ETA+1)"]
    if pd.isna(eta): return "N/A"
    if eta.date() < today and row["도착여부"] == "미도착 🔴":
        return f"D+{(today - eta.date()).days} ⚠️"
    elif eta.date() == today:
        return "Today"
    elif eta.date() > today:
        return f"D-{(eta.date() - today).days}"
    return "✅"

df["D-Day"] = df.apply(classify_dday, axis=1)

# ✅ 상태 이모지 변환
def status_emoji(status):
    status = str(status).strip()
    if status == "회사 도착": return "✅ 회사 도착"
    if "지연" in status: return "⚠️ 지연됨"
    if "생산" in status: return "⏳ 생산중"
    return f"🔍 {status}"

df["상태표시"] = df["상태"].apply(status_emoji)

# ✅ 테두리 색상 함수
def get_border_color(d_day):
    if "D+" in d_day: return "#E74C3C"
    if "D-DAY" in d_day or "Today" in d_day: return "#2ECC71"
    if "D-1" in d_day or "D-2" in d_day: return "#F4D03F"
    return "#3498DB"

# ✅ 상단 요약 (미래 or 미도착 기준 필터링)
filtered_df = df[
    df["회사도착 예상일(=ETA+1)"].notna() &
    (
        (df["회사도착 예상일(=ETA+1)"].dt.date >= today) |
        ((df["회사도착 예상일(=ETA+1)"].dt.date < today) & (df["도착여부"] != "도착 완료 ✅"))
    )
]

col1, col2, col3, col4 = st.columns(4)
col1.metric("전체 건수", len(filtered_df))
col2.metric("도착 완료", sum(filtered_df["도착여부"] == "도착 완료 ✅"))
col3.metric("미도착", sum(filtered_df["도착여부"] == "미도착 🔴"))
col4.metric("💼 지연 건", sum(filtered_df["D-Day"].str.contains("D\\+")))

# ✅ 캘린더
st.subheader("🗓 ETA 일정 캘린더 (달력 스타일 뷰)")
events = []
for _, row in df.iterrows():
    eta = row["회사도착 예상일(=ETA+1)"]
    if pd.isna(eta): continue
    status = row["상태표시"]
    product = row["PRODUCT"]
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
    "headerToolbar": {"start": "title", "center": "", "end": "today prev,next"}
}, key="calendar_view")

# ✅ 사이드바 필터 (과거 포함 + 다중 선택)
st.sidebar.markdown("## 🔎 날짜 및 모델명 필터")
selected_date = st.sidebar.date_input("출하 예정일 선택", value=today)
all_models = sorted(df["PRODUCT"].dropna().unique())
selected_models = st.sidebar.multiselect("📦 모델명 검색", all_models)

# ✅ 필터 적용
matched = df[df["회사도착 예상일(=ETA+1)"].dt.date == selected_date]
if selected_models:
    matched = matched[matched["PRODUCT"].isin(selected_models)]

arrived = matched[matched["도착여부"] == "도착 완료 ✅"]
not_arrived = matched[matched["도착여부"] == "미도착 🔴"]

# ✅ 카드 출력 함수
def render_cards(df, title, color):
    if df.empty: return
    st.markdown("---")
    st.markdown(f"## {color} {selected_date} {title} 출하건")
    cols = st.columns(3)
    for i, (_, row) in enumerate(df.iterrows()):
        eta = row["회사도착 예상일(=ETA+1)"]
        d_day = row["D-Day"]
        border_color = get_border_color(d_day)
        with cols[i % 3]:
            st.markdown(f"""
            <div style='border:3px solid {border_color}; border-radius:14px; padding:20px; margin:10px; background-color:#fefefe;'>
                <h4>📦 {row['PRODUCT']}</h4>
                <div style='font-size:16px; line-height:1.8;'>
                    🔢 발주수량: {row['발주수량']}개<br>
                    📝 주문상세: {row['주문상세']}<br>
                    📦 상태: {row['상태표시']}<br>
                    🗓 ETA+1: {eta.date() if pd.notna(eta) else "N/A"}<br>
                    🚚 도착여부: {row['도착여부']}<br>
                    📆 D-Day: {d_day}
                </div>
            </div>
            """, unsafe_allow_html=True)

render_cards(not_arrived, "미도착", "🔴")
render_cards(arrived, "도착 완료", "✅")

# ✅ 개별 카드 뷰 (7일 이내)
st.subheader("📦 개별 출하 현황 (ETA+1 기준 7일 이내)")
for _, row in df.sort_values("회사도착 예상일(=ETA+1)").iterrows():
    eta = row["회사도착 예상일(=ETA+1)"]
    d_day = row["D-Day"]
    if pd.isna(eta): continue
    days_to_eta = (eta.date() - today).days
    if not (0 <= days_to_eta <= 7): continue
    d_day_display = {
        2: "🐢 D-2: 도착 임박",
        1: "🐇 D-1: 매우 임박!",
        0: "🚛 D-DAY: 오늘 도착!"
    }.get(days_to_eta, f"🗖 D-Day: {d_day}")
    border_color = get_border_color(d_day)
    st.markdown(f"""
    <div style='border:3px solid {border_color}; border-radius:14px; padding:26px; margin-bottom:22px; background-color:#fefefe;'>
        <h3>📦 {row['PRODUCT']}</h3>
        <div style='font-size:20px; font-weight:bold;'>{d_day_display}</div>
        <div style='line-height:2.1; font-size:18px; margin-top:16px;'>
            🔢 발주수량: {row['발주수량']}개<br>
            📝 주문상세: {row['주문상세']}<br>
            📦 상태: {row['상태표시']}<br>
            🗓 ETA+1: {eta.date()}<br>
            🚚 도착여부: {row['도착여부']}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ✅ 원본 표 보기
if st.checkbox("📄 원본 표 보기"):
    st.dataframe(df[[
        "PRODUCT", "발주수량", "주문상세", "AS불량건 요청수량",
        "실제 출하 수량", "출하예정일", "ETD배타는 날",
        "상태표시", "회사도착 예상일(=ETA+1)", "회사실제 도착일",
        "도착여부", "D-Day"
    ]], use_container_width=True)
