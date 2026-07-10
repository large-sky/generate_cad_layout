def 調用資料庫進行十二宮深度解盤(self):
    self.report_logs.append("\n==============================================")
    self.report_logs.append("🔮 專業版 168組核心星情核心宮位深度解盤剖析")
    self.report_logs.append("==============================================")
    
    for zhi, info in self.gong_位.items():
        gong_name = info["宮名"]
        stars = info["主星"] # 這是一個包含此宮位主星的 list，例如 ["太陽", "紫微"]
        
        # 1. 讀取並標註主星的廟旺利陷
        star_status_list = []
        for star in stars:
            if star in BRIGHTNESS_MAP:
                brightness_val = BRIGHTNESS_MAP[star][zhi]
                label = BRIGHTNESS_LABELS[brightness_val]
                star_status_list.append(f"{star}({label})")
                
                # 2. 觸發單星廟旺斷語
                lookup_key = f"{star}_{brightness_val}"
                if gong_name in STAR_INTERPRETATIONS and lookup_key in STAR_INTERPRETATIONS[gong_name]:
                    self.report_logs.append(f"【{gong_name}斷語】{STAR_INTERPRETATIONS[gong_name][lookup_key]}")
        
        # 3. 觸發雙星或多星群聚特殊斷語（例如太陽/紫微/廉貞/破軍同宮）
        if len(stars) > 1 and gong_name in STAR_INTERPRETATIONS:
            # 將主星排序後組合成 key
            combo_key = "_".join(sorted(stars))
            if combo_key in STAR_INTERPRETATIONS[gong_name]:
                self.report_logs.append(f"【{gong_name}特殊格】{STAR_INTERPRETATIONS[gong_name][combo_key]}")