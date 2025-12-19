import os
import datetime
import re
from googleapiclient.discovery import build

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 【名单 A】品牌区 (Brand Zone)
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

# 【名单 B】个人博主 (Creator Zone)
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

# 全球扫描范围
TARGET_REGIONS = ['US', 'GB', 'DE', 'FR', 'JP', 'KR', 'TW', 'IN', 'BR', 'AU']

def get_youtube_service():
    if not API_KEY: return None
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 辅助功能 ---
def get_seconds(duration_str):
    if not duration_str: return 0
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?', duration_str)
    if not match: return 0
    time_data = match.groupdict()
    hours = int(time_data['hours'] or 0)
    minutes = int(time_data['minutes'] or 0)
    seconds = int(time_data['seconds'] or 0)
    return hours * 3600 + minutes * 60 + seconds

def get_beijing_time_str():
    utc_now = datetime.datetime.utcnow()
    beijing_now = utc_now + datetime.timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d")

# --- 核心逻辑 ---
def fetch_filtered_global_pool(youtube):
    print("正在进行全球扫描...")
    raw_videos = []
    seen_ids = set()
    
    # 抓取全球热门
    for region in TARGET_REGIONS:
        try:
            res = youtube.videos().list(
                chart='mostPopular', regionCode=region,
                part='snippet,statistics,contentDetails', maxResults=15
            ).execute()
            for item in res['items']:
                if item['id'] not in seen_ids:
                    raw_videos.append(item)
                    seen_ids.add(item['id'])
        except: pass

    # 分桶与清洗
    bucket_music = []
    bucket_entertainment = []
    bucket_content = []
    
    for v in raw_videos:
        # 1. 过滤 Shorts (<60s)
        duration = v['contentDetails'].get('duration', '')
        if get_seconds(duration) < 60: continue

        # 2. 过滤黑名单 (儿童/新闻/游戏)
        cat_id = v['snippet'].get('categoryId', '0')
        if cat_id in ['1', '20', '25']: continue
        
        # 3. 填充数据
        v['like_count'] = int(v['statistics'].get('likeCount', 0))
        v['comment_count'] = int(v['statistics'].get('commentCount', 0))
        
        # 4. 获取高清封面
        thumbs = v['snippet']['thumbnails']
        v['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']

        if cat_id == '10': bucket_music.append(v)
        elif cat_id == '24': bucket_entertainment.append(v)
        else: bucket_content.append(v)

    # 排序与截断
    bucket_music.sort(key=lambda x: x['like_count'], reverse=True)
    bucket_entertainment.sort(key=lambda x: x['like_count'], reverse=True)
    bucket_content.sort(key=lambda x: x['like_count'], reverse=True)
    
    return bucket_music[:7] + bucket_entertainment[:5] + bucket_content[:40]

def fetch_channel_videos_optimized(youtube, channel_ids):
    videos = []
    # 获取上传列表
    for i in range(0, len(channel_ids), 50):
        try:
            res = youtube.channels().list(id=','.join(channel_ids[i:i+50]), part='contentDetails').execute()
            for item in res['items']:
                uid = item['contentDetails']['relatedPlaylists']['uploads']
                # 获取视频
                pl_res = youtube.playlistItems().list(playlistId=uid, part='snippet', maxResults=3).execute()
                for vid in pl_res['items']:
                    v_data = {'id': vid['snippet']['resourceId']['videoId'], 'snippet': vid['snippet']}
                    # 获取封面
                    thumbs = vid['snippet']['thumbnails']
                    v_data['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']
                    videos.append(v_data)
        except: pass
            
    # 补全统计数据
    final_videos = []
    vid_ids = [v['id'] for v in videos]
    for i in range(0, len(vid_ids), 50):
        try:
            stats = youtube.videos().list(id=','.join(vid_ids[i:i+50]), part='statistics').execute()
            # 合并数据
            for j, s_item in enumerate(stats['items']):
                # 找到对应的原始数据(简单对齐)
                if j < len(videos[i:i+50]):
                    v_ref = videos[i+j]
                    if v_ref['id'] == s_item['id']:
                        v_ref['statistics'] = s_item['statistics']
                        final_videos.append(v_ref)
        except: pass
    return final_videos

# --- 网页生成 (采用封面+点击播放模式) ---
def generate_html(most_liked, most_commented, brands, creators):
    today_str = get_beijing_time_str()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Global</title>
        <style>
            :root {{ --bg: #050505; --card: #141414; --text: #e5e5e5; }}
            body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif; margin: 0; }}
            
            header {{ padding: 80px 20px 40px; text-align: center; }}
            h1 {{ margin: 0; font-size: 3rem; font-weight: 800; background: linear-gradient(to right, #fff, #888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .date {{ color: #666; font-size: 0.8rem; margin-top: 10px; letter-spacing: 2px; text-transform: uppercase; }}
            
            .nav {{ display: flex; justify-content: center; gap: 30px; padding: 20px; border-bottom: 1px solid #222; position: sticky; top: 0; background: rgba(5,5,5,0.95); backdrop-filter: blur(10px); z-index: 99; overflow-x: auto; }}
            .btn {{ background: none; border: none; color: #666; cursor: pointer; font-size: 0.9rem; padding: 10px 15px; font-weight: 600; white-space: nowrap; transition: 0.3s; }}
            .btn.active {{ color: #fff; border-bottom: 2px solid #fff; }}
            
            .container {{ max-width: 1600px; margin: 0 auto; padding: 40px 20px; min-height: 80vh; }}
            .tab {{ display: none; animation: fade 0.6s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 30px; }}
            .card {{ background: transparent; }}
            
            /* 核心修改：封面图模式 */
            .vid-wrap {{ 
                position: relative; padding-bottom: 56.25%; background: #111; border-radius: 8px; overflow: hidden; cursor: pointer;
                transition: transform 0.3s;
            }}
            .vid-wrap:hover {{ transform: scale(1.02); }}
            .vid-wrap img {{ position: absolute; top:0; left:0; width:100%; height:100%; object-fit: cover; opacity: 0.9; transition: opacity 0.3s; }}
            .vid-wrap:hover img {{ opacity: 1; }}
            
            /* 播放按钮 */
            .play-icon {{
                position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
                width: 50px; height: 50px; background: rgba(0,0,0,0.7); border-radius: 50%;
                display: flex; align-items: center; justify-content: center; border: 2px solid #fff;
                transition: background 0.3s;
            }}
            .play-icon::after {{ content: ''; border-style: solid; border-width: 10px 0 10px 18px; border-color: transparent transparent transparent #fff; margin-left: 4px; }}
            .vid-wrap:hover .play-icon {{ background: #f00; border-color: #f00; }}

            .info {{ padding-top: 12px; }}
            .title {{ font-weight: 600; font-size: 0.95rem; margin-bottom: 6px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
            .meta {{ color: #888; font-size: 0.8rem; display: flex; justify-content: space-between; }}
            .hl {{ color: #fff; font-weight: bold; background: #222; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <header>
            <h1>VISION</h1>
            <div class="date">{today_str} • WORLD EDITION</div>
        </header>
        <nav class="nav">
            <button class="btn active" onclick="show('likes', this)">Top Liked</button>
            <button class="btn" onclick="show('comments', this)">Top Discussed</button>
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
            
            // 点击加载视频功能
            function playVideo(wrapper, videoId) {{
                wrapper.innerHTML = '<iframe src="https://www.youtube.com/embed/' + videoId + '?autoplay=1" allow="autoplay" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
            }}
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def render(videos, mode):
    if not videos: return "<p style='color:#666'>Updating...</p>"
    html = ""
    for v in videos:
        s = v.get('statistics', {})
        like = int(s.get('likeCount', 0))
        comm = int(s.get('commentCount', 0))
        def fmt(n): return f"{round(n/1000000,1)}M" if n>1000000 else (f"{round(n/1000,1)}K" if n>1000 else str(n))
        
        badge = ""
        if mode == 'likes': badge = f"♥ {fmt(like)}"
        elif mode == 'comments': badge = f"💬 {fmt(comm)}"
        else: badge = "PLAY"
        
        # 核心：生成封面图结构，onclick 触发 iframe
        html += f"""
        <div class="card">
            <div class="vid-wrap" onclick="playVideo(this, '{v['id']}')">
                <img src="{v.get('cover', '')}" loading="lazy">
                <div class="play-icon"></div>
            </div>
            <div class="info">
                <div class="title">{v['snippet']['title']}</div>
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
    
    # 1. 抓取与清洗
    clean_pool = fetch_filtered_global_pool(youtube)
    # 2. 排序
    most_liked = sorted(clean_pool, key=lambda x: int(x['statistics'].get('likeCount', 0)), reverse=True)
    most_commented = sorted(clean_pool, key=lambda x: int(x['statistics'].get('commentCount', 0)), reverse=True)
    # 3. 抓取列表
    brands = fetch_channel_videos_optimized(youtube, BRAND_CHANNELS)
    creators = fetch_channel_videos_optimized(youtube, CREATOR_CHANNELS)
    
    generate_html(most_liked, most_commented, brands, creators)

if __name__ == "__main__":
    main()
