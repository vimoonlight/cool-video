import os
import datetime
import re
from googleapiclient.discovery import build

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 品牌频道 ID 列表
BRAND_CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', 'UCL8RlvQSa4YEj74wLBSku-A', 'UCblfuW_4rakIfk66AQ40hIg',
    'UCtI0Hodo5o5dUb67FeUjDeA', 'UC0UBX6y5bL1sU7Oq6wMv0aA', 'UCx5XG1Lnc65_3rLqQWa_49w',
    'UCOHMGt67_u8FjT_L4t8Zcww', 'UC5WjFrtBdufl6CZojX3D8dQ', 'UCvQECJukTDEUU9Nd6TQq_xg', 'UCsTcErHg8oDvUnTzoqsYeNw'
]

# 个人博主 ID 列表
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', 'UCX6OQ3DkcsbYNE6H8uQQuVA', 'UCtinbF-Q-fVthA0qFrcFb9Q',
    'UCBJycsmduvYEL83R_U4JriQ', 'UCsooa4yRKGN_zEE8iknghZA', 'UCAL3JXZSzSm8AlZyD3nQdBA',
    'UC295-Dw_tDNtZXFeAPAW6Aw', 'UCpw269dbC0hDrwNmyq4U66Q'
]

# 全球扫描地区
TARGET_REGIONS = ['US', 'GB', 'DE', 'FR', 'JP', 'KR', 'TW', 'IN', 'BR', 'AU']

def get_youtube_service():
    if not API_KEY: return None
    try:
        return build('youtube', 'v3', developerKey=API_KEY)
    except Exception as e:
        print(f"API Service Error: {e}")
        return None

def get_seconds(duration_str):
    if not duration_str: return 0
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?', duration_str)
    if not match: return 0
    time_data = match.groupdict()
    return int(time_data['hours'] or 0) * 3600 + int(time_data['minutes'] or 0) * 60 + int(time_data['seconds'] or 0)

def get_beijing_time():
    # 强制获取北京时间 (UTC+8)
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)

def fetch_filtered_global_pool(youtube):
    print("Scanning Global Trends...")
    raw_videos = []
    seen_ids = set()
    for region in TARGET_REGIONS:
        try:
            res = youtube.videos().list(chart='mostPopular', regionCode=region, part='snippet,statistics,contentDetails', maxResults=25).execute()
            for item in res['items']:
                if item['id'] not in seen_ids:
                    raw_videos.append(item)
                    seen_ids.add(item['id'])
        except Exception as e: print(f"Skip {region}: {e}")

    # 分桶过滤逻辑
    b_music, b_ent, b_content = [], [], []
    for v in raw_videos:
        duration = v['contentDetails'].get('duration', '')
        if get_seconds(duration) < 60: continue # 过滤 Shorts
        
        cat_id = v['snippet'].get('categoryId', '0')
        if cat_id in ['1', '20', '25']: continue # 过滤 动画/游戏/新闻
        
        v['like_count'] = int(v['statistics'].get('likeCount', 0))
        if cat_id == '10': b_music.append(v)
        elif cat_id == '24': b_ent.append(v)
        else: b_content.append(v)

    # 配额限制: MV 7条, 娱乐 5条, 优质内容 40条
    b_music.sort(key=lambda x: x['like_count'], reverse=True)
    b_ent.sort(key=lambda x: x['like_count'], reverse=True)
    b_content.sort(key=lambda x: x['like_count'], reverse=True)
    
    return b_music[:7] + b_ent[:5] + b_content[:40]

def fetch_optimized_list(youtube, channel_ids):
    final_videos = []
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        try:
            res = youtube.channels().list(id=','.join(batch), part='contentDetails').execute()
            ids_to_fetch = []
            for item in res['items']:
                up_id = item['contentDetails']['relatedPlaylists']['uploads']
                pl_res = youtube.playlistItems().list(playlistId=up_id, part='contentDetails', maxResults=3).execute()
                ids_to_fetch.extend([v['contentDetails']['videoId'] for v in pl_res['items']])
            
            # 补全详细统计数据
            for j in range(0, len(ids_to_fetch), 50):
                v_res = youtube.videos().list(id=','.join(ids_to_fetch[j:j+50]), part='snippet,statistics').execute()
                final_videos.extend(v_res['items'])
        except Exception as e: print(f"List Error: {e}")
    return final_videos

def generate_html(most_liked, most_commented, brands, creators):
    today_str = get_beijing_time().strftime("%Y-%m-%d")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Global Curated</title>
        <style>
            :root {{ --bg: #050505; --card: #141414; --text: #e5e5e5; --accent: #fff; }}
            body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif; margin: 0; }}
            header {{ padding: 80px 20px 50px; text-align: center; background: radial-gradient(circle at top, #1a1a1a 0%, #050505 80%); }}
            h1 {{ margin: 0; font-size: 3rem; letter-spacing: -2px; font-weight: 800; background: linear-gradient(to right, #fff, #999); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .date {{ color: #666; font-size: 0.8rem; margin-top: 15px; letter-spacing: 3px; text-transform: uppercase; }}
            .nav {{ display: flex; justify-content: center; gap: 30px; padding: 20px; border-bottom: 1px solid #222; position: sticky; top: 0; background: rgba(5,5,5,0.95); backdrop-filter: blur(10px); z-index: 99; overflow-x: auto; }}
            .btn {{ background: none; border: none; color: #666; cursor: pointer; font-size: 0.9rem; padding: 10px 15px; font-weight: 600; white-space: nowrap; transition: 0.3s; }}
            .btn:hover, .btn.active {{ color: #fff; }}
            .btn.active {{ border-bottom: 2px solid #fff; }}
            .container {{ max-width: 1600px; margin: 0 auto; padding: 40px 20px; min-height: 80vh; }}
            .tab {{ display: none; }}
            .tab.active {{ display: block; animation: fade 0.6s; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(10px);}} to {{opacity:1; transform:translateY(0);}} }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 40px 30px; }}
            .card {{ background: transparent; transition: 0.3s; }}
            .card:hover .vid {{ transform: scale(1.03); box-shadow: 0 20px 40px rgba(0,0,0,0.6); }}
            .vid {{ position: relative; padding-bottom: 56.25%; background: #111; border-radius: 8px; overflow: hidden; }}
            .vid iframe {{ position: absolute; top:0; left:0; width:100%; height:100%; border:0; }}
            .info {{ padding-top: 15px; }}
            .title {{ font-weight: 600; font-size: 1rem; margin-bottom: 8px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
            .meta {{ color: #888; font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center; }}
            .hl {{ color: #fff; font-weight: bold; background: #222; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }}
        </style>
    </head>
    <body>
        <header>
            <h1>VISION</h1>
            <div class="date">{today_str} • WORLD EDITION</div>
        </header>
        <nav class="nav">
            <button class="btn active" onclick="show('likes', this)">Curated Top Liked</button>
            <button class="btn" onclick="show('comments', this)">Curated Discussed</button>
            <button class="btn" onclick="show('brands', this)">Brand Zone</button>
            <button class="btn" onclick="show('creators', this)">Creator Zone</button>
        </nav>
        <div class="container">
            <div id="likes" class="tab active"><div class="grid">{render(most_liked, 'likes')}</div></div>
            <div id="comments" class="tab"><div class="grid">{render(most_commented, 'comments')}</div></div>
            <div id="brands" class="tab"><div class="grid">{render(brands, 'brand')}</div></div>
            <div id="creators" class="tab"><div class="grid">{render(creators, 'creator')}</div></div>
        </div>
        <script>
            function show(id, btn) {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                document.getElementById(id).classList.add('active');
                btn.classList.add('active');
            }}
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def render(videos, mode):
    if not videos: return "<p style='color:#666; text-align:center; padding:50px;'>No new content found. Please check back later.</p>"
    html = ""
    for v in videos:
        s = v.get('statistics', {})
        def fmt(n): 
            n = int(n)
            return f"{round(n/1e6,1)}M" if n>1e6 else (f"{round(n/1e3,1)}K" if n>1e3 else str(n))
        badge = f"♥ {fmt(s.get('likeCount', 0))}" if mode == 'likes' else (f"💬 {fmt(s.get('commentCount', 0))}" if mode == 'comments' else "PLAY")
        html += f"""
        <div class="card">
            <div class="vid"><iframe src="https://www.youtube.com/embed/{v['id']}" loading="lazy" allowfullscreen></iframe></div>
            <div class="info">
                <div class="title">{v['snippet']['title']}</div>
                <div class="meta"><span>{v['snippet']['channelTitle']}</span><span class="hl">{badge}</span></div>
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    pool = fetch_filtered_global_pool(youtube)
    generate_html(
        sorted(pool, key=lambda x: int(x['statistics'].get('likeCount', 0)), reverse=True),
        sorted(pool, key=lambda x: int(x['statistics'].get('commentCount', 0)), reverse=True),
        fetch_optimized_list(youtube, BRAND_CHANNELS),
        fetch_optimized_list(youtube, CREATOR_CHANNELS)
    )

if __name__ == "__main__":
    main()
