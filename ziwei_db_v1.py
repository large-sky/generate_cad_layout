import sqlite3
import os
from lunar_python import Lunar, Solar
import wcwidth

# --- 基礎常數定義 ---
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
PALACES_BASE = ["命宮", "兄弟", "夫妻", "子女", "財帛", "疾厄", "遷移", "交友", "官祿", "田宅", "福德", "父母"]

GRID_LAYOUT = [
    ["巳", "午", "未", "申"],
    ["辰", "中", "中", "酉"],
    ["卯", "中", "中", "戌"],
    ["寅", "丑", "子", "亥"]
]

class ZiWeiEngine:
    def __init__(self, db_conn, year, month, day, hour_zhi, gender, sub_type, is_lunar=False):
        self.db = db_conn
        self.gender = gender  # "1" 為男, "2" 為女
        self.hour_zhi = hour_zhi
        self.is_late_sub = (hour_zhi == "子" and sub_type == "1") # 23:00-24:00 晚子
        
        # 日期與換日計算
        if not is_lunar:
            base_solar = Solar.fromYmdHms(year, month, day, 12, 0, 0)
            self.solar = base_solar.next(1) if self.is_late_sub else base_solar
            self.lunar = Lunar.fromSolar(self.solar)
        else:
            base_lunar = Lunar.fromYmd(year, month, day)
            if self.is_late_sub:
                advanced_solar = base_lunar.getSolar().next(1)
                self.lunar = Lunar.fromSolar(advanced_solar)
                self.solar = advanced_solar
            else:
                self.lunar = base_lunar
                self.solar = self.lunar.getSolar()
                
        # 獲取生年天干（晚子時不變更生年干支）
        orig_lunar = Lunar.fromSolar(Solar.fromYmdHms(year, month, day, 12, 0, 0)) if not is_lunar else Lunar.fromYmd(year, month, day)
        self.year_gan = orig_lunar.getYearGan()
        self.year_zhi = orig_lunar.getYearZhi()

        self.month_idx = abs(self.lunar.getMonth())
        self.day_idx = self.lunar.getDay()
        self.hour_idx = DI_ZHI.index(self.hour_zhi) + 1

        # 初始化十二地支宮位節點
        self.gong_位 = {zhi: {"宮干": "", "宮名": "", "原始主星": [], "顯示主星": []} for zhi in DI_ZHI}
        self.ming_gong_zhi = ""
        self.ju_name = ""
        self.ju_num = 0
        self.ziwei_zhi = ""

    def pad_chinese(self, text, width):
        cur_len = sum(wcwidth.wcwidth(c) for c in text)
        if cur_len >= width: return text
        return text + " " * (width - cur_len)

    # 🚀 外部排盤核心進入點
    def execute_astrology_flow(self):
        self.安十二宮()
        self.五虎遁與五行局()
        self.推紫微星位置()
        self.安十四主星()
        self.從資料庫撈取四化與亮度()
        self.渲染可視化命盤()
        self.調用資料庫進行十二宮深度解盤()

    def 安十二宮(self):
        start_pos = DI_ZHI.index("寅")
        ming_idx = (start_pos + (self.month_idx - 1) - (self.hour_idx - 1)) % 12
        self.ming_gong_zhi = DI_ZHI[ming_idx]
        for i, gong_name in enumerate(PALACES_BASE):
            current_zhi_idx = (ming_idx - i) % 12
            self.gong_位[DI_ZHI[current_zhi_idx]]["宮名"] = gong_name

    def 五虎遁與五行局(self):
        gan_idx = TIAN_GAN.index(self.year_gan)
        start_gan_idx = (gan_idx * 2 + 2) % 10 
        for i in range(12):
            zhi_idx = (DI_ZHI.index("寅") + i) % 12
            g_idx = (start_gan_idx + i) % 10
            self.gong_位[DI_ZHI[zhi_idx]]["宮干"] = TIAN_GAN[g_idx]
            
        ming_gan = self.gong_位[self.ming_gong_zhi]["宮干"]
        m_gan_val = (TIAN_GAN.index(ming_gan) // 2) + 1
        m_zhi_val = ((DI_ZHI.index(self.ming_gong_zhi) // 2) % 3) + 1
        sum_val = m_gan_val + m_zhi_val
        if sum_val > 5: sum_val -= 5
        ju_map = {1: ("金四局", 4), 2: ("水二局", 2), 3: ("火六局", 6), 4: ("土五局", 5), 5: ("木三局", 3)}
        self.ju_name, self.ju_num = ju_map[sum_val]

    def 推紫微星位置(self):
        X = self.day_idx
        N = self.ju_num
        商 = X // N; 餘 = X % N
        if 餘 == 0:
            zw_idx = (DI_ZHI.index("寅") + 商 - 1) % 12
        else:
            補數 = N - 餘
            zw_idx = (DI_ZHI.index("寅") + 商 + 1 + (補數 if 補數 % 2 == 0 else -補數)) % 12
        self.ziwei_zhi = DI_ZHI[zw_idx]

    def 安十四主星(self):
        zw_idx = DI_ZHI.index(self.ziwei_zhi) 
        zw_dict = {0: "紫微", -1: "天機", -3: "太陽", -4: "武曲", -5: "天同", -8: "廉貞"}
        for offset, name in zw_dict.items():
            self.gong_位[DI_ZHI[(zw_idx + offset) % 12]]["原始主星"].append(name)
            
        tf_idx = (4 - zw_idx) % 12 
        tf_dict = {0: "天府", 1: "太陰", 2: "貪狼", 3: "巨門", 4: "天相", 5: "天梁", 6: "七殺", 10: "破軍"}
        for offset, name in tf_dict.items():
            self.gong_位[DI_ZHI[(tf_idx + offset) % 12]]["原始主星"].append(name)

    def 從資料庫撈取四化與亮度(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (self.year_gan,))
        row = cursor.fetchone()
        hua_dict = {"(祿)": row[0], "(權)": row[1], "(科)": row[2], "(忌)": row[3]} if row else {}

        for zhi, info in self.gong_位.items():
            formatted = []
            for star in info["原始主星"]:
                cursor.execute("SELECT level FROM brightness WHERE star=? AND zhi=?", (star, zhi))
                br_row = cursor.fetchone()
                b_lbl = f".{br_row[0]}" if br_row and br_row[0] else ""
                
                h_lbl = ""
                for h_type, t_star in hua_dict.items():
                    if star == t_star:
                        h_lbl = h_type
                        break
                formatted.append(f"{star}{b_lbl}{h_lbl}")
            info["顯示主星"] = formatted

    def 渲染可視化命盤(self):
        cell_w = 34
        hr = "+" + ("-" * cell_w + "+") * 4
        g_name = "乾造 (男命)" if self.gender == "1" else "坤造 (女命)"
        print("\n" + "="*50 + " 紫微斗數大運命盤 " + "="*50)
        print(f"【基本資料】 性別: {g_name} | 生年干支: {self.year_gan}{self.year_zhi}年")
        print(f"【時間參數】 陽曆基準: {self.solar.getYear()}-{self.solar.getMonth()}-{self.solar.getDay()} | 農曆: {self.month_idx}月{self.day_idx}日 | 時辰: {self.hour_zhi}時")
        print(hr)
        for row in range(4):
            for sub in range(4):
                line = "|"
                for col in range(4):
                    z = GRID_LAYOUT[row][col]
                    if z == "中":
                        if row == 1 and sub == 1:
                            line += self.pad_chinese(f"  紫微斗數離線系統 v2.0", cell_w) + "|"
                        elif row == 1 and sub == 2:
                            line += self.pad_chinese(f"  命宮所在: {self.ming_gong_zhi}宮", cell_w) + "|"
                        elif row == 2 and sub == 1:
                            line += self.pad_chinese(f"  五行局: {self.ju_name}", cell_w) + "|"
                        elif row == 2 and sub == 2:
                            line += self.pad_chinese(f"  紫微星落點: {self.ziwei_zhi}宮", cell_w) + "|"
                        else:
                            line += " " * cell_w + "|"
                    else:
                        g = self.gong_位[z]
                        if sub == 0:
                            line += self.pad_chinese(f" {' '.join(g['顯示主星'][:2])}", cell_w) + "|"
                        elif sub == 1:
                            line += self.pad_chinese(f" {' '.join(g['顯示主星'][2:])}", cell_w) + "|"
                        elif sub == 2:
                            line += " " * cell_w + "|"
                        elif sub == 3:
                            line += self.pad_chinese(f" {g['宮干']}{z} {g['宮名']:>22}", cell_w) + "|"
                print(line)
            print(hr)

    def 調用資料庫進行十二宮深度解盤(self):
        print("\n" + "="*45 + " 🎯 本命十二宮離線斷語分析 (生年四化明確版) 🎯 " + "="*45)
        cursor = self.db.cursor()
        
        # 1. 事先撈取並建立生年四化的對應表 (例如：{"天同": "祿", "天機": "權"})
        cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (self.year_gan,))
        sihua_row = cursor.fetchone()
        
        natal_sihua_map = {}
        if sihua_row:
            natal_sihua_map[sihua_row[0]] = "祿"
            natal_sihua_map[sihua_row[1]] = "權"
            natal_sihua_map[sihua_row[2]] = "科"
            natal_sihua_map[sihua_row[3]] = "忌"
            
        # 2. 開始依序解盤本命十二宮
        for p_name in PALACES_BASE:
            target_zhi = [z for z, info in self.gong_位.items() if info["宮名"] == p_name][0]
            info = self.gong_位[target_zhi]
            
            print(f"\n【{p_name}】 (落於地支「{info['宮干']}{target_zhi}」方位)")
            
            if not info["原始主星"]:
                print("   ➔ [空宮無主星]：本宮無十四主星坐守。底層能量較易受對宮牽引，大運流年波動顯著。")
                continue
                
            for star in info["原始主星"]:
                # 撈取該宮位與該星曜的本命核心斷語
                cursor.execute("SELECT text FROM analysis WHERE palace=? AND star=?", (p_name, star))
                query_result = cursor.fetchone()
                
                if query_result:
                    print(f"   ➔ 坐守星曜【{star}】核心斷語: {query_result[0]}")
                else:
                    print(f"   ➔ 坐守星曜【{star}】核心斷語: 基礎星性發揮影響，吉凶依據格局引動。")
                    
                # 🚀 關鍵明確化：檢查這顆星曜在本命盤上有沒有「被生年四化引動」？
                if star in natal_sihua_map:
                    n_type = natal_sihua_map[star]
                    print(f"      ✨ [生年四化鎖定] 本命【{star}】終身化【{n_type}】！")
                    
                    # 依據化祿、權、科、忌輸出該宮位專屬的終身具體現象
                    if n_type == "祿":
                        print(f"         ➔ 【生年化祿具體現象】：代表一生緣分、財祿與順遂。在【{p_name}】事務上天生自帶福氣與資源，緣分深厚，多得貴人相助，心態相對樂觀豁達。")
                    elif n_type == "權":
                        print(f"         ➔ 【生年化權具體現象】：代表一生掌控、實權與成就。在【{p_name}】事務上具備強烈的掌控欲、開創力與主導權，專業技術過人，但也容易因主觀或強勢帶來壓力和勞碌。")
                    elif n_type == "科":
                        print(f"         ➔ 【生年化科具體現象】：代表一生名聲、條理與解厄。在【{p_name}】事務上擅長計畫與文書處理，容易獲得名聲或貴人暗中相助，遇到困難多能條理化解，風浪較小。")
                    elif n_type == "忌":
                        print(f"         ➔ 【生年化忌具體現象】：代表一生執念、欠債與考驗。在【{p_name}】事務上是您這輩子的「心思核心」與「不安全感來源」，容易投入過多心神，導致思慮打結或產生阻礙，宜學習釋懷與防守。")
                        
        print("\n" + "="*120)
    # 🎯 升級版函數：將 0~90 歲流年的四化引動完全明確化
    def calculate_lifetime_fortune(self, start_age=0, end_age=90):
        print("\n" + "═"*45 + f" 📊 啟動 {start_age} 至 {end_age} 歲一生流年全自動批導系統 (四化明確版) " + "═"*45)
        cursor = self.db.cursor()
        
        start_gan_idx = TIAN_GAN.index(self.year_gan)
        start_zhi_idx = DI_ZHI.index(self.year_zhi)
        
        for current_age in range(start_age, end_age + 1):
            liunian_gan = TIAN_GAN[(start_gan_idx + current_age) % 10]
            liunian_zhi = DI_ZHI[(start_zhi_idx + current_age) % 12]
            
            original_palace_name = self.gong_位[liunian_zhi]["宮名"]
            star_list = self.gong_位[liunian_zhi]["原始主星"]
            
            # 1. 撈取當年的流年四化星曜
            cursor.execute("SELECT lu, quan, ke, ji FROM sihua WHERE gan=?", (liunian_gan,))
            sihua_row = cursor.fetchone()
            
            # 定義四化對應表，方便後續比對
            # 格式為：{ "星曜名稱": "四化類型" }，例如：{"天同": "祿", "天機": "權"}
            current_year_sihua_map = {}
            if sihua_row:
                current_year_sihua_map[sihua_row[0]] = "祿"
                current_year_sihua_map[sihua_row[1]] = "權"
                current_year_sihua_map[sihua_row[2]] = "科"
                current_year_sihua_map[sihua_row[3]] = "忌"
            
            sihua_text = f"{sihua_row[0]}(祿) {sihua_row[1]}(權) {sihua_row[2]}(科) {sihua_row[3]}(忌)" if sihua_row else "無"
            
            print(f"\n【虛歲 {current_age:>2} 歲】 流年運勢 ➔ 干支：【{liunian_gan}{liunian_zhi}】年  | 流年命宮落於本命【{original_palace_name}】")
            print(f"   ➔ 當年環境四化背景：{sihua_text}")
            
            # 2. 進行解盤與四化明確化比對
            if not star_list:
                print("   ➔ [流年命宮為空宮]：當年運勢極易受對宮（遷移）星曜牽引，環境變動感強烈，宜靜觀其變。")
            else:
                for star in star_list:
                    # 撈取基礎星曜特質
                    cursor.execute("SELECT text FROM analysis WHERE palace=? AND star=?", ("命宮", star))
                    query_result = cursor.fetchone()
                    base_text = query_result[0] if query_result else "基礎星性發揮作用。"
                    print(f"   ➔ 坐守星曜【{star}】特質: {base_text}")
                    
                    # 🚀 關鍵明確化：檢查這顆星曜今年有沒有「被四化引動」？
                    if star in current_year_sihua_map:
                         s_type = current_year_sihua_map[star]
                         print(f"      🔥 [動態引動成功] 當年【{star}】化【{s_type}】！")
                         
                         # 依據化祿、權、科、忌輸出極其明確的流年核心事件
                         if s_type == "祿":
                             print(f"         ➔ 【流年化祿具體現象】：代表「得」與「順遂」。今年在該宮位事務上機會叢生，資金或資源進帳順暢，多得貴人相助，心態樂觀。")
                         elif s_type == "權":
                             print(f"         ➔ 【流年化權具體現象】：代表「權勢」與「掌控」。今年在該宮位事務上具備極強的開創力、實質掌控欲與話語權，專業技術升級，但也容易因為強勢而面臨壓力。")
                         elif s_type == "科":
                             print(f"         ➔ 【流年化科具體現象】：代表「名聲」與「條理」。今年利於合約簽署、證照考核、名譽提升，多有文書喜慶或暗中助力，問題多能迎刃而解。")
                         elif s_type == "忌":
                             print(f"         ➔ 【流年化忌具體現象】：代表「執念」與「阻礙」。今年在該宮位事務上容易出現思慮打結、行政糾紛、原則衝突或情緒內耗，切忌盲目擴張，宜防守維穩。")
            print("   " + "-" * 90)
        print("\n" + "═"*120)

# --- 4. 終端機前端互動執行區 ---
if __name__ == "__main__":
    db_file = 'ziwei.db'
    if not os.path.exists(db_file):
        print(f"警告：找不到 {db_file}，請先執行匯入配置腳本導入 JSON 種子資料！")
    else:
        db_conn = sqlite3.connect(db_file)
        
        print("\n" + "★"*20 + " 紫微斗數系統核心啟動 " + "★"*20)
        gender = input("1. 選擇性別 [1] 男 (乾造)  [2] 女 (坤造): ").strip()
        cal_type = input("2. 選擇曆法 [1] 國曆/陽曆     [2] 農曆/陰曆: ").strip()
        is_lunar = True if cal_type == "2" else False
        
        y = int(input("3. 出生西元年 (如 1990): ").strip())
        m = int(input("4. 出生月份 (如 1): ").strip())
        d = int(input("5. 出生日期 (如 1): ").strip())
        
        # 時辰地支 1-12 選單制
        print("\n6. 請選擇出生時辰地支：")
        print("   [1] 子時 (23-01)   [2] 丑時 (01-03)   [3] 寅時 (03-05)   [4] 卯時 (05-07)")
        print("   [5] 辰時 (07-09)   [6] 巳時 (09-11)   [7] 午時 (11-13)   [8] 未時 (13-15)")
        print("   [9] 申時 (15-17)  [10] 酉時 (17-19)  [11] 戌時 (19-21)  [12] 亥時 (21-23)")
        hour_choice = int(input("   請輸入數字 (1-12): ").strip())
        
        h_zhi = DI_ZHI[hour_choice - 1]
        
        sub_type = None
        if h_zhi == "子":
            print("\n【子時分段校準】")
            print("  [1] 晚子時 (23:00 - 24:00) ➔ 時間線跨日，推進日柱與農曆日期。")
            print("  [2] 早子時 (00:00 - 01:00) ➔ 當日凌晨，日期保持不變。")
            sub_type = input("  請選擇 [1] 或 [2]: ").strip()

        # 1. 實例化紫微排盤引擎
        engine = ZiWeiEngine(db_conn, y, m, d, h_zhi, gender, sub_type, is_lunar=is_lunar)
        
        # 2. 執行本命排盤與解盤
        engine.execute_astrology_flow()
        
        # 🚀 3. 外部調用：直接呼叫 0~90 歲一生流年全自動推算函數
        engine.calculate_lifetime_fortune(start_age=0, end_age=90)
        
        db_conn.close()