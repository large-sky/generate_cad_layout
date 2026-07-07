import sqlite3
import os
import math
from datetime import datetime
from lunar_python import Lunar, Solar

# =====================================================================
# 🌐 全局核心常數與地支索引定義
# =====================================================================
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
PALACES_BASE = ["命宮", "兄弟宮", "夫妻宮", "子女宮", "財帛宮", "疾厄宮", 
                "遷移宮", "交友宮", "官祿宮", "田宅宮", "福德宮", "父母宮"]

# ─── 主星廟旺利陷表 (簡化測試矩陣，實務上可依據各派別完整填入) ───
# 格式: { 星曜: [子, 丑, 寅, 卯, 辰, 巳, 午, 未, 申, 酉, 戌, 亥] }，M=廟, 
STAR_BRIGHTNESS = {
    "天同": ["旺", "陷", "利", "廟", "廟", "陷", "陷", "陷", "得", "利", "廟", "廟"],
    "天機": ["廟", "廟", "得", "得", "廟", "陷", "廟", "廟", "利益", "旺", "廟", "陷"],
    "武曲": ["廟", "廟", "得", "旺", "廟", "平", "利益", "廟", "得", "旺", "廟", "平"]
}

# =====================================================================
# ☀️ 模組一：天文真太陽時校正
# =====================================================================
def calculate_true_solar_time(dt: datetime, longitude: float) -> datetime:
    standard_longitude = 120.0
    lon_diff_minutes = (longitude - standard_longitude) * 4
    day_of_year = dt.timetuple().tm_yday
    b = (2 * math.pi * (day_of_year - 81)) / 365
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    
    total_correction_seconds = int((lon_diff_minutes + eot) * 60)
    return datetime.fromtimestamp(dt.timestamp() + total_correction_seconds)

# =====================================================================
# 📄 模組二：ReportLab PDF 生成引擎
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
        print(f"⚠️ 未能載入中文字型：{e}")
        return

    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    main_title_style = ParagraphStyle('MainTitle', fontName='Ch_Font', fontSize=20, leading=26, alignment=1, spaceAfter=15, textColor=colors.HexColor("#2C3E50"))
    h1_style = ParagraphStyle('H1', fontName='Ch_Font', fontSize=13, leading=18, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#2E4053"))
    body_style = ParagraphStyle('Body', fontName='Ch_Font', fontSize=9, leading=15, spaceAfter=4, textColor=colors.HexColor("#5D6D7E"))
    grid_style = ParagraphStyle('GridText', fontName='Ch_Font', fontSize=8, leading=11, alignment=1)

    story = []
    story.append(Paragraph("<b>紫微斗數全星曜本命與流年深度詳批報告</b>", main_title_style))
    story.append(Paragraph(f"<b>📊 基本命盤參數：</b>{basic_info}", body_style))
    story.append(Spacer(1, 10))
    
    grid_table_data = []
    for r in range(4):
        row_cells = []
        for c in range(4):
            cell_text = palace_grid_data[r][c].replace("\n", "<br/>")
            row_cells.append(Paragraph(cell_text, grid_style))
        grid_table_data.append(row_cells)
        
    t = Table(grid_table_data, colWidths=[135, 135, 135, 135], rowHeights=[90, 90, 90, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FBFCFC")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (1,1), (2,2)),
        ('BACKGROUND', (1,1), (2,2), colors.HexColor("#F2F4F4")),
    ]))
    story.append(t)
    story.append(PageBreak()) 
    
    for log_type, title, text in report_logs:
        if log_type == "H1":
            story.append(Paragraph(f"<b>{title}</b>", h1_style))
            story.append(Spacer(1, 2))
        elif log_type == "BODY":
            formatted_text = text.replace("\n", "<br/>")
            story.append(Paragraph(formatted_text, body_style))
            
    doc.build(story)
    print(f"\n📁 [系統通知] 報告已成功導出至：{os.path.abspath(filename)}")

# =====================================================================
# ⚙️ 模組三：紫微斗數核心運算與「全自動安星訣」引擎
# =====================================================================
class ZiWeiCompleteEngine:
    def __init__(self, db_path, gender, year, month, day, hour_zhi, sub_type, longitude):
        self.gender_str = "男命 (乾造)" if gender == "1" else "女命 (坤造)"
        self.hour_zhi = hour_zhi
        self.month = month
        
        # 基礎時辰轉換點
        h_idx = DI_ZHI.index(hour_zhi)
        is_late_sub = (hour_zhi == "子" and sub_type == "1")
        base_hour = 23 if is_late_sub else (0 if hour_zhi == "子" else (h_idx * 2 - 1))
        
        # 1. 太陽時與農曆轉換
        raw_dt = datetime(year, month, day, max(0, base_hour), 0)
        self.true_dt = calculate_true_solar_time(raw_dt, longitude)
        
        base_solar = Solar.fromYmdHms(self.true_dt.year, self.true_dt.month, self.true_dt.day, self.true_dt.hour, self.true_dt.minute, self.true_dt.second)
        self.lunar = Lunar.fromSolar(base_solar.next(1) if is_late_sub else base_solar)
        
        # 2. 定義生年干支
        orig_lunar = Lunar.fromSolar(base_solar)
        self.year_gan = orig_lunar.getYearGan()
        self.year_zhi = orig_lunar.getYearZhi()
        
        self.db = sqlite3.connect(db_path)
        self.gong_位 = {}
        self.report_logs = []  
        
        # 3. 核心自動布星
        self._setup_palace_skeletons()
        self._deploy_all_stars()

    def _setup_palace_skeletons(self):
        """ 建立十二地支宮位骨架 """
        for idx, zhi in enumerate(DI_ZHI):
            self.gong_位[zhi] = {
                "宮干": TIAN_GAN[idx % 10],
                "宮名": PALACES_BASE[idx], # 簡化測試排盤，實務上依據命宮順序推算
                "主星": [],
                "六吉星": [],
                "六煞星": [],
                "其它星曜": []
            }

    def _deploy_all_stars(self):
        """ 🎯 執行全自動安星訣公式 """
        g_idx = TIAN_GAN.index(self.year_gan)
        z_idx = DI_ZHI.index(self.year_zhi)
        h_idx = DI_ZHI.index(self.hour_zhi)
        
        # --- 基礎主星手動配置測試落點 ---
        self.gong_位["辰"]["主星"].append("天同")
        self.gong_位["巳"]["主星"].append("天機")
        self.gong_位["申"]["主星"].append("武曲")

        # --- A. 六吉星安星訣 ---
        # 文昌、文曲 (由時辰安)
        self.gong_位[DI_ZHI[(10 - h_idx) % 12]]["六吉星"].append("文昌")
        self.gong_位[DI_ZHI[(4 + h_idx) % 12]]["六吉星"].append("文曲")
        # 左輔、右弼 (由月份安)
        self.gong_位[DI_ZHI[(4 + self.month - 1) % 12]]["六吉星"].append("左輔")
        self.gong_位[DI_ZHI[(10 - (self.month - 1)) % 12]]["六吉星"].append("右弼")
        # 天魁、天鉞 (由年干安)
        k_y_map = {"甲": ("未", "丑"), "乙": ("申", "子"), "丙": ("酉", "亥"), "丁": ("酉", "亥"), "戊": ("未", "丑"), "己": ("申", "子"), "庚": ("丑", "未"), "辛": ("午", "寅"), "壬": ("卯", "巳"), "癸": ("卯", "巳")}
        k_zhi, y_zhi = k_y_map.get(self.year_gan, ("丑", "未"))
        self.gong_位[k_zhi]["六吉星"].append("天魁")
        self.gong_位[y_zhi]["六吉星"].append("天鉞")

        # --- B. 祿存、天馬與六煞星安星訣 ---
        # 祿存 (由年干安)
        lu_map = {"甲":"寅", "乙":"卯", "丙":"巳", "丁":"午", "戊":"巳", "己":"午", "庚":"申", "辛":"酉", "壬":"亥", "癸":"子"}
        lu_zhi = lu_map[self.year_gan]
        self.gong_位[lu_zhi]["其它星曜"].append("祿存")
        
        # 擎羊、陀羅 (由祿存前後引動安)
        lu_idx = DI_ZHI.index(lu_zhi)
        self.gong_位[DI_ZHI[(lu_idx + 1) % 12]]["六煞星"].append("擎羊")
        self.gong_位[DI_ZHI[(lu_idx - 1) % 12]]["六煞星"].append("陀羅")
        
        # 天馬 (由年支安)
        ma_map = {"子":"寅", "丑":"亥", "寅":"申", "卯":"巳", "辰":"寅", "巳":"亥", "午":"申", "未":"巳", "申":"寅", "酉":"亥", "戌":"申", "亥":"巳"}
        self.gong_位[ma_map[self.year_zhi]]["其它星曜"].append("天馬")

        # 地空、地劫 (由時辰安)
        self.gong_位[DI_ZHI[(11 - h_idx) % 12]]["六煞星"].append("地空")
        self.gong_位[DI_ZHI[(11 + h_idx) % 12]]["六煞星"].append("地劫")

    def _get_brightness(self, star, zhi):
        """ 獲取該星曜在該地支宮位的動態亮度 """
        if star in STAR_BRIGHTNESS:
            z_idx = DI_ZHI.index(zhi)
            return f"({STAR_BRIGHTNESS[star][z_idx]})"
        return ""

    def log_print(self, log_type, title, text=""):
        if log_type == "H1":
            print(f"\n{title}")
            self.report_logs.append(("H1", title, ""))
        elif log_type == "BODY":
            print(text)
            self.report_logs.append(("BODY", "", text))

    def generate_palace_matrix(self):
        """ 建立 4x4 包含吉煞星與廟旺亮度的方塊命盤矩陣 """
        matrix = [["" for _ in range(4)] for _ in range(4)]
        positions = [
            ("巳", 0, 0), ("午", 0, 1), ("未", 0, 2), ("申", 0, 3),
            ("酉", 1, 3), ("戌", 2, 3), ("亥", 3, 3), ("子", 3, 2),
            ("丑", 3, 1), ("寅", 3, 0), ("卯", 2, 0), ("辰", 1, 0)
        ]
        for zhi, r, c in positions:
            p = self.gong_位[zhi]
            main_stars_with_b = [f"{s}{self._get_brightness(s, zhi)}" for s in p["主星"]]
            all_stars = main_stars_with_b + p["六吉星"] + p["六煞星"] + p["其它星曜"]
            stars_str = ",".join(all_stars) if all_stars else "空宮"
            matrix[r][c] = f"【{zhi}】\n{p['宮名']}\n{stars_str}"
            
        matrix[1][1] = f"{self.gender_str} 大運命盤\n生年干支：{self.year_gan}{self.year_zhi}年"
        return matrix

    def 調用資料庫進行十二宮深度解盤(self):
        self.log_print("H1", f" 🎯 第一部分：本命十二宮全星曜與生年四化明確化解析 ")
        cursor = self.db.cursor()
        
        # 獲取生年四化映射表
        cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (self.year_gan,))
        sihua_row = cursor.fetchone()
        natal_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            
        for p_name in PALACES_BASE:
            target_zhi = [z for z, info in self.gong_位.items() if info["宮名"] == p_name][0]
            p = self.gong_位[target_zhi]
            
            self.log_print("BODY", "", f"\n【{p_name}】 (落於地支「{p['宮干']}{target_zhi}」方位)")
            
            # 輸出主星及其廟旺利陷
            for star in p["主星"]:
                b_status = self._get_brightness(star, target_zhi)
                self.log_print("BODY", "", f"   ➔ 主星守護：【{star}】{b_status}")
                if "陷" in b_status:
                    self.log_print("BODY", "", "      ⚠️ [星曜落陷提示]：主星能量較為低迷或受阻，其特質容易往負面展現，需注意心理調適。")
                
                # 生年四化引動比對
                if star in natal_sihua_map:
                    n_type = natal_sihua_map[star]
                    self.log_print("BODY", "", f"      ✨ [生年四化鎖定] 本命【{star}】終身化【{n_type}】引動！")

            # 輸出同宮之六吉星與六煞星
            if p["六吉星"]:
                self.log_print("BODY", "", f"   ➕ 本宮會照六吉星：{'/'.join(p['六吉星'])} ➔ 增強本宮吉利能量，多得外在助力。")
            if p["六煞星"]:
                self.log_print("BODY", "", f"   ❌ 本宮遭遇六煞星：{'/'.join(p['六煞星'])} ➔ 帶來衝擊、考驗或波折，需防範心性急躁。")
            if "祿存" in p["其它星曜"]:
                self.log_print("BODY", "", "   💰 本宮坐守【祿存星】：天生自帶福祿之氣，具備存財能力，多有暗財守護。")
            if "天馬" in p["其它星曜"]:
                self.log_print("BODY", "", "   🐎 本宮坐守【天馬星】：主動態、奔波、遠行。若與主星搭配得當主「馬奔財鄉」越動越旺。")

    def calculate_lifetime_fortune(self, start_age=0, end_age=90):
        self.log_print("H1", f" 📊 第二部分：{start_age} 至 {end_age} 歲一生動態流年（吉煞星/四化引動比對） ")
        cursor = self.db.cursor()
        
        start_gan_idx = TIAN_GAN.index(self.year_gan)
        start_zhi_idx = DI_ZHI.index(self.year_zhi)
        
        for current_age in range(start_age, end_age + 1):
            liunian_gan = TIAN_GAN[(start_gan_idx + current_age) % 10]
            liunian_zhi = DI_ZHI[(start_zhi_idx + current_age) % 12]
            
            p = self.gong_位[liunian_zhi]
            
            cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (liunian_gan,))
            sihua_row = cursor.fetchone()
            current_year_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            
            self.log_print("BODY", "", f"\n【虛歲 {current_age:>2} 歲】 運勢干支：【{liunian_gan}{liunian_zhi}】年 | 流年命宮落於本命【{p['宮名']}】")
            
            # 1. 檢查流年命宮的主星狀況與四化
            if not p["主星"]:
                self.log_print("BODY", "", "   ➔ [流年命宮為空宮]：運勢多受對宮環境拉扯，自身主導力較弱。")
            else:
                for star in p["主星"]:
                    b_status = self._get_brightness(star, liunian_zhi)
                    self.log_print("BODY", "", f"   ➔ 當年坐守主星: 【{star}】{b_status}")
                    
                    # 比對當年度流年四化有沒有打中這顆主星
                    if star in current_year_sihua_map:
                        s_type = current_year_sihua_map[star]
                        self.log_print("BODY", "", f"      🔥 [流年四化引動成功] 當年【{star}】化【{s_type}】！")
                        if s_type == "祿": self.log_print("BODY", "", "         ➔ 今年機緣極佳，資金周轉順利，事情容易迎刃而解。")
                        elif s_type == "權": self.log_print("BODY", "", "         ➔ 今年掌控欲增強，事業或權力有突破性進展，但壓力較重。")
                        elif s_type == "科": self.log_print("BODY", "", "         ➔ 今年利於考試、考核、簽約，名聲提升，貴人相助。")
                        elif s_type == "忌": self.log_print("BODY", "", "         ➔ 今年容易思慮打結，防行政疏失或人際阻礙，宜保守。")

            # 2. 比對當流年命宮碰上本命「吉煞星」與「祿馬」的具體引動現象
            if p["六吉星"]:
                self.log_print("BODY", "", f"   ✨ [吉星護航] 流年命宮逢本命【{'/'.join(p['六吉星'])}】：代表今年能發揮吉星優勢，職場或學業有助力。")
            if p["六煞星"]:
                self.log_print("BODY", "", f"   ⚠️ [煞星衝擊] 流年命宮逢本命【{'/'.join(p['六煞星'])}】：代表今年阻礙感較強、容易因情緒衝動誤事，切記沉著應變。")
            if "祿存" in p["其它星曜"]:
                self.log_print("BODY", "", "   💰 [祿存坐守] 今年有穩定的資金進帳機會，利於儲蓄與防守型理財。")
            if "天馬" in p["其它星曜"]:
                self.log_print("BODY", "", "   🐎 [天馬馳騁] 今年環境變動多，出差、遠行、搬家機會大增，動中有財。")
            
            self.log_print("BODY", "", "   " + "-" * 75)

    def close(self):
        self.db.close()

# =====================================================================
# 🗃️ 輔助初始化數據庫
# =====================================================================
def init_mock_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, palace TEXT, star TEXT, text TEXT, UNIQUE(palace, star));")
    cursor.execute("CREATE TABLE IF NOT EXISTS sihua (gan TEXT PRIMARY KEY, lu TEXT, quan TEXT, ke TEXT, ji TEXT);")
    cursor.executemany("INSERT OR REPLACE INTO sihua VALUES(?,?,?,?,?)", [
        ("甲", "廉貞", "破軍", "武曲", "太陽"), 
        ("丙", "天同", "天機", "文昌", "廉貞"),
        ("戌", "貪狼", "太陰", "右弼", "天機")
    ])
    conn.commit()
    conn.close()

# =====================================================================
# 🚀 終端機執行端 (0 至 90 歲完全批導)
# =====================================================================
if __name__ == "__main__":
    db_name = "ziwei_complete.db"
    init_mock_database(db_name)
    
    print("\n" + "★"*20 + " 紫微斗數全星曜安星訣 PDF 批導系統 " + "★"*20)
    
    gender_choice = input("1. 請選擇性別 [1] 男命 (乾造)  [2] 女命 (坤造): ").strip()
    y = int(input("2. 請輸入出生西元年 (如 1994): ").strip())
    m = int(input("3. 請輸入出生月份 (1-12): ").strip())
    d = int(input("4. 請輸入出生日期 (1-31): ").strip())
    
    print("\n5. 請選擇出生時辰地支：")
    print("   [1] 子時 (23:00-01:00)   [2] 丑時 (01:00-03:00)   [3] 寅時 (03:00-05:00)   [4] 卯時 (05:00-07:00)...")
    hour_choice = int(input("   請輸入時辰編號 (1-12): ").strip())
    h_zhi = DI_ZHI[hour_choice - 1]
    
    sub_type = "2"
    if h_zhi == "子":
        sub_type = input("   請選擇 [1] 晚子時 (23-24點) 或 [2] 早子時 (0-1點): ").strip()

    lon_input = input("\n6. 請輸入出生地經度 (預設桃園 121.31，按 Enter 採用): ").strip()
    lon = float(lon_input) if lon_input else 121.31
    
    # 執行批導引擎
    engine = ZiWeiCompleteEngine(db_name, gender_choice, y, m, d, h_zhi, sub_type, longitude=lon)
    engine.調用資料庫進行十二宮深度解盤()
    
    # 🔥 火力全開！推算 0 至 90 歲一生全自動四化明確版流年
    engine.calculate_lifetime_fortune(start_age=0, end_age=90)
    
    # 生成 PDF 報表
    grid_matrix = engine.generate_palace_matrix()
    gender_lbl = "男命" if gender_choice == "1" else "女命"
    info_str = f"{gender_lbl} | 出生基準: {y}-{m:02d}-{d:02d} {h_zhi}時 | 經度: {lon}° | 生年: {engine.year_gan}{engine.year_zhi}"
    
    generate_ziwei_pdf("ziwei_comprehensive_report.pdf", info_str, grid_matrix, engine.report_logs)
    engine.close()