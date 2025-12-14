import os
import datetime
import random
from googleapiclient.discovery import build

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 【名单 A】品牌/商业广告
# 策略：填 15-20 个大品牌，每个抓最新 3 条 -> 凑够约 50 条
BRAND_CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', # Apple
    'UCL8RlvQSa4YEj74wLBSku-A', # Nike
    'UCblfuW_4rakIfk66AQ40hIg', # Red Bull
    'UCtI0Hodo5o5dUb67FeUjDeA', # SpaceX
    'UC0UBX6y5bL1sU7Oq6wMv0aA', # Samsung
    'UCx5XG1Lnc65_3rLqQWa_49w', # Louis Vuitton
    'UCOHMGt67_u8FjT_L4t8Zcww', # Gucci
    'UC5WjFrtBdufl6CZojX3D8dQ', # Porsche
    'UCvQECJukTDEUU9Nd6TQq_xg', # Google
    'UCsTcErHg8oDvUnTzoqsYeNw', # Adidas
]

# 【名单 B】个人博主
# 策略：填 15-20 个优质博主
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', # Peter McKinnon
    'UCX6OQ3DkcsbYNE6H8uQQuVA', # MrBeast
    'UCtinbF-Q-fVthA0qFrcFb9Q', # Casey Neistat
    'UCBJycsmduvYEL83R_U4JriQ', # MKBHD
    'UCsooa4yRKGN_zEE8iknghZA', # TED-Ed
    'UCAL3JXZSzSm8AlZyD3nQdBA', # Primitive Technology
    'UC295-Dw_tDNtZXFeAPAW6Aw', # 5-Minute Crafts
    'UCpw269dbC0hDrwNmyq4U66Q', # Dude Perfect
]

# 全球热门扫描范围
TARGET_REGIONS = ['US', 'GB', 'DE', 'FR', 'JP', 'KR', 'TW', 'IN', 'BR', 'AU']

def get_youtube_service():
    if not API_KEY: return None
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 核心优化逻辑：通过 Uploads Playlist 获取视频 (极省配额) ---

def fetch_channel_videos_optimized(youtube, channel_ids):
    """
    优化版：不使用 search (100点)，而是获取上传列表 (2点)
    每个频道获取最新 3 个视频
    """
    videos = []
    print(f"正在以低功耗模式抓取 {len(channel_ids)} 个频道...")
    
    # 1. 批量获取频道的 ContentDetails (找到他们的上传列表ID)
    # YouTube API 允许一次查 50 个频道
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        try:
            res = youtube.channels().list(
                id=','.join(batch),
                part='contentDetails'
            ).execute()
            
            # 2. 遍历每个频道，去抓它的上传列表
            for item in res['items']:
                uploads_list_id = item['contentDetails']['relatedPlaylists']['uploads']
                
                # 获取该列表最新的 3 个视频
                playlist_res = youtube.playlistItems().list(
                    playlistId=uploads_list_id,
                    part='snippet,contentDetails',
                    maxResults=3  # 这里控制每个频道抓几个
                ).execute()
                
                for vid_item in playlist_res['items']:
                    # 格式化一下，保持统一
                    video_data = {
                        'id': vid_item['contentDetails']['videoId'],
                        'snippet': vid_item['snippet']
                    }
                    videos.append(video_data)
                    
        except Exception as e:
            print(f"频道批量获取出错: {e}")
            
    # 3. 批量获取这些视频的统计数据 (点赞/评论数)
    # 因为 playlistItems 不返回 viewCount，必须多这一步
    final_videos = []
    video_ids_list = [v['id'] for v in videos]
    
    print(f"正在获取 {len(video_ids_list)} 个视频的详细数据...")
    
    for i in range(0, len(video_ids_list), 50):
        batch_ids = video_ids_list[i:i+50]
        try:
            stats_res = youtube.videos().list(
                id=','.join(batch_ids),
                part='statistics,snippet'
            ).execute()
            final_videos.extend(stats_res['items'])
        except Exception as e:
            print(f"详情获取出错: {e}")

    return final_videos

def fetch_global_pool(youtube):
    """获取全球热门"""
    print("正在扫描全球热门...")
    videos = []
    seen_ids = set()
    
    for region in TARGET_REGIONS:
        try:
            res = youtube.videos().list(
                chart='mostPopular',
                regionCode=region,
                part='snippet,statistics',
                maxResults=10 
            ).execute()
            
            for item in res['items']:
                if item['id'] not in seen_ids:
                    videos.append(item)
                    seen_ids.add(item['id'])
        except:
            pass
    return videos

# --- 网页生成 ---
def generate_html(most_liked, most_commented, brands, creators):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | World Edition</title>
        <style>
            :root {{ --bg: #050505; --card: #141414; --text: #e5e5e5; --accent: #fff; }}
            body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; }}
            
            header {{ padding: 80px 20px 50px; text-align: center; background: radial-gradient(circle at top, #1a1a1a 0%, #050505 80%); }}
            h1 {{ margin: 0; font-size: 3rem; letter-spacing: -2px; font-weight: 800; background: linear-gradient(to right, #fff, #888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .date {{ color: #666; font-size: 0.8rem; margin-top: 15px; letter-spacing: 3px; text-transform: uppercase; }}
            
            .nav {{ display: flex; justify-content: center; gap: 30px; padding: 20px; border-bottom: 1px solid #222; position: sticky; top: 0; background: rgba(5,5,5,0.95); backdrop-filter: blur(10px); z-index: 99; overflow-x: auto; }}
            .btn {{ background: none; border: none; color: #666; cursor: pointer; font-size: 0.9rem; padding: 10px 15px; font-weight: 600; white-space: nowrap; transition: 0.3s; }}
            .btn:hover {{ color: #fff; }}
            .btn.active {{ color: #fff; border-bottom: 2px solid #fff; }}
            
            .container {{ max-width: 1600px; margin: 0 auto; padding: 40px 20px; min-height: 80vh; }}
            .tab {{ display: none; animation: fade 0.6s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 40px 30px; }}
            .card {{ background: transparent; transition: transform 0.3s; }}
            .card:hover .vid {{ transform: scale(1.03); box-shadow: 0 20px 40px rgba(0,0,0,0.6); }}
            
            .vid {{ position: relative; padding-bottom: 56.25%; background: #111; border-radius: 8px; transition: all 0.4s ease; overflow: hidden; }}
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
            <div class="date">{today} • WORLD EDITION</div>
        </header>
        <nav class="nav">
            <button class="btn active" onclick="show('likes', this)">Global Top Liked</button>
            <button class="btn" onclick="show('comments', this)">Global Top Discussed</button>
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
    if not videos: return "<p style='color:#666; padding:20px; text-align:center'>Loading...</p>"
    html = ""
    for v in videos:
        s = v.get('statistics', {})
        like = int(s.get('likeCount', 0))
        comm = int(s.get('commentCount', 0))
        view = int(s.get('viewCount', 0))
        
        def fmt(n): return f"{round(n/1000000,1)}M" if n>1000000 else (f"{round(n/1000,1)}K" if n>1000 else str(n))
        
        badge = ""
        if mode == 'likes': badge = f"♥ {fmt(like)}"
        elif mode == 'comments': badge = f"💬 {fmt(comm)}"
        else: badge = f"👁️ {fmt(view)}"
        
        html += f"""
        <div class="card">
            <div class="vid"><iframe src="https://www.youtube.com/embed/{v['id']}" loading="lazy" allowfullscreen></iframe></div>
            <div class="info">
                <div class="title" title="{v['snippet']['title']}">{v['snippet']['title']}</div>
                <div class="meta">
                    <span style="max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{v['snippet']['channelTitle']}</span>
                    <span class="hl">{badge}</span>
                </div>
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    # 1. 获取全球大池子
    global_pool = fetch_global_pool(youtube)
    most_liked = sorted(global_pool, key=lambda x: int(x['statistics'].get('likeCount', 0)), reverse=True)[:50]
    most_commented = sorted(global_pool, key=lambda x: int(x['statistics'].get('commentCount', 0)), reverse=True)[:50]
    
    # 2. 抓取关注列表 (优化版)
    # 现在的逻辑是：每个频道抓 3 个，所以填 17 个 ID 就能凑够 50 条
    brands = fetch_channel_videos_optimized(youtube, BRAND_CHANNELS)
    creators = fetch_channel_videos_optimized(youtube, CREATOR_CHANNELS)
    
    generate_html(most_liked, most_commented, brands, creators)

if __name__ == "__main__":
    main()
