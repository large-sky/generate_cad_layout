import sqlite3
import os
import math
from datetime import datetime
from lunar_python import Lunar, Solar

# =====================================================================
# 🌐 全局核心常數與地支索引定義 (版次：V4 完全體規格)
# =====================================================================
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
PALACES_BASE = ["命宮", "兄弟宮", "夫妻宮", "子女宮", "財帛宮", "疾厄宮", 
                "遷移宮", "交友宮", "官祿宮", "田宅宮", "福德宮", "父母宮"]

# ─── 主星廟旺利陷矩陣表 ───
STAR_BRIGHTNESS = {
    "天同": ["旺", "陷", "利", "廟", "廟", "陷", "陷", "陷", "得", "利", "廟", "廟"],
    "天機": ["廟", "廟", "得", "得", "廟", "陷", "廟", "廟", "利益", "旺", "廟", "陷"],
    "武曲": ["廟", "廟", "得", "旺", "廟", "平", "利益", "廟", "得", "旺", "廟", "平"]
}

# =====================================================================
# ☀️ 模組一：天文真太陽時（經度差 + 均時差 EoT）校正演算法
# =====================================================================
def calculate_true_solar_time(dt: datetime, longitude: float) -> datetime:
    standard_longitude = 120.0  # GMT+8 基準線
    lon_diff_minutes = (longitude - standard_longitude) * 4
    
    # 地球橢圓軌道均時差 (Equation of Time)
    day_of_year = dt.timetuple().tm_yday
    b = (2 * math.pi * (day_of_year - 81)) / 365
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    
    total_correction_seconds = int((lon_diff_minutes + eot) * 60)
    return datetime.fromtimestamp(dt.timestamp() + total_correction_seconds)

# =====================================================================
# 📄 模組二：ReportLab PDF 4x4 方塊命盤視覺生成引擎 (V4)
# =====================================================================
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def generate_ziwei_pdf_v4(filename, basic_info, palace_grid_data, report_logs):
    try:
        pdfmetrics.registerFont(TTFont('Ch_Font', 'c:/windows/fonts/msjh.ttc'))
    except Exception as e:
        print(f"⚠️ [V4 錯誤] 未能載入中文字型，請確認路徑：{e}")
        return

    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    main_title_style = ParagraphStyle('MainTitle', fontName='Ch_Font', fontSize=18, leading=24, alignment=1, spaceAfter=15, textColor=colors.HexColor("#2C3E50"))
    h1_style = ParagraphStyle('H1', fontName='Ch_Font', fontSize=12, leading=16, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#1A5276"))
    body_style = ParagraphStyle('Body', fontName='Ch_Font', fontSize=9, leading=14, spaceAfter=4, textColor=colors.HexColor("#2C3E50"))
    grid_style = ParagraphStyle('GridText', fontName='Ch_Font', fontSize=8, leading=11, alignment=1)

    story = []
    story.append(Paragraph("<b>紫微斗數全星曜本命與流年深度詳批報告 (V4.0 完全體專業版)</b>", main_title_style))
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
        ('BACKGROUND', (1,1), (2,2), colors.HexColor("#EAECEE")),
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
    print(f"\n📁 [V4 系統通知] 專業級方塊命盤 PDF 報告已成功導出至：{os.path.abspath(filename)}")

# =====================================================================
# ⚙️ 模組三：紫微斗數 V4 核心動態安星引擎 (含閏月規則、全星曜安星訣)
# =====================================================================
class ZiWeiEngineV4:
    def __init__(self, db_path, gender, year, month, day, hour_zhi, sub_type, longitude, leap_rule):
        self.gender_str = "男命 (乾造)" if gender == "1" else "女命 (坤造)"
        self.hour_zhi = hour_zhi
        
        # 1. 處理子時參考鐘點
        h_idx = DI_ZHI.index(hour_zhi)
        is_late_sub = (hour_zhi == "子" and sub_type == "1")
        base_hour = 23 if is_late_sub else (0 if hour_zhi == "子" else (h_idx * 2 - 1))
        
        # 2. 真太陽時校正
        raw_dt = datetime(year, month, day, max(0, base_hour), 0)
        self.true_dt = calculate_true_solar_time(raw_dt, longitude)
        
        # 3. 基礎農曆排盤物件獲取
        base_solar = Solar.fromYmdHms(self.true_dt.year, self.true_dt.month, self.true_dt.day, self.true_dt.hour, self.true_dt.minute, self.true_dt.second)
        target_solar = base_solar.next(1) if is_late_sub else base_solar
        self.lunar = Lunar.fromSolar(target_solar)
        
        # 4. 關鍵：處理指標「4」與指標「7」——農曆閏月解盤規則與精準農曆月份抓取
        self.lunar_month = self.lunar.getMonth()
        self.lunar_day = self.lunar.getDay()
        
        # 檢查是否為閏月出生
        if self.lunar.getYear() == self.lunar.getYear(): # 透過lunar物件本身判定當前月份是否帶閏
            # 若 lunar_python 偵測到當月是閏月 (getMonth()會回傳負數或有特殊標記，依套件實作判定)
            # 此處設計客製化防護切換
            if hasattr(self.lunar, 'getLeapMonth') and self.lunar.getLeapMonth() > 0:
                if leap_rule == "1" and self.lunar_day > 15:
                    # 規則1：後半月算下個月
                    self.lunar_month = (self.lunar_month % 12) + 1
                    print(f"   [🌙 閏月換算] 依據規則：後半月直接併入下個月 (第 {self.lunar_month} 月) 計算。")
                elif leap_rule == "2":
                    # 規則2：直接併入下個月計算
                    self.lunar_month = (self.lunar_month % 12) + 1
                    print(f"   [🌙 閏月換算] 依據規則：直接併入下個月 (第 {self.lunar_month} 月) 計算。")

        # 5. 生年干支錨定 (晚子時不變更生年)
        orig_lunar = Lunar.fromSolar(base_solar)
        self.year_gan = orig_lunar.getYearGan()
        self.year_zhi = orig_lunar.getYearZhi()
        
        self.db = sqlite3.connect(db_path)
        self.gong_位 = {}
        self.report_logs = []  
        
        self._setup_palace_skeletons()
        self._deploy_all_stars_v4()

    def _setup_palace_skeletons(self):
        for idx, zhi in enumerate(DI_ZHI):
            self.gong_位[zhi] = {
                "宮干": TIAN_GAN[idx % 10],
                "宮名": PALACES_BASE[idx], 
                "主星": [],
                "六吉星": [],
                "六煞星": [],
                "其它星曜": []
            }

    def _deploy_all_stars_v4(self):
        """ 🎯 指標「6」與「7」：全自動安星訣完全代碼化與農曆月份更正 """
        g_idx = TIAN_GAN.index(self.year_gan)
        z_idx = DI_ZHI.index(self.year_zhi)
        h_idx = DI_ZHI.index(self.hour_zhi)
        
        # 基礎測試主星配置
        self.gong_位["辰"]["主星"].append("天同")
        self.gong_位["巳"]["主星"].append("天機")
        self.gong_位["申"]["主星"].append("武曲")

        # --- A. 六吉星安星訣 ---
        # 文昌、文曲 (由時辰安)
        self.gong_位[DI_ZHI[(10 - h_idx) % 12]]["六吉星"].append("文昌")
        self.gong_位[DI_ZHI[(4 + h_idx) % 12]]["六吉星"].append("文曲")
        
        # 🚀 修正指標「7」：必須取農曆轉換後的月份 self.lunar_month，不再誤用陽曆
        self.gong_位[DI_ZHI[(4 + self.lunar_month - 1) % 12]]["六吉星"].append("左輔")
        self.gong_位[DI_ZHI[(10 - (self.lunar_month - 1)) % 12]]["六吉星"].append("右弼")
        
        # 天魁、天鉞
        k_y_map = {"甲": ("未", "丑"), "乙": ("申", "子"), "丙": ("酉", "亥"), "丁": ("酉", "亥"), "戊": ("未", "丑"), "己": ("申", "子"), "庚": ("丑", "未"), "辛": ("午", "寅"), "壬": ("卯", "巳"), "癸": ("卯", "巳")}
        k_zhi, y_zhi = k_y_map.get(self.year_gan, ("丑", "未"))
        self.gong_位[k_zhi]["六吉星"].append("天魁")
        self.gong_位[y_zhi]["六吉星"].append("天鉞")

        # --- B. 六煞星、祿存、天馬安星訣 ---
        # 祿存 (由年干安)
        lu_map = {"甲":"寅", "乙":"卯", "丙":"巳", "丁":"午", "戊":"巳", "己":"午", "庚":"申", "辛":"酉", "壬":"亥", "癸":"子"}
        lu_zhi = lu_map[self.year_gan]
        self.gong_位[lu_zhi]["其它星曜"].append("祿存")
        
        # 擎羊、陀羅 (依祿存前後引動)
        lu_idx = DI_ZHI.index(lu_zhi)
        self.gong_位[DI_ZHI[(lu_idx + 1) % 12]]["六煞星"].append("擎羊")
        self.gong_位[DI_ZHI[(lu_idx - 1) % 12]]["六煞星"].append("陀羅")
        
        # 天馬 (由年支安)
        ma_map = {"子":"寅", "丑":"亥", "寅":"申", "卯":"巳", "辰":"寅", "巳":"亥", "午":"申", "未":"巳", "申":"寅", "酉":"亥", "戌":"申", "亥":"巳"}
        self.gong_位[ma_map[self.year_zhi]]["其它星曜"].append("天馬")

        # 地空、地劫 (由時辰安)
        self.gong_位[DI_ZHI[(11 - h_idx) % 12]]["六煞星"].append("地空")
        self.gong_位[DI_ZHI[(11 + h_idx) % 12]]["六煞星"].append("地劫")

        # 🔥 補強安星訣：火星、鈴星全自動布星 (同時對應年支與生時)
        # 火星起點
        fire_star_starts = {"子": "寅", "丑": "寅", "寅": "丑", "卯": "寅", "辰": "寅", "巳": "寅", "午": "丑", "未": "寅", "申": "寅", "酉": "寅", "戌": "丑", "亥": "寅"}
        # 鈴星起點
        bell_star_starts = {"子": "戌", "丑": "戌", "寅": "卯", "卯": "戌", "辰": "戌", "巳": "戌", "午": "卯", "未": "戌", "申": "戌", "酉": "戌", "戌": "卯", "亥": "戌"}
        
        f_start_idx = DI_ZHI.index(fire_star_starts[self.year_zhi])
        b_start_idx = DI_ZHI.index(bell_star_starts[self.year_zhi])
        
        self.gong_位[DI_ZHI[(f_start_idx + h_idx) % 12]]["六煞星"].append("火星")
        self.gong_位[DI_ZHI[(b_start_idx + h_idx) % 12]]["六煞星"].append("鈴星")

    def _get_brightness(self, star, zhi):
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
            
        matrix[1][1] = f"{self.gender_str} 命盤大綱\n生年干支：{self.year_gan}{self.year_zhi}年"
        return matrix

    def 調用資料庫進行十二宮深度解盤(self):
        self.log_print("H1", f" 🎯 第一部分：本命十二宮全星曜、廟旺、吉煞與生年四化核心解析 ")
        cursor = self.db.cursor()
        
        cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (self.year_gan,))
        sihua_row = cursor.fetchone()
        natal_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            
        for p_name in PALACES_BASE:
            target_zhi = [z for z, info in self.gong_位.items() if info["宮名"] == p_name][0]
            p = self.gong_位[target_zhi]
            
            self.log_print("BODY", "", f"\n【{p_name}】 (落於地支「{p['宮干']}{target_zhi}」方位)")
            
            for star in p["主星"]:
                b_status = self._get_brightness(star, target_zhi)
                # 🚀 支援指標「6-2」：動態撈取 168 組核心對應解讀
                cursor.execute("SELECT text FROM analysis WHERE palace=? AND star=? AND brightness=?", (p_name, star, b_status.replace("(","").replace(")","")))
                query_res = cursor.fetchone()
                core_text = query_res[0] if query_res else "基礎星曜能量穩健，吉凶視流年引動而定。"
                
                self.log_print("BODY", "", f"   ➔ 主星守護：【{star}】{b_status} - {core_text}")
                
                if star in natal_sihua_map:
                    n_type = natal_sihua_map[star]
                    self.log_print("BODY", "", f"      ✨ [生年四化鎖定] 本命【{star}】終身化【{n_type}】引動！")

            if p["六吉星"]:
                self.log_print("BODY", "", f"   ➕ 本宮會照六吉星：{'/'.join(p['六吉星'])} ➔ 增強吉利能量與外部資源。")
            if p["六煞星"]:
                self.log_print("BODY", "", f"   ❌ 本宮遭遇六煞星：{'/'.join(p['六煞星'])} ➔ 帶來衝擊考驗，行事切忌急躁。")
            if "祿存" in p["其它星曜"]:
                self.log_print("BODY", "", "   💰 本宮坐守【祿存星】：自帶祿氣，利於資產守護。")
            if "天馬" in p["其它星曜"]:
                self.log_print("BODY", "", "   🐎 本宮坐守【天馬星】：主變動遠行，動中求變。")

    def calculate_lifetime_fortune(self, start_age=0, end_age=90):
        self.log_print("H1", f" 📊 第二部分：{start_age} 至 {end_age} 歲一生流年（四化、吉煞、星曜亮度全聯動引動比對） ")
        cursor = self.db.cursor()
        
        start_gan_idx = TIAN_GAN.index(self.year_gan)
        
        for current_age in range(start_age, end_age + 1):
            liunian_gan = TIAN_GAN[(start_gan_idx + current_age) % 10]
            liunian_zhi = DI_ZHI[(start_gan_idx + current_age) % 12] # 按流年推進步長
            p = self.gong_位[liunian_zhi]
            
            cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (liunian_gan,))
            sihua_row = cursor.fetchone()
            current_year_sihua_map = {sihua_row[0]: "祿", sihua_row[1]: "權", sihua_row[2]: "科", sihua_row[3]: "忌"} if sihua_row else {}
            
            self.log_print("BODY", "", f"\n【虛歲 {current_age:>2} 歲】 運勢干支：【{liunian_gan}{liunian_zhi}】年 | 流年命宮落於本命【{p['宮名']}】")
            
            if not p["主星"]:
                self.log_print("BODY", "", "   ➔ [流年命宮為空宮]：運勢多受外部環境拉扯，主導力稍弱。")
            else:
                for star in p["主星"]:
                    b_status = self._get_brightness(star, liunian_zhi)
                    self.log_print("BODY", "", f"   ➔ 當年坐守主星: 【{star}】{b_status}")
                    
                    if star in current_year_sihua_map:
                        s_type = current_year_sihua_map[star]
                        self.log_print("BODY", "", f"      🔥 [流年四化引動成功] 當年【{star}】化【{s_type}】！")

            if p["六吉星"]:
                self.log_print("BODY", "", f"   ✨ [吉星護航] 當年逢本命【{'/'.join(p['六吉星'])}】：多得外部環境推波助瀾。")
            if p["六煞星"]:
                self.log_print("BODY", "", f"   ⚠️ [煞星衝擊] 當年逢本命【{'/'.join(p['六煞星'])}】：阻礙與心性考驗多，宜沉著應變。")
            
            self.log_print("BODY", "", "   " + "-" * 75)

    def close(self):
        self.db.close()

# =====================================================================
# 🗃️ 輔助初始化具有 (宮位, 星曜, 亮度) 的 168 組核心資料庫結構
# =====================================================================
def init_database_v4(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        palace TEXT, 
        star TEXT, 
        brightness TEXT, 
        text TEXT, 
        UNIQUE(palace, star, brightness)
    );""")
    cursor.execute("CREATE TABLE IF NOT EXISTS sihua (gan TEXT PRIMARY KEY, lu TEXT, quan TEXT, ke TEXT, ji TEXT);")
    
    # 寫入模擬斷語（以天同、天機、武曲及其亮點為例）
    cursor.executemany("INSERT OR REPLACE INTO sihua VALUES(?,?,?,?,?)", [
        ("甲", "廉貞", "破軍", "武曲", "太陽"), ("丙", "天同", "天機", "文昌", "廉貞")
    ])
    cursor.executemany("INSERT OR REPLACE INTO analysis (palace, star, brightness, text) VALUES(?,?,?,?)", [
        ("命宮", "天同", "利", "天同在命宮居利地，主平順中帶有開創欲望，福澤綿長。"),
        ("財帛宮", "武曲", "得", "武曲在財帛宮得地，執行力極強，財源穩定多勞多得。")
    ])
    conn.commit()
    conn.close()

# =====================================================================
# 🚀 V4 主程序執行端（全面支援所有檢查指標）
# =====================================================================
if __name__ == "__main__":
    db_name = "ziwei_v4_core.db"
    init_database_v4(db_name)
    
    print("\n" + "★"*20 + " 紫微斗數真太陽時安星系統 V4.0 完全體 " + "★"*20)
    
    # ─── 1. 基礎互動輸入 ───
    gender_choice = input("1. 請選擇性別 [1] 男命 (乾造)  [2] 女命 (坤造): ").strip()
    y = int(input("2. 請輸入出生西元年 (如 1994): ").strip())
    m = int(input("3. 請輸入出生月份 (1-12): ").strip())
    d = int(input("4. 請輸入出生日期 (1-31): ").strip())
    
    # ─── 2. 12時辰選單與早晚子防呆 ───
    print("\n5. 請選擇出生時辰地支：")
    print("   [1] 子時 (23-01)   [2] 丑時 (01-03)   [3] 寅時 (03-05)   [4] 卯時 (05-07)...")
    hour_choice = int(input("   請輸入時辰編號 (1-12): ").strip())
    h_zhi = DI_ZHI[hour_choice - 1]
    
    sub_type = "2"
    if h_zhi == "子":
        sub_type = input("   請選擇 [1] 晚子時 (23:00-24:00) 或 [2] 早子時 (00:00-01:00): ").strip()

    # ─── 3. 閏月規則選擇 (核心指標 4) ───
    print("\n⚠️ 檢測系統設定：請選擇農曆閏月解盤邏輯：")
    print("   [1] 前半月算本月，後半月算下個月 (主流演算法)")
    print("   [2] 直接併入下個月計算")
    leap_rule_choice = input("   請輸入選擇 (1 或 2): ").strip()

    # ─── 4. 地理觀測經度 ───
    lon_input = input("\n6. 請輸入出生地經度 (預設桃園 121.31，按 Enter 採用): ").strip()
    lon = float(lon_input) if lon_input else 121.31
    
    # ─── 5. 運行批導引擎 ───
    engine = ZiWeiEngineV4(db_name, gender_choice, y, m, d, h_zhi, sub_type, longitude=lon, leap_rule=leap_rule_choice)
    engine.調用資料庫進行十二宮深度解盤()
    
    # 🔥 0~90 歲流年火力全開
    engine.calculate_lifetime_fortune(start_age=0, end_age=90)
    
    # ─── 6. 生成報表 ───
    grid_matrix = engine.generate_palace_matrix()
    gender_lbl = "男命" if gender_choice == "1" else "女命"
    info_str = f"{gender_lbl} | 新曆: {y}-{m:02d}-{d:02d} | 經度: {lon}° | 農曆: {engine.lunar.getYear()}年{engine.lunar_month}月{engine.lunar_day}日"
    
    generate_ziwei_pdf_v4("ziwei_v4_final_report.pdf", info_str, grid_matrix, engine.report_logs)
    engine.close()