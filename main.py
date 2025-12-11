import os
import datetime
from googleapiclient.discovery import build

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 【名单 A】品牌/商业广告 (Brand Zone)
BRAND_CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', # Apple
    'UCL8RlvQSa4YEj74wLBSku-A', # Nike
    'UCblfuW_4rakIfk66AQ40hIg', # Red Bull
    'UCtI0Hodo5o5dUb67FeUjDeA', # SpaceX
    'UC0UBX6y5bL1sU7Oq6wMv0aA', # Samsung
]

# 【名单 B】个人博主 (Creator Zone)
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', # Peter McKinnon
    'UCX6OQ3DkcsbYNE6H8uQQuVA', # MrBeast
    'UCtinbF-Q-fVthA0qFrcFb9Q', # Casey Neistat
    'UCBJycsmduvYEL83R_U4JriQ', # MKBHD
    'UCsooa4yRKGN_zEE8iknghZA', # TED-Ed
]

def get_youtube_service():
    if not API_KEY:
        print("Error: API Key is missing!")
        return None
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 核心逻辑 ---

def fetch_list_latest(youtube, channels):
    """抓取指定名单的最新视频"""
    videos = []
    print(f"正在抓取名单视频，共 {len(channels)} 个频道...")
    for channel_id in channels:
        try:
            res = youtube.search().list(
                channelId=channel_id, part='snippet,id', order='date', maxResults=1, type='video'
            ).execute()
            
            if res['items']:
                item = res['items'][0]
                vid = item['id']['videoId']
                # 补全数据
                stats_res = youtube.videos().list(id=vid, part='statistics').execute()
                if stats_res['items']:
                    item['statistics'] = stats_res['items'][0]['statistics']
                    videos.append(item)
        except Exception as e:
            print(f"频道 {channel_id} 错误: {e}")
    return videos

def fetch_global_pool(youtube):
    """抓取全球热门池 (50个用于筛选)"""
    print("正在扫描全球数据池...")
    videos = []
    # 昨天的时间
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat("T") + "Z"
    
    try:
        # 搜索
        search_response = youtube.search().list(
            part='id', order='viewCount', type='video', publishedAfter=yesterday, maxResults=50
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        if video_ids:
            # 详情
            stats_response = youtube.videos().list(id=','.join(video_ids), part='snippet,statistics').execute()
            videos = stats_response['items']
            
    except Exception as e:
        print(f"全球池错误: {e}")
    return videos

# --- 网页生成 (核心 UI 设计) ---
def generate_html(most_liked, most_commented, brands, creators):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Curated Video Trends</title>
        <style>
            :root {{
                --bg-color: #0a0a0a;
                --card-bg: #161616;
                --text-primary: #ffffff;
                --text-secondary: #888888;
                --accent: #ffffff;
            }}
            body {{
                background-color: var(--bg-color);
                color: var(--text-primary);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                margin: 0; padding: 0;
            }}
            header {{
                padding: 40px 20px; text-align: center;
                background: linear-gradient(to bottom, #000 0%, #0a0a0a 100%);
            }}
            h1 {{ font-weight: 200; letter-spacing: 4px; text-transform: uppercase; margin: 0; font-size: 1.8rem; }}
            .date {{ font-size: 0.8rem; color: var(--text-secondary); margin-top: 10px; letter-spacing: 1px; }}
            .nav-container {{
                display: flex; justify-content: center; gap: 20px; margin-bottom: 30px;
                padding: 10px 20px; border-bottom: 1px solid #222; position: sticky; top: 0;
                background: rgba(10, 10, 10, 0.95); backdrop-filter: blur(10px); z-index: 100;
                flex-wrap: wrap;
            }}
            .tab-btn {{
                background: none; border: none; color: var(--text-secondary);
                font-size: 0.9rem; padding: 10px 15px; cursor: pointer;
                transition: all 0.3s ease; font-weight: 500; position: relative;
            }}
            .tab-btn:hover {{ color: var(--text-primary); }}
            .tab-btn.active {{ color: var(--text-primary); }}
            .tab-btn.active::after {{
                content: ''; position: absolute; bottom: -11px; left: 0;
                width: 100%; height: 2px; background-color: var(--accent);
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; min-height: 80vh; }}
            .tab-content {{ display: none; animation: fadeIn 0.5s ease; }}
            .tab-content.active {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 30px; }}
            .card {{
                background: var(--card-bg); border-radius: 12px; overflow: hidden;
                transition: transform 0.3s ease; border: 1px solid #222;
            }}
            .card:hover {{ transform: translateY(-5px); border-color: #333; }}
            .video-wrapper {{ position: relative; padding-bottom: 56.25%; height: 0; background: #000; }}
            .video-wrapper iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; }}
            .info {{ padding: 20px; }}
            .title {{
                font-size: 0.95rem; font-weight: 600; line-height: 1.4; margin-bottom: 12px;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 2.8em;
            }}
            .meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: var(--text-secondary); }}
            .stat-badge {{ background: #333; padding: 4px 8px; border-radius: 4px; color: #fff; font-size: 0.75rem; font-weight: bold; }}
        </style>
    </head>
    <body>
        <header>
            <h1>VISION</h1>
            <div class="date">GLOBAL TRENDS • {today}</div>
        </header>

        <nav class="nav-container">
            <button class="tab-btn active" onclick="openTab(event, 'likes')">Most Liked (最多赞)</button>
            <button class="tab-btn" onclick="openTab(event, 'comments')">Most Discussed (热议中)</button>
            <button class="tab-btn" onclick="openTab(event, 'brands')">Brand Zone (品牌区)</button>
            <button class="tab-btn" onclick="openTab(event, 'creators')">Creator Zone (个人区)</button>
        </nav>

        <div class="container">
            <div id="likes" class="tab-content active"><div class="grid">{render_cards(most_liked, 'likes')}</div></div>
            <div id="comments" class="tab-content"><div class="grid">{render_cards(most_commented, 'comments')}</div></div>
            <div id="brands" class="tab-content"><div class="grid">{render_cards(brands, 'brand')}</div></div>
            <div id="creators" class="tab-content"><div class="grid">{render_cards(creators, 'creator')}</div></div>
        </div>

        <script>
            function openTab(evt, tabName) {{
                var i, tabcontent, tablinks;
                tabcontent = document.getElementsByClassName("tab-content");
                for (i = 0; i < tabcontent.length; i++) {{
                    tabcontent[i].style.display = "none";
                }}
                tablinks = document.getElementsByClassName("tab-btn");
                for (i = 0; i < tablinks.length; i++) {{
                    tablinks[i].className = tablinks[i].className.replace(" active", "");
                }}
                document.getElementById(tabName).style.display = "block";
                evt.currentTarget.className += " active";
            }}
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def render_cards(videos, mode):
    html = ""
    if not videos:
        return "<p style='padding:20px; color:#666'>No data available right now.</p>"
        
    for v in videos:
        stats = v.get('statistics', {})
        like_cnt = int(stats.get('likeCount', 0))
        comm_cnt = int(stats.get('commentCount', 0))
        
        def fmt(num):
            if num > 1000000: return f"{round(num/1000000, 1)}M"
            if num > 1000: return f"{round(num/1000, 1)}K"
            return str(num)

        badge_html = ""
        if mode == 'likes': 
            badge_html = f'<div class="stat-badge">♥ {fmt(like_cnt)} Likes</div>'
        elif mode == 'comments':
            badge_html = f'<div class="stat-badge">💬 {fmt(comm_cnt)} Comments</div>'
        else:
            badge_html = f'<div class="stat-badge">Play</div>'

        html += f"""
        <div class="card">
            <div class="video-wrapper">
                <iframe src="https://www.youtube.com/embed/{v['id']}" loading="lazy" allowfullscreen></iframe>
            </div>
            <div class="info">
                <div class="title">{v['snippet']['title']}</div>
                <div class="meta">
                    <span style="font-weight:500">{v['snippet']['channelTitle']}</span>
                    {badge_html}
                </div>
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    global_pool = fetch_global_pool(youtube)
    most_liked = sorted(global_pool, key=lambda x: int(x['statistics'].get('likeCount', 0)), reverse=True)[:50]
    most_commented = sorted(global_pool, key=lambda x: int(x['statistics'].get('commentCount', 0)), reverse=True)[:50]
    
    brands = fetch_list_latest(youtube, BRAND_CHANNELS)
    creators = fetch_list_latest(youtube, CREATOR_CHANNELS)
    
    generate_html(most_liked, most_commented, brands, creators)

if __name__ == "__main__":
    main()
