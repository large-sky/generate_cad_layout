import sqlite3
import os
import math
from datetime import datetime, timedelta
from lunar_python import Lunar, Solar

# =====================================================================
# 🌐 全局核心常數定義
# =====================================================================
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
PALACES_BASE = ["命宮", "兄弟宮", "夫妻宮", "子女宮", "財帛宮", "疾厄宮", 
                "遷移宮", "交友宮", "官祿宮", "田宅宮", "福德宮", "父母宮"]

# =====================================================================
# ☀️ 模組一：天文真太陽時校正演算法 (True Solar Time)
# =====================================================================
def calculate_true_solar_time(dt: datetime, longitude: float) -> datetime:
    """
    將標準平太陽時(GMT+8)轉換為物理經度與均時差校正後的「真太陽時」。
    """
    standard_longitude = 120.0  # GMT+8 基準經度
    lon_diff_minutes = (longitude - standard_longitude) * 4
    
    day_of_year = dt.timetuple().tm_yday
    b = (2 * math.pi * (day_of_year - 81)) / 365
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    
    total_correction_seconds = int((lon_diff_minutes + eot) * 60)
    ts = dt.timestamp() + total_correction_seconds
    true_dt = datetime.fromtimestamp(ts)
    
    print(f"\n   [⏰ 天文真太陽時校正報告]")
    print(f"   ➔ 輸入標準時間: {dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"   ➔ 地理經度補正: {lon_diff_minutes:+.2f} 分鐘 (觀測經度: {longitude}°)")
    print(f"   ➔ 地球軌道均時差 (EoT): {eot:+.2f} 分鐘")
    print(f"   ➔ 修正後真實觀測太陽時: {true_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    return true_dt

# =====================================================================
# 📄 模組二：ReportLab PDF 報表生成引擎
# =====================================================================
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def generate_ziwei_pdf(filename, basic_info, palace_grid_data, report_logs):
    try:
        pdfmetrics.registerFont(TTFont('Ch_Font', 'c:/windows/fonts/msjh.ttc'))
    except Exception as e:
        print(f"⚠️ 未能載入預設中文字型，請確認字型路徑：{e}")
        return

    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    main_title_style = ParagraphStyle('MainTitle', fontName='Ch_Font', fontSize=20, leading=26, alignment=1, spaceAfter=15, textColor=colors.HexColor("#2C3E50"))
    h1_style = ParagraphStyle('H1', fontName='Ch_Font', fontSize=14, leading=20, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#16A085"))
    body_style = ParagraphStyle('Body', fontName='Ch_Font', fontSize=10, leading=16, spaceAfter=4, textColor=colors.HexColor("#34495E"))
    grid_style = ParagraphStyle('GridText', fontName='Ch_Font', fontSize=9, leading=12, alignment=1)

    story = []
    
    # 1. 報告標題與基本資料
    story.append(Paragraph("<b>紫微斗數命理終身與流年精緻詳批報告</b>", main_title_style))
    story.append(Paragraph(f"<b>📊 基本命盤參數：</b>{basic_info}", body_style))
    story.append(Spacer(1, 15))
    
    # 2. 建立 4x4 命盤視覺圖
    grid_table_data = []
    for r in range(4):
        row_cells = []
        for c in range(4):
            cell_text = palace_grid_data[r][c].replace("\n", "<br/>")
            row_cells.append(Paragraph(cell_text, grid_style))
        grid_table_data.append(row_cells)
        
    t = Table(grid_table_data, colWidths=[135, 135, 135, 135], rowHeights=[90, 90, 90, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAFAFA")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (1,1), (2,2)),
        ('BACKGROUND', (1,1), (2,2), colors.HexColor("#EAEDED")),
    ]))
    story.append(t)
    story.append(PageBreak()) 
    
    # 3. 匯入深度斷語
    for log_type, title, text in report_logs:
        if log_type == "H1":
            story.append(Paragraph(f"<b>{title}</b>", h1_style))
            story.append(Spacer(1, 2))
        elif log_type == "BODY":
            formatted_text = text.replace("\n", "<br/>")
            story.append(Paragraph(formatted_text, body_style))
            
    doc.build(story)
    print(f"\n📁 [系統通知] 精美 PDF 詳批報告已成功生成至：{os.path.abspath(filename)}")

# =====================================================================
# ⚙️ 模組三：紫微斗數核心運算引擎
# =====================================================================
class ZiWeiEngine:
    def __init__(self, db_path, gender, year, month, day, hour_zhi, sub_type, longitude):
        self.gender = "乾造 (男命)" if gender == "1" else "坤造 (女命)"
        self.hour_zhi = hour_zhi
        self.is_late_sub = (hour_zhi == "子" and sub_type == "1") # 晚子時判斷 (23:00-24:00)

        # 基礎時間錨定
        # 為了安全地推算地支時辰對應的參考鐘點（子時用 0 點，丑時用 2 點...）
        hour_map_idx = DI_ZHI.index(hour_zhi)
        base_hour = 0 if hour_zhi == "子" and not self.is_late_sub else (23 if self.is_late_sub else (hour_map_idx * 2 - 1))
        
        raw_dt = datetime(year, month, day, max(0, base_hour), 0)
        
        # 1. 真太陽時校正
        self.true_dt = calculate_true_solar_time(raw_dt, longitude)
        
        # 2. 處理晚子時跨日換曆法邏輯
        base_solar = Solar.fromYmdHms(self.true_dt.year, self.true_dt.month, self.true_dt.day, self.true_dt.hour, self.true_dt.minute, self.true_dt.second)
        if self.is_late_sub:
            # 晚子時推進到隔天，但紫微斗數慣例：生年干支依據原日（以下會做orig_lunar保留生年干支）
            advanced_solar = base_solar.next(1)
            self.lunar = Lunar.fromSolar(advanced_solar)
        else:
            self.lunar = Lunar.fromSolar(base_solar)
            
        # 3. 獲取精準生年干支 (晚子時不變更生年干支)
        orig_lunar = Lunar.fromSolar(base_solar)
        self.year_gan = orig_lunar.getYearGan()
        self.year_zhi = orig_lunar.getYearZhi()
        
        self.db = sqlite3.connect(db_path)
        self.gong_位 = {}
        self.report_logs = []  
        self._init_mock_palaces()
        
    def _init_mock_palaces(self):
        for idx, zhi in enumerate(DI_ZHI):
            self.gong_位[zhi] = {
                "宮干": TIAN_GAN[idx % 10],
                "宮名": PALACES_BASE[idx],
                "原始主星": ["天同", "天機"] if idx == 4 else (["武曲"] if idx == 8 else [])
            }

    def log_print(self, log_type, title, text=""):
        if log_type == "H1":
            print(f"\n{title}")
            self.report_logs.append(("H1", title, ""))
        elif log_type == "BODY":
            print(text)
            self.report_logs.append(("BODY", "", text))

    def generate_palace_matrix(self):
        matrix = [["" for _ in range(4)] for _ in range(4)]
        matrix[0][0] = f"【巳】\n{self.gong_位['巳']['宮名']}\n{','.join(self.gong_位['巳']['原始主星'])}"
        matrix[0][1] = f"【午】\n{self.gong_位['午']['宮名']}\n{','.join(self.gong_位['午']['原始主星'])}"
        matrix[0][2] = f"【未】\n{self.gong_位['未']['宮名']}\n{','.join(self.gong_位['未']['原始主星'])}"
        matrix[0][3] = f"【申】\n{self.gong_位['申']['宮名']}\n{','.join(self.gong_位['申']['原始主星'])}"
        matrix[1][3] = f"【酉】\n{self.gong_位['酉']['宮名']}\n{','.join(self.gong_位['酉']['原始主星'])}"
        matrix[2][3] = f"【戌】\n{self.gong_位['戌']['宮名']}\n{','.join(self.gong_位['戌']['原始主星'])}"
        matrix[3][3] = f"【亥】\n{self.gong_位['亥']['宮名']}\n{','.join(self.gong_位['亥']['原始主星'])}"
        matrix[3][2] = f"【子】\n{self.gong_位['子']['宮名']}\n{','.join(self.gong_位['子']['原始主星'])}"
        matrix[3][1] = f"【丑】\n{self.gong_位['丑']['宮名']}\n{','.join(self.gong_位['丑']['原始主星'])}"
        matrix[3][0] = f"【寅】\n{self.gong_位['寅']['宮名']}\n{','.join(self.gong_位['寅']['原始主星'])}"
        matrix[2][0] = f"【卯】\n{self.gong_位['卯']['宮名']}\n{','.join(self.gong_位['卯']['原始主星'])}"
        matrix[1][0] = f"【辰】\n{self.gong_位['辰']['宮名']}\n{','.join(self.gong_位['辰']['原始主星'])}"
        matrix[1][1] = f"{self.gender} 大運命盤\n生年干支：{self.year_gan}{self.year_zhi}年\n時辰：{self.hour_zhi}時"
        return matrix

    def 調用資料庫進行十二宮深度解盤(self):
        self.log_print("H1", f" 🎯 第一部分：本命十二宮生年四化特質分析 ")
        cursor = self.db.cursor()
        
        cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (self.year_gan,))
        sihua_row = cursor.fetchone()
        natal_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            
        for p_name in PALACES_BASE:
            target_zhi = [z for z, info in self.gong_位.items() if info["宮名"] == p_name][0]
            info = self.gong_位[target_zhi]
            
            self.log_print("BODY", "", f"\n【{p_name}】 (落於地支「{info['宮干']}{target_zhi}」方位)")
            if not info["原始主星"]:
                self.log_print("BODY", "", "   ➔ [空宮無主星]：本宮無十四主星坐守。底層能量較易受對宮牽引。")
                continue
                
            for star in info["原始主星"]:
                cursor.execute("SELECT text FROM analysis WHERE palace=? AND star=?", (p_name, star))
                query_result = cursor.fetchone()
                base_text = query_result[0] if query_result else "基礎星性發揮影響，吉凶依據格局引動。"
                self.log_print("BODY", "", f"   ➔ 坐守星曜【{star}】核心斷語: {base_text}")
                    
                if star in natal_sihua_map:
                    n_type = natal_sihua_map[star]
                    self.log_print("BODY", "", f"      ✨ [生年四化鎖定] 本命【{star}】終身化【{n_type}】！")
                    if n_type == "祿":
                        self.log_print("BODY", "", f"         ➔ 一生福氣順遂，自帶福氣與資助。")
                    elif n_type == "權":
                        self.log_print("BODY", "", f"         ➔ 一生具備極強主導權、掌控欲與專業成就。")
                    elif n_type == "科":
                        self.log_print("BODY", "", f"         ➔ 擅長計劃、名聲佳，遇難能有貴人條理解厄。")
                    elif n_type == "忌":
                        self.log_print("BODY", "", f"         ➔ 此宮為終身心思核心與不安全感來源，易投入過多心神。")

    def calculate_lifetime_fortune(self, start_age=0, end_age=90):
        self.log_print("H1", f" 📊 第二部分：{start_age} 至 {end_age} 歲一生流年四化明確版動態批導 ")
        cursor = self.db.cursor()
        
        start_gan_idx = TIAN_GAN.index(self.year_gan)
        start_zhi_idx = DI_ZHI.index(self.year_zhi)
        
        for current_age in range(start_age, end_age + 1):
            liunian_gan = TIAN_GAN[(start_gan_idx + current_age) % 10]
            liunian_zhi = DI_ZHI[(start_zhi_idx + current_age) % 12]
            
            original_palace_name = self.gong_位[liunian_zhi]["宮名"]
            star_list = self.gong_位[liunian_zhi]["原始主星"]
            
            cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (liunian_gan,))
            sihua_row = cursor.fetchone()
            
            current_year_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            sihua_text = f"{sihua_row[0]}(祿) {sihua_row[1]}(權) {sihua_row[2]}(科) {sihua_row[3]}(忌)" if sihua_row else "無"
            
            self.log_print("BODY", "", f"\n【虛歲 {current_age:>2} 歲】 運勢干支：【{liunian_gan}{liunian_zhi}】年 | 流年命宮落於本命【{original_palace_name}】")
            self.log_print("BODY", "", f"   ➔ 當年環境四化背景：{sihua_text}")
            
            if not star_list:
                self.log_print("BODY", "", "   ➔ [流年命宮為空宮]：運勢易受對宮星曜牽引，環境多變動。")
            else:
                for star in star_list:
                    cursor.execute("SELECT text FROM analysis WHERE palace=? AND star=?", ("命宮", star))
                    query_result = cursor.fetchone()
                    base_text = query_result[0] if query_result else "基礎星性發揮作用。"
                    self.log_print("BODY", "", f"   ➔ 坐守星曜【{star}】特質: {base_text}")
                    
                    if star in current_year_sihua_map:
                         s_type = current_year_sihua_map[star]
                         self.log_print("BODY", "", f"      🔥 [動態引動成功] 當年【{star}】化【{s_type}】！")
                         if s_type == "祿":
                             self.log_print("BODY", "", f"         ➔ 【流年化祿】：代表得與順遂。今年機會叢生，資金或資源進帳順暢。")
                         elif s_type == "權":
                             self.log_print("BODY", "", f"         ➔ 【流年化權】：代表權勢與掌控。今年開創力強，有實質話語權。")
                         elif s_type == "科":
                             self.log_print("BODY", "", f"         ➔ 【流年化科】：代表名聲與條理。利於合約、考核、名譽提升。")
                         elif s_type == "忌":
                             self.log_print("BODY", "", f"         ➔ 【流年化忌】：代表執念與阻礙。防思慮打結、行政糾紛，宜守不宜攻。")
            self.log_print("BODY", "", "   " + "-" * 75)

    def close(self):
        self.db.close()

def init_mock_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, palace TEXT, star TEXT, text TEXT, UNIQUE(palace, star));")
    cursor.execute("CREATE TABLE IF NOT EXISTS sihua (gan TEXT PRIMARY KEY, lu TEXT, quan TEXT, ke TEXT, ji TEXT);")
    cursor.executemany("INSERT OR REPLACE INTO sihua VALUES(?,?,?,?,?)", [("甲", "廉貞", "破軍", "武曲", "太陽"), ("丙", "天同", "天機", "文昌", "廉貞")])
    cursor.executemany("INSERT OR REPLACE INTO analysis (palace, star, text) VALUES(?,?,?)", [
        ("命宮", "天同", "天同星主平順、福氣、具包容力。"), ("命宮", "天機", "天機星主聰穎、思維多變動、擅長企劃。"),
        ("財帛宮", "武曲", "武曲主掌正財、執行力極強、多勞多得。")
    ])
    conn.commit()
    conn.close()

# =====================================================================
# 🚀 終端機動態輸入與全自動批導區
# =====================================================================
if __name__ == "__main__":
    db_name = "ziwei_dynamic.db"
    init_mock_database(db_name)
    
    print("\n" + "★"*20 + " 紫微斗數真太陽時 PDF 批導系統啟動 " + "★"*20)
    
    # ─── 1. 性別選擇 ───
    gender_choice = input("1. 請選擇性別 [1] 男命 (乾造)  [2] 女命 (坤造): ").strip()
    while gender_choice not in ["1", "2"]:
        gender_choice = input("   輸入錯誤，請重新選擇 [1] 或 [2]: ").strip()
        
    # ─── 2. 出生年月日 ───
    y = int(input("2. 請輸入出生西元年 (如 1994): ").strip())
    m = int(input("3. 請輸入出生月份 (1-12): ").strip())
    d = int(input("4. 請輸入出生日期 (1-31): ").strip())
    
    # ─── 3. 時辰地支選單制 (1-子、2-丑...) ───
    print("\n5. 請選擇出生時辰地支：")
    print("   [1] 子時 (23:00-01:00)   [2] 丑時 (01:00-03:00)   [3] 寅時 (03:00-05:00)   [4] 卯時 (05:00-07:00)")
    print("   [5] 辰時 (07:00-09:00)   [6] 巳時 (09:00-11:00)   [7] 午時 (11:00-13:00)   [8] 未時 (13:00-15:00)")
    print("   [9] 申時 (15:00-17:00)  [10] 酉時 (17:00-19:00)  [11] 戌時 (19:00-21:00)  [12] 亥時 (21:00-23:00)")
    hour_choice = int(input("   請輸入時辰對應編號 (1-12): ").strip())
    while hour_choice < 1 or hour_choice > 12:
        hour_choice = int(input("   輸入超出範圍，請重新輸入 (1-12): ").strip())
    
    h_zhi = DI_ZHI[hour_choice - 1]
    
    # ─── 4. 子時二級選單（早子/晚子） ───
    sub_type = "2" # 預設非晚子時
    if h_zhi == "子":
        print("\n   ⚠️ 【檢測到子時輸入】請進一步區分：")
        print("   [1] 晚子時 (23:00 - 24:00) ➔ 屬於昨日深夜，日期會換日跨天推進")
        print("   [2] 早子時 (00:00 - 01:00) ➔ 屬於今日凌晨，日期維持當天")
        sub_type = input("   請選擇 [1] 或 [2]: ").strip()
        while sub_type not in ["1", "2"]:
            sub_type = input("   輸入錯誤，請重新選擇 [1] 晚子 或 [2] 早子: ").strip()

    # ─── 5. 地理觀測經度 ───
    lon_input = input("\n6. 請輸入出生地經度 (預設桃園 121.31，直接按 Enter 採用): ").strip()
    lon = float(lon_input) if lon_input else 121.31
    
    # ─── 6. 執行核心排盤與 0-90 歲推算 ───
    engine = ZiWeiEngine(db_name, gender_choice, y, m, d, h_zhi, sub_type, longitude=lon)
    engine.調用資料庫進行十二宮深度解盤()
    engine.calculate_lifetime_fortune(start_age=0, end_age=90)  # 火力全開推算至 90 歲
    
    # ─── 7. 導出為精美 PDF 報表 ───
    grid_matrix = engine.generate_palace_matrix()
    gender_lbl = "男命 (乾造)" if gender_choice == "1" else "女命 (坤造)"
    info_str = (f"基本身分: {gender_lbl} | 輸入基準日: {y}-{m:02d}-{d:02d} | 選擇時辰: {h_zhi}時 "
                f"{'(晚子)' if (h_zhi=='子' and sub_type=='1') else '(常規)'} | "
                f"太陽時校正落點: {engine.true_dt.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"生年干支: {engine.year_gan}{engine.year_zhi}")
    
    generate_ziwei_pdf("ziwei_final_report.pdf", info_str, grid_matrix, engine.report_logs)
    engine.close()