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
    'UCx5XG1Lnc65_3rLqQWa_49w', # Louis Vuitton
    'UCOHMGt67_u8FjT_L4t8Zcww', # Gucci
]

# 【名单 B】个人博主 (Creator Zone)
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', # Peter McKinnon
    'UCX6OQ3DkcsbYNE6H8uQQuVA', # MrBeast
    'UCtinbF-Q-fVthA0qFrcFb9Q', # Casey Neistat
    'UCBJycsmduvYEL83R_U4JriQ', # MKBHD
    'UCsooa4yRKGN_zEE8iknghZA', # TED-Ed
    'UCAL3JXZSzSm8AlZyD3nQdBA', # Primitive Technology
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
    """强力抓取全球热门池 (强制翻页以获取更多数据)"""
    print("正在扫描全球数据池 (Deep Scan)...")
    videos = []
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat("T") + "Z"
    
    # 我们将收集到的 ID 先存这里
    candidate_ids = []
    next_page_token = None
    
    # 循环抓取，最多抓 3 页 (每页50个，理论上限150个候选)
    for _ in range(3):
        try:
            search_response = youtube.search().list(
                part='id', 
                order='viewCount', 
                type='video', 
                publishedAfter=yesterday, 
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in search_response['items']:
                candidate_ids.append(item['id']['videoId'])
            
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break # 没有下一页了
                
        except Exception as e:
            print(f"搜索翻页出错: {e}")
            break
    
    print(f"共找到 {len(candidate_ids)} 个候选视频 ID，正在获取详细数据...")

    # YouTube API 限制一次最多查 50 个详情，所以要分批查询
    # Python 切片技巧: candidates[0:50], candidates[50:100], ...
    for i in range(0, len(candidate_ids), 50):
        batch_ids = candidate_ids[i : i+50]
        if not batch_ids: continue
        
        try:
            stats_response = youtube.videos().list(
                id=','.join(batch_ids), 
                part='snippet,statistics'
            ).execute()
            videos.extend(stats_response['items'])
        except Exception as e:
            print(f"详情获取出错: {e}")

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
        <title>VISION | Global Trends</title>
        <style>
            :root {{
                --bg-color: #050505;
                --card-bg: #141414;
                --text-primary: #e5e5e5;
                --text-secondary: #a3a3a3;
                --accent: #fff;
            }}
            body {{
                background-color: var(--bg-color);
                color: var(--text-primary);
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                margin: 0; padding: 0;
            }}
            header {{
                padding: 60px 20px 40px; text-align: center;
                background: radial-gradient(circle at center, #1a1a1a 0%, #050505 100%);
            }}
            h1 {{ font-weight: 700; letter-spacing: -1px; margin: 0; font-size: 2.5rem; color: #fff; }}
            .date {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 10px; text-transform: uppercase; letter-spacing: 2px; }}
            
            .nav-container {{
                display: flex; justify-content: center; gap: 40px; margin-bottom: 40px;
                padding: 15px 20px; border-bottom: 1px solid #262626; position: sticky; top: 0;
                background: rgba(5, 5, 5, 0.95); backdrop-filter: blur(12px); z-index: 100;
                flex-wrap: wrap;
            }}
            .tab-btn {{
                background: none; border: none; color: #666;
                font-size: 1rem; padding: 10px 0; cursor: pointer;
                transition: color 0.3s ease; font-weight: 500; position: relative;
            }}
            .tab-btn:hover {{ color: #fff; }}
            .tab-btn.active {{ color: #fff; }}
            .tab-btn.active::after {{
                content: ''; position: absolute; bottom: -16px; left: 0;
                width: 100%; height: 2px; background-color: #fff;
            }}
            
            .container {{ max-width: 1600px; margin: 0 auto; padding: 0 40px 60px; min-height: 80vh; }}
            .tab-content {{ display: none; animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1); }}
            .tab-content.active {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 40px 30px; }}
            .card {{
                background: transparent; border-radius: 0; overflow: hidden;
                transition: transform 0.3s ease;
            }}
            .card:hover .video-wrapper {{ transform: scale(1.02); border-radius: 8px; }}
            .video-wrapper {{ 
                position: relative; padding-bottom: 56.25%; height: 0; background: #000; 
                border-radius: 4px; transition: all 0.3s ease; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            }}
            .video-wrapper iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; border-radius: inherit; }}
            
            .info {{ padding: 15px 0 0 0; }}
            .title {{
                font-size: 1rem; font-weight: 500; line-height: 1.4; margin-bottom: 8px;
                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; color: #fff;
            }}
            .meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #888; }}
            .stat-highlight {{ color: #fff; font-weight: 600; }}
        </style>
    </head>
    <body>
        <header>
            <h1>VISION</h1>
            <div class="date">{today} • GLOBAL EDITION</div>
        </header>

        <nav class="nav-container">
            <button class="tab-btn active" onclick="openTab(event, 'likes')">Most Liked</button>
            <button class="tab-btn" onclick="openTab(event, 'comments')">Most Discussed</button>
            <button class="tab-btn" onclick="openTab(event, 'brands')">Brand Selection</button>
            <button class="tab-btn" onclick="openTab(event, 'creators')">Creator Showcase</button>
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
        return "<p style='color:#666; padding:20px'>Loading trends...</p>"
        
    for v in videos:
        stats = v.get('statistics', {})
        like_cnt = int(stats.get('likeCount', 0))
        comm_cnt = int(stats.get('commentCount', 0))
        view_cnt = int(stats.get('viewCount', 0))
        
        def fmt(num):
            if num > 1000000: return f"{round(num/1000000, 1)}M"
            if num > 1000: return f"{round(num/1000, 1)}K"
            return str(num)

        meta_html = ""
        if mode == 'likes': 
            meta_html = f'<span>♥ <span class="stat-highlight">{fmt(like_cnt)}</span></span>'
        elif mode == 'comments':
            meta_html = f'<span>💬 <span class="stat-highlight">{fmt(comm_cnt)}</span></span>'
        else:
            meta_html = f'<span>👁️ {fmt(view_cnt)}</span>'

        html += f"""
        <div class="card">
            <div class="video-wrapper">
                <iframe src="https://www.youtube.com/embed/{v['id']}" loading="lazy" allowfullscreen></iframe>
            </div>
            <div class="info">
                <div class="title" title="{v['snippet']['title']}">{v['snippet']['title']}</div>
                <div class="meta">
                    <span>{v['snippet']['channelTitle']}</span>
                    {meta_html}
                </div>
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    # 1. 抓取全球池 (现在会翻3页，最多拿150个候选)
    global_pool = fetch_global_pool(youtube)
    
    # 2. 排序并取前 50
    most_liked = sorted(global_pool, key=lambda x: int(x['statistics'].get('likeCount', 0)), reverse=True)[:50]
    most_commented = sorted(global_pool, key=lambda x: int(x['statistics'].get('commentCount', 0)), reverse=True)[:50]
    
    # 3. 抓取列表
    brands = fetch_list_latest(youtube, BRAND_CHANNELS)
    creators = fetch_list_latest(youtube, CREATOR_CHANNELS)
    
    generate_html(most_liked, most_commented, brands, creators)

if __name__ == "__main__":
    main()
