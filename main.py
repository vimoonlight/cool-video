import os
import datetime
import re
import html
from googleapiclient.discovery import build
from deep_translator import GoogleTranslator

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 【名单 A】品牌区
BRAND_CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', 'UCL8RlvQSa4YEj74wLBSku-A', 'UCblfuW_4rakIfk66AQ40hIg', 
    'UCtI0Hodo5o5dUb67FeUjDeA', 'UC0UBX6y5bL1sU7Oq6wMv0aA', 'UCx5XG1Lnc65_3rLqQWa_49w', 
    'UC5WjFrtBdufl6CZojX3D8dQ', 'UCvQECJukTDEUU9Nd6TQq_xg'
]

# 【名单 B】个人博主
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', 'UCX6OQ3DkcsbYNE6H8uQQuVA', 'UCtinbF-Q-fVthA0qFrcFb9Q', 
    'UCBJycsmduvYEL83R_U4JriQ', 'UCsooa4yRKGN_zEE8iknghZA', 'UCAL3JXZSzSm8AlZyD3nQdBA', 
    'UCpw269dbC0hDrwNmyq4U66Q'
]

# 全球扫描范围
TARGET_REGIONS = {
    'US': '🇺🇸', 'GB': '🇬🇧', 'DE': '🇩🇪', 'FR': '🇫🇷', 
    'JP': '🇯🇵', 'KR': '🇰🇷', 'TW': '🇹🇼', 'IN': '🇮🇳', 
    'BR': '🇧🇷', 'AU': '🇦🇺'
}

def get_youtube_service():
    if not API_KEY: return None
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 翻译与辅助 ---
def translate_text(text):
    if not text: return ""
    try:
        src = text[:400]
        return GoogleTranslator(source='auto', target='zh-CN').translate(src)
    except: return text

def get_seconds(duration_str):
    if not duration_str: return 0
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?', duration_str)
    if not match: return 0
    d = match.groupdict()
    return int(d['hours'] or 0)*3600 + int(d['minutes'] or 0)*60 + int(d['seconds'] or 0)

def get_beijing_time():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)

# --- 核心数据获取逻辑 ---
def get_channel_subs_batch(youtube, channel_ids):
    subs_map = {}
    unique_ids = list(set(channel_ids))
    for i in range(0, len(unique_ids), 50):
        try:
            res = youtube.channels().list(id=','.join(unique_ids[i:i+50]), part='statistics').execute()
            for item in res['items']:
                count = int(item['statistics'].get('subscriberCount', 1000000))
                if count == 0: count = 1
                subs_map[item['id']] = count
        except: pass
    return subs_map

def attach_hot_comment(youtube, video_item):
    try:
        res = youtube.commentThreads().list(
            part="snippet", videoId=video_item['id'], order="relevance", maxResults=1, textFormat="plainText"
        ).execute()
        if res['items']:
            raw = res['items'][0]['snippet']['topLevelComment']['snippet']['textDisplay']
            raw = html.unescape(raw).replace('\n', ' ')
            zh = translate_text(raw)
            if len(zh) > 30: zh = zh[:28] + "..."
            video_item['hot_comment'] = zh
        else: video_item['hot_comment'] = ""
    except: video_item['hot_comment'] = ""
    return video_item

def fetch_categorized_global_pool(youtube):
    print("正在进行全球扫描...")
    raw_videos = []
    seen_ids = set()
    
    # 扩大抓取量，为 FWA 风格提供足够的素材 (每国 30 -> 40)
    for code, flag in TARGET_REGIONS.items():
        try:
            res = youtube.videos().list(
                chart='mostPopular', regionCode=code,
                part='snippet,statistics,contentDetails', maxResults=40
            ).execute()
            for item in res['items']:
                if item['id'] not in seen_ids:
                    item['region_flag'] = flag
                    org = item['snippet']['title']
                    zh = translate_text(org)
                    item['title_dual'] = {'zh': zh, 'org': org}
                    raw_videos.append(item)
                    seen_ids.add(item['id'])
        except: pass

    # 计算黑马
    print("计算黑马指数...")
    all_cids = [v['snippet']['channelId'] for v in raw_videos]
    subs_map = get_channel_subs_batch(youtube, all_cids)

    bucket_breakout = []
    bucket_music = []
    bucket_ent = []
    bucket_content = []
    
    for v in raw_videos:
        if get_seconds(v['contentDetails'].get('duration', '')) < 60: continue
        cat = v['snippet'].get('categoryId', '0')
        if cat in ['1', '20', '25']: continue
        
        v['like_cnt'] = int(v['statistics'].get('likeCount', 0))
        v['comm_cnt'] = int(v['statistics'].get('commentCount', 0))
        v['view_cnt'] = int(v['statistics'].get('viewCount', 0))
        cid = v['snippet']['channelId']
        subs = subs_map.get(cid, 10000000)
        
        viral_ratio = v['view_cnt'] / subs
        v['viral_ratio'] = viral_ratio
        
        thumbs = v['snippet']['thumbnails']
        v['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']
        
        # 黑马判定：倍率高且播放量不低
        if viral_ratio > 3.0 and v['view_cnt'] > 50000:
            bucket_breakout.append(v)
        elif cat == '10': bucket_music.append(v)
        elif cat == '24': bucket_ent.append(v)
        else: bucket_content.append(v)

    # 排序
    bucket_breakout.sort(key=lambda x: x['viral_ratio'], reverse=True)
    # FWA 风格需要更多黑马，取前 20 个
    final_breakout = bucket_breakout[:20]

    # 常规榜单排序
    bucket_music.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['like_cnt'], reverse=True)
    
    liked_set = {'music': bucket_music[:6], 'ent': bucket_ent[:4], 'content': bucket_content[:30]}
    
    bucket_music.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['comm_cnt'], reverse=True)
    discuss_set = {'music': bucket_music[:6], 'ent': bucket_ent[:4], 'content': bucket_content[:30]}
    
    print("获取评论...")
    # 这里只给 FWA 黑马榜获取评论，因为它是视觉重心
    for v in final_breakout:
        attach_hot_comment(youtube, v)
        
    return final_breakout, liked_set, discuss_set

def fetch_channel_videos(youtube, channel_ids):
    videos = []
    for i in range(0, len(channel_ids), 50):
        try:
            res = youtube.channels().list(id=','.join(channel_ids[i:i+50]), part='contentDetails').execute()
            for item in res['items']:
                uid = item['contentDetails']['relatedPlaylists']['uploads']
                pl = youtube.playlistItems().list(playlistId=uid, part='snippet', maxResults=3).execute()
                for vid in pl['items']:
                    v_data = {'id': vid['snippet']['resourceId']['videoId'], 'snippet': vid['snippet']}
                    thumbs = vid['snippet']['thumbnails']
                    v_data['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']
                    org = vid['snippet']['title']
                    zh = translate_text(org)
                    v_data['title_dual'] = {'zh': zh, 'org': org}
                    videos.append(v_data)
        except: pass
    
    final_videos = []
    vids = [v['id'] for v in videos]
    for i in range(0, len(vids), 50):
        try:
            stats = youtube.videos().list(id=','.join(vids[i:i+50]), part='statistics').execute()
            for j, s in enumerate(stats['items']):
                if j < len(videos[i:i+50]):
                    v = videos[i+j]
                    if v['id'] == s['id']:
                        v['statistics'] = s['statistics']
                        final_videos.append(v)
        except: pass
    return final_videos

# --- 网页生成 (FWA 风格重构) ---
def generate_html(breakout, liked_set, discuss_set, brands, creators):
    now = get_beijing_time()
    today_str = now.strftime("%Y-%m-%d")
    day_num = now.strftime("%d") # 19
    month_str = now.strftime("%B").upper() # DECEMBER
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | FWA Edition</title>
        <style>
            :root {{ 
                --bg: #F0F0F0; 
                --text: #111; 
                --accent: #FFD700; /* FWA 黄色点缀 */
                --black: #000;
            }}
            
            body {{ 
                background: var(--bg); 
                color: var(--text); 
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; 
                margin: 0; padding: 0;
            }}
            
            /* --- 1. 顶部 Hero Section (Breakout Hits) --- */
            /* 黑色通栏，参考你发的第一张图 */
            .hero-section {{
                background: var(--black);
                color: #fff;
                padding: 80px 40px;
                position: relative;
            }}
            
            .hero-header {{
                max-width: 1600px; margin: 0 auto;
                display: flex; justify-content: space-between; align-items: flex-end;
                border-bottom: 4px solid #fff;
                padding-bottom: 20px; margin-bottom: 60px;
            }}
            .hero-title {{ 
                font-size: 5rem; font-weight: 900; letter-spacing: -2px; line-height: 0.9;
                text-transform: uppercase;
            }}
            .hero-date {{
                text-align: right; font-weight: 700; font-size: 1.2rem;
            }}
            .hero-date span {{ display: block; font-size: 3rem; color: var(--accent); }}

            /* FWA 风格时间线布局 */
            .timeline-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
                gap: 40px;
                max-width: 1600px; margin: 0 auto;
            }}
            
            /* FWA 风格卡片 */
            .fwa-card {{
                display: flex; flex-direction: column;
                transition: transform 0.3s;
                position: relative;
            }}
            .fwa-card:hover {{ transform: translateY(-10px); }}
            
            .fwa-cover {{
                position: relative; padding-bottom: 56.25%; /* 16:9 */
                background: #222; overflow: hidden;
                box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                cursor: pointer;
            }}
            .fwa-cover img {{ 
                position: absolute; top:0; left:0; width:100%; height:100%; object-fit: cover; 
                transition: transform 0.5s; opacity: 0.9;
            }}
            .fwa-card:hover .fwa-cover img {{ transform: scale(1.05); opacity: 1; }}
            
            /* FWA 左侧竖线装饰 */
            .fwa-info {{
                margin-top: 20px;
                padding-left: 15px;
                border-left: 3px solid #333;
                transition: border-color 0.3s;
            }}
            .fwa-card:hover .fwa-info {{ border-color: var(--accent); }}
            
            .fwa-title-zh {{ font-size: 1.1rem; font-weight: 800; color: #fff; margin-bottom: 5px; line-height: 1.3; }}
            .fwa-title-org {{ font-size: 0.85rem; color: #888; margin-bottom: 10px; }}
            .fwa-meta {{ font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }}
            
            .play-overlay {{
                position: absolute; top:0; left:0; width:100%; height:100%;
                background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;
                opacity: 0; transition: 0.3s;
            }}
            .fwa-card:hover .play-overlay {{ opacity: 1; }}
            .play-btn {{ width: 60px; height: 60px; background: #fff; border-radius: 50%; }}
            
            /* --- 2. 下半部分 (常规内容) --- */
            .content-section {{
                padding: 60px 40px;
                max-width: 1600px; margin: 0 auto;
            }}
            
            .nav {{ 
                display: flex; justify-content: center; gap: 20px; margin-bottom: 60px; 
                position: sticky; top: 20px; z-index: 99;
            }}
            .btn {{ 
                background: #fff; border: 1px solid #ccc; color: #333; 
                padding: 12px 30px; font-weight: 700; border-radius: 4px; 
                cursor: pointer; text-transform: uppercase; letter-spacing: 1px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.05); transition: 0.2s;
            }}
            .btn:hover, .btn.active {{ background: #000; color: #fff; border-color: #000; }}
            
            .tab {{ display: none; animation: fade 0.5s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            .std-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 30px; }}
            
            .std-card {{ background: #fff; box-shadow: 0 5px 15px rgba(0,0,0,0.05); transition: 0.3s; }}
            .std-card:hover {{ transform: translateY(-5px); box-shadow: 0 15px 30px rgba(0,0,0,0.1); }}
            
            .std-cover {{ position: relative; padding-bottom: 56.25%; background: #eee; cursor: pointer; }}
            .std-cover img {{ position: absolute; top:0; left:0; width:100%; height:100%; object-fit: cover; }}
            
            .std-info {{ padding: 20px; }}
            .std-title {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 5px; color: #000; }}
            .std-meta {{ font-size: 0.8rem; color: #666; display: flex; justify-content: space-between; }}

        </style>
    </head>
    <body>
        
        <!-- Part 1: Breakout Hits (Hero Section) -->
        <div class="hero-section">
            <div class="hero-header">
                <div class="hero-title">Breakout<br>Hits</div>
                <div class="hero-date">{day_num}<br><span>{month_str}</span></div>
            </div>
            
            <!-- FWA Style Grid -->
            <div class="timeline-grid">
                {render_fwa_cards(breakout)}
            </div>
        </div>

        <!-- Part 2: Categories (White Section) -->
        <div class="content-section">
            <nav class="nav">
                <button class="btn active" onclick="show('liked', this)">Top Liked</button>
                <button class="btn" onclick="show('discussed', this)">Top Discussed</button>
                <button class="btn" onclick="show('brands', this)">Brand Zone</button>
                <button class="btn" onclick="show('creators', this)">Creator Zone</button>
            </nav>

            <div id="liked" class="tab active">
                <h3 style="margin:0 0 20px;">🎵 Music</h3>
                <div class="std-grid">{render_std(liked_set['music'], 'like')}</div>
                <h3 style="margin:40px 0 20px;">🎪 Entertainment</h3>
                <div class="std-grid">{render_std(liked_set['ent'], 'like')}</div>
                <h3 style="margin:40px 0 20px;">💡 Stories</h3>
                <div class="std-grid">{render_std(liked_set['content'], 'like')}</div>
            </div>

            <div id="discussed" class="tab">
                <h3 style="margin:0 0 20px;">💬 Most Discussed</h3>
                <div class="std-grid">{render_std(discuss_set['content'], 'comm')}</div>
            </div>

            <div id="brands" class="tab">
                <div class="std-grid">{render_std(brands, 'view')}</div>
            </div>
            
            <div id="creators" class="tab">
                <div class="std-grid">{render_std(creators, 'view')}</div>
            </div>
        </div>

        <script>
            function show(id, btn) {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                document.getElementById(id).classList.add('active');
                btn.classList.add('active');
            }}
            function play(wrap, id) {{
                wrap.innerHTML = '<iframe src="https://www.youtube.com/embed/'+id+'?autoplay=1" allow="autoplay; fullscreen" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>';
            }}
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def render_fwa_cards(videos):
    """渲染 FWA 风格的高级卡片 (黑马榜专用)"""
    if not videos: return "<p>Loading...</p>"
    html = ""
    for v in videos:
        # 倍率标签
        ratio = round(v.get('viral_ratio', 0), 1)
        
        t_zh = v.get('title_dual', {}).get('zh', v['snippet']['title'])
        t_org = v.get('title_dual', {}).get('org', '')
        if t_zh == t_org: t_org = ""
        
        comm = v.get('hot_comment', '')
        if comm: comm = f"“{comm}”"

        html += f"""
        <div class="fwa-card">
            <div class="fwa-cover" onclick="play(this, '{v['id']}')">
                <img src="{v.get('cover')}" loading="lazy">
                <div class="play-overlay">
                    <!-- 简单的播放按钮 SVG -->
                    <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
                        <circle cx="30" cy="30" r="30" fill="white"/>
                        <path d="M40 30L24 40L24 20L40 30Z" fill="black"/>
                    </svg>
                </div>
            </div>
            <div class="fwa-info">
                <div style="color:#FFD700; font-size:0.8rem; margin-bottom:5px;">⚡ {ratio}x VIRAL</div>
                <div class="fwa-title-zh">{t_zh}</div>
                <div class="fwa-title-org">{t_org}</div>
                <div class="fwa-meta">{v['snippet']['channelTitle']}</div>
                <div style="margin-top:10px; font-style:italic; color:#888; font-size:0.85rem;">{comm}</div>
            </div>
        </div>
        """
    return html

def render_std(videos, sort_key):
    """渲染下半部分的常规白色卡片"""
    if not videos: return ""
    html = ""
    for v in videos:
        s = v.get('statistics', {})
        if sort_key == 'like': label = f"♥ {round(int(s.get('likeCount',0))/1000,1)}K"
        elif sort_key == 'comm': label = f"💬 {round(int(s.get('commentCount',0))/1000,1)}K"
        else: label = f"👁️ {round(int(s.get('viewCount',0))/1000,1)}K"
        
        t = v.get('title_dual', {}).get('zh', v['snippet']['title'])
        
        html += f"""
        <div class="std-card">
            <div class="std-cover" onclick="play(this, '{v['id']}')">
                <img src="{v.get('cover')}" loading="lazy">
            </div>
            <div class="std-info">
                <div class="std-title">{t}</div>
                <div class="std-meta">
                    <span>{v['snippet']['channelTitle']}</span>
                    <span>{label}</span>
                </div>
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    breakout, liked_set, discuss_set = fetch_categorized_global_pool(youtube)
    brands = fetch_channel_videos(youtube, BRAND_CHANNELS)
    creators = fetch_channel_videos(youtube, CREATOR_CHANNELS)
    
    generate_html(breakout, liked_set, discuss_set, brands, creators)

if __name__ == "__main__":
    main()
