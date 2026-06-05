#!/usr/bin/env python3
"""
591 中古屋急賣監控 - 台南/高雄，1000萬以下
產出：~/Python/house_monitor/index.html（開啟即可看地圖+物件卡）
cron: 每週一 09:00
"""

import os, json, time, statistics, smtplib, requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── 設定 ───────────────────────────────────────────────
REGIONS = {"高雄市": "17", "台南市": "15"}
MAX_PRICE = "0_1000"
LABELS   = {"急售": "13", "低於市價": "10"}
RESULT_FILE  = os.path.expanduser("~/Python/house_monitor/seen_ids.json")
GEOCODE_FILE = os.path.expanduser("~/Python/house_monitor/geocache.json")
OUTPUT_HTML  = os.path.expanduser("~/Python/house_monitor/index.html")

EMAIL_TO       = os.environ.get("HOUSE_EMAIL_TO", "")
EMAIL_FROM     = os.environ.get("HOUSE_EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("HOUSE_EMAIL_PASSWORD", "")
SMTP_HOST      = os.environ.get("HOUSE_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.environ.get("HOUSE_SMTP_PORT", "587"))

# 行政區中心座標（快速顯示，不需 geocoding API）
SECTION_COORDS = {
    # 高雄市
    "三民區": [22.6498, 120.3124], "苓雅區": [22.6237, 120.3278],
    "前金區": [22.6304, 120.2989], "鹽埕區": [22.6272, 120.2836],
    "鼓山區": [22.6567, 120.2748], "旗津區": [22.5954, 120.2706],
    "前鎮區": [22.5837, 120.3191], "小港區": [22.5512, 120.3504],
    "左營區": [22.6889, 120.2953], "楠梓區": [22.7305, 120.3123],
    "仁武區": [22.7006, 120.3525], "大社區": [22.7377, 120.3549],
    "岡山區": [22.7964, 120.2956], "橋頭區": [22.7492, 120.2998],
    "燕巢區": [22.7840, 120.3614], "田寮區": [22.8810, 120.3795],
    "鳳山區": [22.6270, 120.3579], "大寮區": [22.5881, 120.3862],
    "林園區": [22.5038, 120.4027], "鳥松區": [22.6561, 120.3617],
    "大樹區": [22.6832, 120.4133], "旗山區": [22.8882, 120.4810],
    "美濃區": [22.8961, 120.5444], "六龜區": [23.0036, 120.6281],
    "甲仙區": [23.0809, 120.5947], "杉林區": [22.9866, 120.5272],
    "內門區": [22.8949, 120.4671], "茂林區": [22.9010, 120.6690],
    "桃源區": [23.1694, 120.7145], "那瑪夏區": [23.2344, 120.7168],
    "阿蓮區": [22.8697, 120.3087], "路竹區": [22.8537, 120.2622],
    "湖內區": [22.8975, 120.2232], "茄萣區": [22.9098, 120.1944],
    "永安區": [22.8390, 120.2246], "彌陀區": [22.8021, 120.2368],
    "梓官區": [22.7560, 120.2499], "東沙群島": [20.7044, 116.7227],
    # 台南市
    "中西區": [22.9972, 120.1965], "東區": [22.9908, 120.2261],
    "南區": [22.9695, 120.1978], "北區": [23.0131, 120.2092],
    "安平區": [22.9924, 120.1614], "安南區": [23.0489, 120.1749],
    "永康區": [23.0374, 120.2476], "歸仁區": [22.9636, 120.2777],
    "新化區": [23.0383, 120.3113], "左鎮區": [23.0249, 120.3596],
    "玉井區": [23.1272, 120.4569], "楠西區": [23.1655, 120.4867],
    "南化區": [23.2168, 120.4622], "仁德區": [22.9504, 120.2218],
    "關廟區": [22.9301, 120.3157], "龍崎區": [22.9252, 120.3637],
    "官田區": [23.1249, 120.2693], "麻豆區": [23.1810, 120.2535],
    "佳里區": [23.1695, 120.1773], "西港區": [23.1373, 120.1739],
    "七股區": [23.1451, 120.0994], "將軍區": [23.1904, 120.1257],
    "學甲區": [23.2213, 120.1715], "北門區": [23.2722, 120.1200],
    "新營區": [23.3088, 120.3161], "後壁區": [23.3763, 120.3568],
    "白河區": [23.3541, 120.4196], "東山區": [23.2630, 120.4238],
    "六甲區": [23.2256, 120.3451], "下營區": [23.2011, 120.2939],
    "柳營區": [23.2511, 120.3081], "鹽水區": [23.3180, 120.2632],
    "善化區": [23.1425, 120.2978], "大內區": [23.1016, 120.3597],
    "山上區": [23.0802, 120.3318], "新市區": [23.0795, 120.2836],
    "安定區": [23.0712, 120.2301], "仁德區": [22.9504, 120.2218],
}
# ──────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def get_ts(session):
    r = session.get("https://api.591.com.tw/api/tools/getTimestamp",
                    params={"from": "https://sale.591.com.tw/"}, headers=HEADERS, timeout=10)
    return str(r.json()["data"]["_timestamp"])


def fetch_section_market(session, regionid, section_id, ts):
    """抓該行政區全部物件，計算單坪均價中位數（排除離群值）"""
    r = session.get("https://bff-house.591.com.tw/v1/web/sale/list", params={
        "timestamp": ts, "type": "2", "category": "1",
        "regionid": regionid, "section_id": section_id,
        "firstRow": "0", "totalRows": "100",
    }, headers=HEADERS, timeout=15)
    items = r.json().get("data", {}).get("house_list", [])
    prices = [float(h["unitprice"]) for h in items if h.get("unitprice") and float(h["unitprice"]) > 5]
    if len(prices) < 3:
        return None
    # 排除離群值：只保留 Q1-1.5×IQR ~ Q3+1.5×IQR
    prices.sort()
    q1 = prices[len(prices)//4]
    q3 = prices[3*len(prices)//4]
    iqr = q3 - q1
    filtered = [p for p in prices if q1 - 1.5*iqr <= p <= q3 + 1.5*iqr]
    return round(statistics.median(filtered), 2) if filtered else None


def fetch_target_listings(session, regionid, label, ts):
    r = session.get("https://bff-house.591.com.tw/v1/web/sale/list", params={
        "timestamp": ts, "type": "2", "category": "1",
        "regionid": regionid, "price": MAX_PRICE, "label": label,
        "firstRow": "0", "totalRows": "100",
    }, headers=HEADERS, timeout=15)
    return r.json().get("data", {}).get("house_list", [])


def get_coords(section_name, region_name):
    """回傳行政區中心座標"""
    if section_name in SECTION_COORDS:
        # 加輕微隨機偏移避免所有同區物件重疊
        import random
        base = SECTION_COORDS[section_name]
        return [base[0] + random.uniform(-0.005, 0.005),
                base[1] + random.uniform(-0.005, 0.005)]
    # 城市中心 fallback
    defaults = {"高雄市": [22.6273, 120.3014], "台南市": [23.0000, 120.2133]}
    return defaults.get(region_name, [22.6273, 120.3014])


def load_seen_ids():
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    with open(RESULT_FILE, "w") as f:
        json.dump(list(ids), f)


def build_html(all_items, run_time):
    markers_js = ""
    cards_html = ""

    for item in all_items:
        lat, lng = item["coords"]
        discount_pct = item.get("discount_pct", 0)
        is_townhouse = item.get("shape_name") == "透天厝"
        color = "#e74c3c" if discount_pct >= 15 else "#e67e22" if discount_pct >= 8 else "#f1c40f"
        # 透天厝用藍紫色邊框特別標示
        border_color = "#8e44ad" if is_townhouse else color

        op_tag = item.get("operation_tag_title", "")
        townhouse_label = "🏘️ 透天厝 " if is_townhouse else ""

        marker_popup = (
            f"<b>{townhouse_label}{item['section']} {item['address']}</b><br>"
            f"<span style='color:{color};font-weight:bold'>{item['price']} 萬</span> "
            f"({item['unitprice']} 萬/坪)<br>"
            f"{item['room']} · {item['area']} 坪 · {item['houseage']}<br>"
        )
        if op_tag:
            marker_popup += f"<span style='background:#fff3cd;padding:2px 4px;border-radius:3px;font-size:11px'>{op_tag}</span><br>"
        if discount_pct > 0:
            marker_popup += f"<b style='color:{color}'>低於市場行情 {discount_pct:.0f}%</b><br>"
        marker_popup += f"<a href='{item['url']}' target='_blank'>→ 591 查看</a>"

        radius = 8 + min(discount_pct/3, 8)
        if is_townhouse:
            # 透天厝：星形標記（用較大圓形+粗紫色邊框）
            markers_js += f"""
        L.circleMarker([{lat}, {lng}], {{
            radius: {radius + 4:.0f},
            color: '#8e44ad', fillColor: '{color}', fillOpacity: 0.85, weight: 4,
            dashArray: '6,3'
        }}).addTo(map).bindPopup(`{marker_popup}`);"""
        else:
            markers_js += f"""
        L.circleMarker([{lat}, {lng}], {{
            radius: {radius:.0f},
            color: '{color}', fillColor: '{color}', fillOpacity: 0.75, weight: 2
        }}).addTo(map).bindPopup(`{marker_popup}`);"""

        houseage_yr = item.get("houseage_num", 0)
        badge = ""
        abnormal_threshold = 55 if houseage_yr >= 20 else 35
        if discount_pct >= abnormal_threshold:
            badge = f"<span class='badge' style='background:#7f8c8d'>⚠ 請確認</span>"
        elif discount_pct >= 8:
            badge = f"<span class='badge'>低 {discount_pct:.0f}%</span>"
        if item.get("is_down_price"):
            badge += f"<span class='badge-red'>↓降{float(item.get('down_price_percent',0)):.0f}%</span>"
        townhouse_badge = "<span class='badge-townhouse'>🏘️ 透天厝</span>" if is_townhouse else ""

        card_class = "card card-townhouse" if is_townhouse else "card"
        cards_html += f"""
        <div class="{card_class}" onclick="window.open('{item['url']}','_blank')">
          <div class="card-top">
            <span class="tag {'tag-low' if item['label_name']=='低於市價' else ''}">{item['label_name']}</span>
            <span class="region">{item['region']} {item['section']}</span>
            {townhouse_badge}{badge}
          </div>
          <div class="card-addr">{item['address']}</div>
          <div class="card-title">{item['title'][:40]}</div>
          <div class="card-price">
            <span class="price">{item['price']} 萬</span>
            <span class="unit">{item['unitprice']} 萬/坪</span>
            {"<span class='market'>市場均價 "+str(item['market_median'])+" 萬/坪</span>" if item.get('market_median') else ""}
          </div>
          <div class="card-meta">
            {item['room']} · {item['area']} 坪 · {item['houseage']} · {item['floor']}
          </div>
          {"<div class='card-optag'>📊 "+op_tag+"</div>" if op_tag else ""}
        </div>"""

    total = len(all_items)

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台南/高雄 急售房屋監控 · {run_time}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f0f2f5; color: #333; }}

  header {{ background: #1a1a2e; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 20px; font-weight: 600; }}
  header .sub {{ font-size: 13px; color: #aaa; margin-top: 2px; }}
  .stats {{ margin-left: auto; display: flex; gap: 20px; text-align: center; }}
  .stat-val {{ font-size: 22px; font-weight: 700; color: #e74c3c; }}
  .stat-lbl {{ font-size: 11px; color: #999; }}

  .legend {{ background: #1a1a2e; color: #ccc; padding: 8px 24px; font-size: 12px; display: flex; gap: 20px; flex-wrap: wrap; }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }}
  .dot-townhouse {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    border: 3px dashed #8e44ad; margin-right: 4px; }}

  #map {{ height: 420px; width: 100%; }}

  .panel {{ padding: 20px 24px; }}
  .panel-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #1a1a2e; }}

  .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
  .filter-btn {{ padding: 6px 14px; border: 1px solid #ddd; border-radius: 20px; background: white;
    cursor: pointer; font-size: 13px; transition: all .2s; }}
  .filter-btn:hover, .filter-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; }}

  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}

  .card {{ background: white; border-radius: 10px; padding: 16px; cursor: pointer;
    transition: box-shadow .2s, transform .2s; border: 1px solid #eee; }}
  .card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.12); transform: translateY(-2px); }}

  .card-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .tag {{ background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
  .tag.low {{ background: #e67e22; }}
  .region {{ font-size: 12px; color: #888; }}
  .badge {{ background: #c0392b; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-left: auto; }}
  .badge-red {{ background: #e74c3c; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px; margin-left: 4px; }}
  .badge-townhouse {{ background: #8e44ad; color: white; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
  .card-townhouse {{ border: 2px solid #8e44ad; background: linear-gradient(135deg, #fff 0%, #fdf4ff 100%); }}

  .card-addr {{ font-size: 15px; font-weight: 600; color: #222; }}
  .card-title {{ font-size: 12px; color: #777; margin: 4px 0 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  .card-price {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }}
  .price {{ font-size: 22px; font-weight: 700; color: #e74c3c; }}
  .unit {{ font-size: 13px; color: #666; }}
  .market {{ font-size: 12px; color: #27ae60; background: #eafaf1; padding: 2px 6px; border-radius: 4px; }}

  .card-meta {{ font-size: 12px; color: #888; }}
  .card-optag {{ font-size: 12px; color: #856404; background: #fff3cd; padding: 4px 8px;
    border-radius: 4px; margin-top: 8px; }}

  .updated {{ font-size: 12px; color: #aaa; margin-top: 16px; text-align: right; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>🏠 台南 / 高雄 急售房屋監控</h1>
    <div class="sub">1000萬以下 · 急售 + 低於市價 · 與行政區行情比較</div>
  </div>
  <div class="stats">
    <div><div class="stat-val">{total}</div><div class="stat-lbl">本次物件</div></div>
  </div>
</header>

<div class="legend">
  <span><span class="dot" style="background:#e74c3c"></span>低於市場 15%+</span>
  <span><span class="dot" style="background:#e67e22"></span>低於市場 8-15%</span>
  <span><span class="dot" style="background:#f1c40f"></span>急售標記</span>
  <span><span class="dot-townhouse"></span>透天厝</span>
  <span>點擊標記查看詳情</span>
</div>

<div id="map"></div>

<div class="panel">
  <div class="panel-title">物件列表</div>
  <div class="filters">
    <button class="filter-btn active" onclick="filterCards('all', this)">全部 ({total})</button>
    <button class="filter-btn" onclick="filterCards('急售', this)">急售</button>
    <button class="filter-btn" onclick="filterCards('低於市價', this)">低於市價</button>
    <button class="filter-btn" onclick="filterCards('高雄市', this)">高雄市</button>
    <button class="filter-btn" onclick="filterCards('台南市', this)">台南市</button>
    <button class="filter-btn" style="border-color:#8e44ad;color:#8e44ad" onclick="filterCards('透天厝', this)">🏘️ 透天厝</button>
  </div>
  <div class="cards" id="cards">
    {cards_html}
  </div>
  <div class="updated">更新時間：{run_time} · 資料來源：591 售屋網</div>
</div>

<script>
var map = L.map('map').setView([22.85, 120.27], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© OpenStreetMap contributors', maxZoom: 18
}}).addTo(map);

{markers_js}

function filterCards(filter, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {{
    if (filter === 'all' || card.textContent.includes(filter)) {{
      card.style.display = '';
    }} else {{
      card.style.display = 'none';
    }}
  }});
}}
</script>

</body>
</html>"""


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 開始搜尋...")
    seen_ids  = load_seen_ids()
    all_items = []

    session = requests.Session()
    ts = get_ts(session)

    # Cache section median prices
    section_medians = {}

    for region_name, regionid in REGIONS.items():
        for label_name, label in LABELS.items():
            print(f"  搜尋：{region_name} {label_name}")
            try:
                listings = fetch_target_listings(session, regionid, label, ts)
                print(f"    找到 {len(listings)} 筆")
            except Exception as e:
                print(f"    ❌ 失敗：{e}")
                continue

            new_count = 0
            for h in listings:
                house_id = str(h.get("houseid", ""))
                section_id = str(h.get("section_id", ""))
                section_name = h.get("section_name", "")
                unitprice = float(h.get("unitprice") or 0)

                # 取行政區中位數（快取）
                cache_key = f"{regionid}_{section_id}"
                if cache_key not in section_medians and section_id:
                    try:
                        med = fetch_section_market(session, regionid, section_id, ts)
                        section_medians[cache_key] = med
                        time.sleep(0.3)
                    except:
                        section_medians[cache_key] = None

                market_median = section_medians.get(cache_key)
                discount_pct = 0
                if market_median and unitprice > 0:
                    discount_pct = max(0, (market_median - unitprice) / market_median * 100)

                op_tag_obj = h.get("operation_tag") or {}
                op_tag_title = ""
                if isinstance(op_tag_obj, dict):
                    title = op_tag_obj.get("title", "")
                    sub   = op_tag_obj.get("sub_title", "")
                    if title:
                        op_tag_title = f"{title}｜{sub}" if sub else title

                item = {
                    "id": house_id,
                    "region": region_name,
                    "section": section_name,
                    "address": h.get("address", ""),
                    "title": h.get("title", ""),
                    "price": h.get("price", "—"),
                    "unitprice": unitprice or "—",
                    "area": h.get("area", "—"),
                    "room": h.get("room", "—"),
                    "floor": h.get("floor", "—"),
                    "houseage": h.get("showhouseage", "—"),
                    "houseage_num": int(h.get("houseage") or 0),
                    "photo": h.get("photo_url", ""),
                    "label_name": label_name,
                    "shape_name": h.get("shape_name", ""),
                    "is_down_price": h.get("is_down_price", 0),
                    "down_price_percent": h.get("down_price_percent", 0),
                    "original_price": h.get("original_price"),
                    "diff_price": h.get("diff_price"),
                    "market_median": market_median,
                    "discount_pct": round(discount_pct, 1),
                    "operation_tag_title": op_tag_title,
                    "coords": get_coords(section_name, region_name),
                    "url": f"https://sale.591.com.tw/home/house/detail/2/{house_id}.html",
                    "is_new": house_id not in seen_ids,
                }
                all_items.append(item)
                if house_id not in seen_ids:
                    seen_ids.add(house_id)
                    new_count += 1

            print(f"    ✅ {new_count} 筆新物件 / 共 {len(listings)} 筆")
            time.sleep(1)

    # 依低於市場比例排序
    all_items.sort(key=lambda x: x["discount_pct"], reverse=True)

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(all_items, run_time)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 網頁已產出：{OUTPUT_HTML}")
    print(f"   共 {len(all_items)} 筆物件")

    # 寄 email（如果有設定）
    new_items = [i for i in all_items if i["is_new"]]
    if new_items and EMAIL_TO:
        _send_email(new_items, run_time)

    save_seen_ids(seen_ids)
    print("完成。")


def _send_email(items, run_time):
    rows = "".join(
        f"<tr><td>{i['region']} {i['section']}</td>"
        f"<td>{i['address']}</td>"
        f"<td><b style='color:#c0392b'>{i['price']} 萬</b></td>"
        f"<td>{i['unitprice']} 萬/坪</td>"
        f"<td>{'低 '+str(i['discount_pct'])+'%' if i['discount_pct']>0 else '—'}</td>"
        f"<td><a href='{i['url']}'>查看</a></td></tr>"
        for i in items
    )
    html = f"""<html><body style='font-family:sans-serif'>
    <h2>🏠 急售/低於市價通知 {run_time}</h2>
    <table style='border-collapse:collapse;font-size:13px'>
    <tr style='background:#f0f0f0'><th>區域</th><th>地址</th><th>總價</th>
    <th>單坪</th><th>折扣</th><th>連結</th></tr>{rows}</table>
    </body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {len(items)} 筆急售物件 {run_time}"
    msg["From"] = EMAIL_FROM
    msg["To"]   = EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.starttls()
        srv.login(EMAIL_FROM, EMAIL_PASSWORD)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("✅ Email 已寄出")


if __name__ == "__main__":
    main()
