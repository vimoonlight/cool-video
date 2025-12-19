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
    'UCE_M8A5yxnLfW0KghEeajjw', # Apple
    'UCL8RlvQSa4YEj74wLBSku-A', # Nike
    'UCblfuW_4rakIfk66AQ40hIg', # Red Bull
    'UCtI0Hodo5o5dUb67FeUjDeA', # SpaceX
    'UC0UBX6y5bL1sU7Oq6wMv0aA', # Samsung
    'UCx5XG1Lnc65_3rLqQWa_49w', # Louis Vuitton
    'UC5WjFrtBdufl6CZojX3D8dQ', # Porsche
    'UCvQECJukTDEUU9Nd6TQq_xg', # Google
]

# 【名单 B】个人博主
CREATOR_CHANNELS = [
    'UCbjptxcv1U12W8xc_1fL8HQ', # Peter McKinnon
    'UCX6OQ3DkcsbYNE6H8uQQuVA', # MrBeast
    'UCtinbF-Q-fVthA0qFrcFb9Q', # Casey Neistat
    'UCBJycsmduvYEL83R_U4JriQ', # MKBHD
    'UCsooa4yRKGN_zEE8iknghZA', # TED-Ed
    'UCAL3JXZSzSm8AlZyD3nQdBA', # Primitive Technology
    'UCpw269dbC0hDrwNmyq4U66Q', # Dude Perfect
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

# --- 翻译模块 ---
def translate_text(text):
    if not text: return ""
    try:
        src = text[:400]
        return GoogleTranslator(source='auto', target='zh-CN').translate(src)
    except: return text

# --- 辅助功能 ---
def get_seconds(duration_str):
    if not duration_str: return 0
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?', duration_str)
    if not match: return 0
    d = match.groupdict()
    return int(d['hours'] or 0)*3600 + int(d['minutes'] or 0)*60 + int(d['seconds'] or 0)

def get_beijing_time_str():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")

# --- 核心逻辑 ---

def get_channel_subs_batch(youtube, channel_ids):
    subs_map = {}
    unique_ids = list(set(channel_ids))
    for i in range(0, len(unique_ids), 50):
        try:
            res = youtube.channels().list(
                id=','.join(unique_ids[i:i+50]), 
                part='statistics'
            ).execute()
            for item in res['items']:
                count = int(item['statistics'].get('subscriberCount', 1000000))
                if count == 0: count = 1
                subs_map[item['id']] = count
        except: pass
    return subs_map

def attach_hot_comment(youtube, video_item):
    try:
        res = youtube.commentThreads().list(
            part="snippet", videoId=video_item['id'], 
            order="relevance", maxResults=1, textFormat="plainText"
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
    print("正在进行全球分层扫描...")
    raw_videos = []
    seen_ids = set()
    
    # 1. 抓取
    for code, flag in TARGET_REGIONS.items():
        try:
            res = youtube.videos().list(
                chart='mostPopular', regionCode=code,
                part='snippet,statistics,contentDetails', maxResults=30
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

    # 2. 准备黑马计算
    print("正在计算黑马指数...")
    all_channel_ids = [v['snippet']['channelId'] for v in raw_videos]
    subs_map = get_channel_subs_batch(youtube, all_channel_ids)

    # 3. 分桶
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
        
        if viral_ratio > 3.0 and v['view_cnt'] > 50000:
            bucket_breakout.append(v)
        elif cat == '10': bucket_music.append(v)
        elif cat == '24': bucket_ent.append(v)
        else: bucket_content.append(v)

    # 4. 排序
    bucket_breakout.sort(key=lambda x: x['viral_ratio'], reverse=True)
    
    # 按照点赞排序生成一套
    bucket_music.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['like_cnt'], reverse=True)
    
    liked_set = {
        'breakout': bucket_breakout[:4], # 黑马取前4
        'music': bucket_music[:6],
        'ent': bucket_ent[:4],
        'content': bucket_content[:30]
    }

    # 按照评论排序生成一套
    bucket_music.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['comm_cnt'], reverse=True)

    discuss_set = {
        'music': bucket_music[:6],
        'ent': bucket_ent[:4],
        'content': bucket_content[:30]
    }
    
    print("正在获取神评论...")
    all_selected = liked_set['breakout'] + liked_set['music'] + liked_set['ent'] + liked_set['content']
    # 简单去重获取评论，避免重复请求
    seen_vids = set()
    for v in all_selected:
        if v['id'] not in seen_vids:
            attach_hot_comment(youtube, v)
            seen_vids.add(v['id'])
        
    return liked_set, discuss_set

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

# --- 网页生成 (Ref: Obys / Best Website Gallery / Creative Review) ---
def generate_html(liked_set, discuss_set, brands, creators):
    today_str = get_beijing_time_str()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Design Edition</title>
        <style>
            /* 1. 基础配色：高级灰背景 + 黑色文字 (Ref 1) */
            :root {{ 
                --bg: #F2F2F2; 
                --text: #111; 
                --card-bg: #fff;
                --accent: #000;
                --shadow: 0 4px 20px rgba(0,0,0,0.06);
            }}
            
            body {{ 
                background: var(--bg); 
                color: var(--text); 
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; 
                margin: 0; 
                padding-bottom: 150px; 
            }}
            
            /* 2. 头部设计：超大排版 (Ref 1) */
            header {{ 
                padding: 100px 40px 60px; 
                text-align: center; 
            }}
            h1 {{ 
                margin: 0; 
                font-size: 10vw; /* 响应式超大字体 */
                font-weight: 900; 
                letter-spacing: -4px; 
                line-height: 0.85;
                text-transform: uppercase;
                color: var(--text);
            }}
            .date {{ 
                font-size: 1rem; 
                font-weight: 600;
                margin-top: 20px; 
                letter-spacing: 2px; 
                text-transform: uppercase; 
                color: #666;
            }}
            
            /* 导航栏：简约胶囊 (Ref 3) */
            .nav {{ 
                display: flex; 
                justify-content: center; 
                gap: 15px; 
                padding: 20px; 
                position: sticky; 
                top: 20px; 
                z-index: 99; 
            }}
            .btn {{ 
                background: #fff; 
                border: 1px solid #ddd; 
                color: #666; 
                cursor: pointer; 
                font-size: 0.9rem; 
                padding: 12px 24px; 
                font-weight: 700; 
                border-radius: 50px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                transition: 0.3s; 
                text-transform: uppercase;
            }}
            .btn:hover, .btn.active {{ 
                background: #000; 
                color: #fff; 
                border-color: #000;
                transform: translateY(-2px);
            }}
            
            .container {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
            .tab {{ display: none; animation: fade 0.6s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            /* 3. 特殊板块：黑马榜 (Ref 3 - Creative Review "Our Picks" Style) */
            .breakout-section {{
                background: #000;
                color: #fff;
                padding: 60px 40px;
                border-radius: 20px;
                margin-bottom: 80px;
            }}
            .breakout-header {{
                font-size: 3rem;
                font-weight: 900;
                text-transform: uppercase;
                letter-spacing: -1px;
                margin-bottom: 40px;
                border-bottom: 2px solid #333;
                padding-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
            }}
            .breakout-tag {{ font-size: 1rem; font-weight: 600; color: #ffeb3b; }}
            
            /* 普通板块标题 (Clean Style) */
            .section-title {{ 
                font-size: 2.5rem; 
                font-weight: 800; 
                color: #000; 
                margin: 80px 0 40px;
                text-transform: uppercase;
                letter-spacing: -1px;
                border-left: 8px solid #000;
                padding-left: 20px;
                line-height: 1;
            }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 40px; }}
            
            /* 4. 卡片设计：Gallery 风格 (Ref 2) */
            /* 图片在上，白底文字在下 */
            .card {{ 
                background: var(--card-bg); 
                border-radius: 16px; 
                overflow: hidden; 
                box-shadow: var(--shadow);
                transition: transform 0.3s ease;
                display: flex;
                flex-direction: column;
            }}
            .card:hover {{ transform: translateY(-8px); box-shadow: 0 15px 40px rgba(0,0,0,0.1); }}
            
            .cover-wrap {{ 
                position: relative; 
                padding-bottom: 56.25%; 
                cursor: pointer; 
                overflow: hidden;
            }}
            .cover-wrap img {{ 
                position: absolute; top:0; left:0; width:100%; height:100%; 
                object-fit: cover; 
                transition: transform 0.5s; 
            }}
            .card:hover .cover-wrap img {{ transform: scale(1.05); }}
            
            /* 徽章悬浮在图片上 */
            .badges {{ position: absolute; top: 15px; left: 15px; display: flex; gap: 8px; z-index: 2; }}
            .badge {{ 
                background: rgba(255,255,255,0.9); 
                color: #000; 
                padding: 6px 12px; 
                border-radius: 30px; 
                font-size: 0.75rem; 
                font-weight: 700; 
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            }}
            
            /* 播放按钮 */
            .play-btn {{ 
                position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) scale(0.8); 
                width: 60px; height: 60px; 
                background: rgba(0,0,0,0.7); 
                border-radius: 50%; 
                display: flex; align-items: center; justify-content: center; 
                opacity: 0; transition: 0.3s;
                border: 2px solid #fff;
            }}
            .play-btn::after {{ content: ''; border: 10px solid transparent; border-left: 16px solid #fff; margin-left: 6px; }}
            .cover-wrap:hover .play-btn {{ opacity: 1; transform: translate(-50%, -50%) scale(1); }}

            /* 文字区域 (Ref 2 Style) */
            .info {{ padding: 25px; flex-grow: 1; display: flex; flex-direction: column; }}
            
            .title-zh {{ 
                font-weight: 800; font-size: 1.1rem; color: #000; 
                margin-bottom: 6px; line-height: 1.3; 
            }}
            .title-org {{ 
                font-size: 0.85rem; color: #888; margin-bottom: 15px; 
                font-weight: 500; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;
            }}
            
            .meta-row {{ 
                margin-top: auto; 
                display: flex; justify-content: space-between; align-items: center; 
                border-top: 1px solid #eee; padding-top: 15px; 
                font-size: 0.8rem; color: #555; font-weight: 600;
            }}
            
            .comment {{ 
                background: #f9f9f9; padding: 12px; border-radius: 8px; 
                margin-top: 15px; font-size: 0.85rem; color: #444; 
                font-style: italic; line-height: 1.5; 
            }}
            
            /* 黑马榜卡片特殊样式 (深色卡片) */
            .breakout-section .card { background: #1a1a1a; color: #fff; border: 1px solid #333; }
            .breakout-section .title-zh { color: #fff; }
            .breakout-section .title-org { color: #888; }
            .breakout-section .meta-row { border-color: #333; color: #aaa; }
            .breakout-section .comment { background: #222; color: #ccc; }

        </style>
    </head>
    <body>
        <header>
            <h1>VISION<br>DAILY</h1>
            <div class="date">{today_str} • DESIGN EDITION</div>
        </header>
        
        <nav class="nav">
            <button class="btn active" onclick="show('liked', this)">Top Liked</button>
            <button class="btn" onclick="show('discussed', this)">Top Discussed</button>
            <button class="btn" onclick="show('brands', this)">Brand Zone</button>
            <button class="btn" onclick="show('creators', this)">Creator Zone</button>
        </nav>

        <div class="container">
            
            <!-- 1. Global Top Liked (含黑马) -->
            <div id="liked" class="tab active">
                <!-- 黑马榜：独立深色区块 (Ref 3) -->
                <div class="breakout-section">
                    <div class="breakout-header">
                        <div>🚀 Breakout Hits</div>
                        <div class="breakout-tag">RISING STARS</div>
                    </div>
                    <div class="grid">
                        {render_cards(liked_set['breakout'], 'breakout', 'like')}
                    </div>
                </div>

                <div class="section-title">🎵 Music & Visuals</div>
                <div class="grid">{render_cards(liked_set['music'], 'music', 'like')}</div>
                
                <div class="section-title">🎪 Entertainment</div>
                <div class="grid">{render_cards(liked_set['ent'], 'ent', 'like')}</div>
                
                <div class="section-title">💡 Deep Content</div>
                <div class="grid">{render_cards(liked_set['content'], 'content', 'like')}</div>
            </div>

            <!-- 2. Global Top Discussed -->
            <div id="discussed" class="tab">
                <div class="section-title">💬 Most Discussed</div>
                <div class="grid">{render_cards(discuss_set['content'], 'content', 'comm')}</div>
            </div>

            <!-- 3. Brand Zone -->
            <div id="brands" class="tab">
                <div class="section-title">💎 Brand Zone</div>
                <div class="grid">{render_cards(brands, 'brand', 'view')}</div>
            </div>
            
            <!-- 4. Creator Zone -->
            <div id="creators" class="tab">
                <div class="section-title">🎨 Creator Zone</div>
                <div class="grid">{render_cards(creators, 'creator', 'view')}</div>
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

def render_cards(videos, type, sort_key):
    if not videos: return "<p style='color:#999; padding:20px'>Loading...</p>"
    html = ""
    for v in videos:
        # 徽章
        badges = ""
        if 'region_flag' in v: badges += f"<div class='badge'>{v['region_flag']}</div>"
        if type == 'breakout' and 'viral_ratio' in v:
             badges += f"<div class='badge'>⚡ {round(v['viral_ratio'], 1)}x</div>"
        
        # 评论
        comm = f"<div class='comment'>“ {v['hot_comment']} ”</div>" if v.get('hot_comment') else ""
        
        # 数据
        s = v.get('statistics', {})
        if sort_key == 'like': label = f"♥ {round(int(s.get('likeCount',0))/1000,1)}K"
        elif sort_key == 'comm': label = f"💬 {round(int(s.get('commentCount',0))/1000,1)}K"
        else: label = f"👁️ {round(int(s.get('viewCount',0))/1000,1)}K"
        
        # 标题
        zh = v.get('title_dual', {}).get('zh', v['snippet']['title'])
        org = v.get('title_dual', {}).get('org', '')
        if zh == org: org = ""

        html += f"""
        <div class="card">
            <div class="cover-wrap" onclick="play(this, '{v['id']}')">
                <img src="{v.get('cover')}" loading="lazy">
                <div class="badges">{badges}</div>
                <div class="play-btn"></div>
            </div>
            <div class="info">
                <div class="title-zh">{zh}</div>
                <div class="title-org">{org}</div>
                <div class="meta-row">
                    <span>{v['snippet']['channelTitle']}</span>
                    <span>{label}</span>
                </div>
                {comm}
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    liked_set, discuss_set = fetch_categorized_global_pool(youtube)
    brands = fetch_channel_videos(youtube, BRAND_CHANNELS)
    creators = fetch_channel_videos(youtube, CREATOR_CHANNELS)
    
    generate_html(liked_set, discuss_set, brands, creators)

if __name__ == "__main__":
    main()
