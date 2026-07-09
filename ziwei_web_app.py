import streamlit as st
import os
from datetime import datetime
from ziwei_db_V4 import ZiWeiEngineV4, init_database_v4, generate_ziwei_pdf_v4

# 初始化資料庫標記
db_name = "ziwei_v4_core.db"
if not os.path.exists(db_name):
    init_database_v4(db_name)

st.set_page_config(page_title="紫微斗數真太陽時排盤系統 V4.0", layout="wide")

st.title("🔮 紫微斗數真太陽時安星排盤系統 (V4.0 專業版)")
st.write("本系統已全量整合 168 組核心星情對應矩陣，支援天文級均時差校正與雙子時防呆機制。")

# 建立側邊欄輸入介面
with st.sidebar:
    st.header("📋 輸入出生基本參數")
    
    # 1. 性別選擇
    gender = st.selectbox("性別選擇", ["男命 (乾造)", "女命 (坤造)"])
    gender_code = "1" if "男" in gender else "2"
    
    # 2. 出生公曆年、月、日限制
    birth_date = st.date_input(
        "出生公曆日期", 
        value=datetime(1990, 1, 1),
        min_value=datetime(1930, 1, 1),
        max_value=datetime(2130, 12, 31)
    )
    
    # 3. 12時辰地支選單與二級早晚子時防呆選單
    DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    hour_choice = st.selectbox("出生時辰地支", [f"[{i+1}] {zhi}時" for i, zhi in enumerate(DI_ZHI)])
    h_zhi = hour_choice.split(" ")[1].replace("時", "")
    
    # 🎯 子時二級防呆機制
    sub_type = "2" # 預設為早子時
    if h_zhi == "子":
        sub_type_lbl = st.radio(
            "⏰ 【子時細分確認】請核對您的具體出生鐘點：", 
            ["早子時 (00:00 - 01:00)", "晚子時 (23:00 - 24:00)"],
            help="斗數中早子時與晚子時日干計算有別，請務必精準勾選。"
        )
        sub_type = "1" if "晚" in sub_type_lbl else "2"
        
    # 4. 閏月（Leap Month）解盤規則
    leap_rule = st.radio(
        "📅 農曆閏月命理換算規則", 
        ["前半個月算本月，後半個月算下個月（主流演算法）", "直接併入下個月計算"],
        index=0
    )
    leap_rule_code = "1" if "前半月" in leap_rule else "2"
    
    # 5. 出生地經度（真太陽時校正基準）
    lon = st.number_input("出生地觀測經度 (桃園預設 121.31)", value=121.31, format="%.2f")
    
    st.write("---")
    btn_calculate = st.button("🚀 開始全自動精準排盤")

# 主畫面渲染邏輯
if btn_calculate:
    # 呼叫 V4.0 高精度天文命理核心
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
    
    # 執行運算與日曆矩陣生成
    engine.調用資料庫進行十二宮深度解盤()
    grid_matrix = engine.generate_palace_matrix()
    
    # 顯示前端排盤九宮格 Table
    st.subheader("📊 本命與流年動態疊宮方塊命盤")
    st.table(grid_matrix)
    
    # PDF 導出與傳參對接
    pdf_filename = f"ziwei_v4_report_{birth_date.strftime('%Y%m%d')}.pdf"
    info_str = f"{gender} | 公曆: {birth_date.strftime('%Y-%m-%d')} | 經度: {lon}°E | 農曆: {engine.lunar.getYear()}年{engine.lunar_month}月{engine.lunar_day}日"
    
    generate_ziwei_pdf_v4(pdf_filename, info_str, grid_matrix, engine.report_logs)
    
    if os.path.exists(pdf_filename):
        with open(pdf_filename, "rb") as pdf_file:
            st.download_button(
                label="📥 下載專業級 PDF 詳批報告 (含 4x4 命盤與全整合斷語)",
                data=pdf_file,
                file_name=f"紫微斗數_{birth_date.strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
        st.success(f"✨ 系統已成功整合真太陽時校正，並輸出完整分析報告。")
    
    # 將深度解盤文字直接呈現在網頁下方
    st.subheader("📖 詳批流年與星情動態引動分析")
    for log in engine.report_logs:
        st.write(log)
        
    engine.close()