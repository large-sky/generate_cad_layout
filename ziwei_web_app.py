import streamlit as st
import os
from datetime import datetime
from ziwei_db_V4 import ZiWeiEngineV4, init_database_v4, generate_ziwei_pdf_v4

# 初始化資料庫
db_name = "ziwei_v4_core.db"
if not os.path.exists(db_name):
    init_database_v4(db_name)

st.set_page_config(page_title="紫微斗數真太陽時排盤系統 V4.0", layout="wide")

st.title("🔮 紫微斗數真太陽時安星排盤系統 (V4.0 專業版)")
st.write("請於下方輸入出生參數，系統將自動進行天文均時差校正與全自動安星。")

# 建立側邊欄輸入介面
with st.sidebar:
    st.header("📋 輸入基本資料")
    gender = st.selectbox("性別", ["男命 (乾造)", "女命 (坤造)"])
    gender_code = "1" if "男" in gender else "2"
    
    birth_date = st.date_input(
    "出生公曆日期", 
    value=datetime(1994, 1, 1),
    min_value=datetime(1930, 1, 1),
    max_value=datetime(2130, 12, 31)
)
    
    DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    hour_choice = st.selectbox("出生時辰", [f"[{i+1}] {zhi}時" for i, zhi in enumerate(DI_ZHI)])
    h_zhi = hour_choice.split(" ")[1].replace("時", "")
    
    sub_type = "2"
    if h_zhi == "子":
        sub_type_lbl = st.radio("子時細分", ["晚子時 (23:00-24:00)", "早子時 (00:00-01:00)"])
        sub_type = "1" if "晚" in sub_type_lbl else "2"
        
    leap_rule = st.radio("農曆閏月換算規則", ["前半月算本月，後半月算下個月", "直接併入下個月計算"])
    leap_rule_code = "1" if "前半月" in leap_rule else "2"
    
    lon = st.number_input("出生地經度 (桃園預設 121.31)", value=121.31, format="%.2f")
    
    btn_calculate = st.button("🚀 開始精準排盤")

# 主畫面邏輯
if btn_calculate:
    # 呼叫 V4 核心引擎
    engine = ZiWeiEngineV4(
        db_path=db_name,
        gender=gender_code,
        year=birth_date.year,
        month=birth_date.month,
        day=birth_date.day,
        hour_zhi=h_zhi,
        sub_type=sub_type,
        longitude=lon,
        leap_rule=leap_rule_code
    )
    
    # 執行運算
    engine.調用資料庫進行十二宮深度解盤()
    engine.calculate_lifetime_fortune(start_age=0, end_age=90)
    
    # 呈現 4x4 方塊命盤視覺圖
    st.subheader("📊 本命十二宮方塊命盤 (疊宮)")
    grid_matrix = engine.generate_palace_matrix()
    
    # 使用 Streamlit Columns 模擬 4x4 命盤
    positions = [
        ("巳", 0, 0), ("午", 0, 1), ("未", 0, 2), ("申", 0, 3),
        ("辰", 1, 0), ("中宮", 1, 1), ("中宮", 1, 2), ("酉", 1, 3),
        ("卯", 2, 0), ("中宮", 2, 1), ("中宮", 2, 2), ("戌", 2, 3),
        ("寅", 3, 0), ("丑", 3, 1), ("子", 3, 2), ("亥", 3, 3)
    ]
    
    # 為了美觀，我們用 Table 顯示
    st.table(grid_matrix)
    
    # PDF 生成與下載
    pdf_filename = "ziwei_v4_web_report.pdf"
    info_str = f"{gender} | 新曆: {birth_date} | 經度: {lon}° | 農曆: {engine.lunar.getYear()}年{engine.lunar_month}月{engine.lunar_day}日"
    generate_ziwei_pdf_v4(pdf_filename, info_str, grid_matrix, engine.report_logs)
    
    if os.path.exists(pdf_filename):
        with open(pdf_filename, "rb") as pdf_file:
            st.download_button(
                label="📥 下載專業級 PDF 詳批報告",
                data=pdf_file,
                file_name=f"紫微斗數_{birth_date}.pdf",
                mime="application/pdf"
            )
    engine.close()