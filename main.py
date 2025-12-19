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
            if len(zh) > 25: zh = zh[:23] + "..."
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
                part='snippet,statistics,contentDetails', maxResults=35
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
        v['view_cnt'] = int(v['statistics'].get('viewCount', 0))
        v['comm_cnt'] = int(v['statistics'].get('commentCount', 0))
        cid = v['snippet']['channelId']
        subs = subs_map.get(cid, 10000000)
        
        viral_ratio = v['view_cnt'] / subs
        v['viral_ratio'] = viral_ratio
        
        thumbs = v['snippet']['thumbnails']
        v['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']
        
        # 黑马判定
        if viral_ratio > 3.0 and v['view_cnt'] > 50000:
            bucket_breakout.append(v)
        elif cat == '10': bucket_music.append(v)
        elif cat == '24': bucket_ent.append(v)
        else: bucket_content.append(v)

    # 4. 排序
    bucket_breakout.sort(key=lambda x: x['viral_ratio'], reverse=True)
    
    bucket_music.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['like_cnt'], reverse=True)
    
    liked_set = {
        'music': bucket_music[:7],
        'ent': bucket_ent[:5],
        'content': bucket_content[:35]
    }

    bucket_music.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['comm_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['comm_cnt'], reverse=True)

    discuss_set = {
        'music': bucket_music[:7],
        'ent': bucket_ent[:5],
        'content': bucket_content[:35]
    }
    
    # 5. 获取神评论
    print("正在获取神评论...")
    final_breakout = bucket_breakout[:20] 
    all_selected = final_breakout + liked_set['music'] + liked_set['ent'] + liked_set['content']
    seen_vids = set()
    for v in all_selected:
        if v['id'] not in seen_vids:
            attach_hot_comment(youtube, v)
            seen_vids.add(v['id'])
        
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

# --- 网页生成 (高级灰 + 吸顶导航) ---
def generate_html(breakout, liked_set, discuss_set, brands, creators):
    today_str = get_beijing_time_str()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Design Edition</title>
        <style>
            /* 1. 配色方案：高级灰 (Ref: Awwwards) */
            :root {{ 
                --bg: #F2F2F2; 
                --text: #111; 
                --card-bg: #fff;
                --accent: #000;
                --shadow: 0 10px 30px rgba(0,0,0,0.06);
            }}
            
            body {{ 
                background: var(--bg); 
                color: var(--text); 
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; 
                margin: 0; 
                padding-bottom: 100px; 
            }}
            
            /* 2. 头部：超大字体 (Ref: OBYS) */
            header {{ 
                padding: 100px 20px 60px; 
                text-align: center; 
            }}
            h1 {{ 
                margin: 0; 
                font-size: 10vw; 
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
            
            /* 3. 吸顶导航栏 (Sticky + Gallery Style) */
            .nav-container {{
                position: sticky;
                top: 0;
                z-index: 999;
                background: rgba(242, 242, 242, 0.95); /* 与背景色一致的毛玻璃 */
                backdrop-filter: blur(10px);
                border-bottom: 1px solid #ddd;
                padding: 20px 0;
                display: flex;
                justify-content: center;
                gap: 15px;
                overflow-x: auto;
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
                box-shadow: 0 4px 10px rgba(0,0,0,0.05);
                transition: 0.3s; 
                text-transform: uppercase;
                white-space: nowrap;
            }}
            .btn:hover {{ 
                background: #000; 
                color: #fff; 
                border-color: #000;
                transform: translateY(-2px);
            }}
            
            /* 选中状态 */
            .btn.active {{ 
                background: #000; 
                color: #fff; 
                border-color: #000;
            }}
            
            /* 黑马榜按钮特殊样式 */
            .btn-breakout {{ font-weight: 900; letter-spacing: 0.5px; }}

            .container {{ max-width: 1600px; margin: 0 auto; padding: 40px 20px; min-height: 80vh; }}
            .tab {{ display: none; animation: fade 0.5s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(15px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            /* 分区标题 (黑色加粗) */
            .section-title {{ 
                display: flex; align-items: center; margin: 60px 0 30px; 
                font-size: 2rem; font-weight: 900; color: #000;
                letter-spacing: -1px;
            }}
            .section-title::before {{ content: ''; width: 8px; height: 32px; background: #000; margin-right: 15px; }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 40px 30px; }}
            
            /* 4. 卡片设计：白卡片 + 悬浮徽章 */
            .card {{ 
                position: relative; 
                border-radius: 16px; 
                overflow: hidden; 
                background: var(--card-bg); 
                transition: transform 0.3s ease; 
                box-shadow: var(--shadow);
                display: flex; flex-direction: column;
            }}
            .card:hover {{ transform: translateY(-8px); box-shadow: 0 20px 40px rgba(0,0,0,0.1); }}
            
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
            
            .play-btn {{ 
                position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) scale(0.8); 
                width: 60px; height: 60px; 
                background: rgba(255,255,255,0.8); 
                border-radius: 50%; backdrop-filter: blur(5px); 
                display: flex; align-items: center; justify-content: center; 
                opacity: 0; transition: all 0.3s;
                box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            }}
            .play-btn::after {{ content: ''; border: 10px solid transparent; border-left: 16px solid #000; margin-left: 6px; }}
            .card:hover .play-btn {{ opacity: 1; transform: translate(-50%, -50%) scale(1); }}

            /* 悬浮徽章 */
            .badge-top-right {{ 
                position: absolute; top: 15px; right: 15px; 
                display: flex; flex-direction: column; gap: 8px; align-items: flex-end;
                z-index: 5;
            }}
            .badge-item {{ 
                background: rgba(255,255,255,0.95); 
                padding: 6px 12px; border-radius: 20px; 
                font-size: 0.75rem; color: #000; 
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                font-weight: 700; 
                display: flex; align-items: center; gap: 5px; 
            }}
            
            .info {{ padding: 25px; display: flex; flex-direction: column; flex-grow: 1; }}
            .title-zh {{ font-weight: 800; font-size: 1.1rem; color: #000; margin-bottom: 6px; line-height: 1.3; }}
            .title-org {{ font-size: 0.85rem; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 15px; }}
            
            .meta-row {{ 
                margin-top: auto; 
                display: flex; justify-content: space-between; align-items: center; 
                border-top: 1px solid #f0f0f0; padding-top: 15px;
                font-size: 0.8rem; color: #666; font-weight: 600;
            }}
            .channel-name {{ display: flex; align-items: center; gap: 6px; }}
            .channel-name::before {{ content:''; width:8px; height:8px; background:#000; border-radius:50%; }}
            
            .comment {{ 
                font-size: 0.85rem; color: #555; background: #f9f9f9; 
                padding: 12px; border-radius: 8px; line-height: 1.5; 
                font-style: italic; margin-top: 15px;
            }}

        </style>
    </head>
    <body>
        <!-- 头部 -->
        <header>
            <h1>VISION<br>DAILY</h1>
            <div class="date">{today_str} • DESIGN EDITION</div>
        </header>
        
        <!-- 吸顶导航 -->
        <nav class="nav-container">
            <button class="btn btn-breakout active" onclick="show('breakout', this)">🚀 Breakout Hits</button>
            <button class="btn" onclick="show('liked', this)">Top Liked</button>
            <button class="btn" onclick="show('discussed', this)">Top Discussed</button>
            <button class="btn" onclick="show('brands', this)">Brand Zone</button>
            <button class="btn" onclick="show('creators', this)">Creator Zone</button>
        </nav>

        <div class="container">
            <!-- 1. Breakout Hits (黑马) -->
            <div id="breakout" class="tab active">
                <div class="section-title">🚀 Viral & Trending</div>
                <div class="grid">{render_cards(breakout, 'breakout')}</div>
            </div>

            <!-- 2. Liked (分层) -->
            <div id="liked" class="tab">
                <div class="section-title">🎵 Music</div>
                <div class="grid">{render_cards(liked_set['music'], 'music')}</div>
                <div class="section-title">🎪 Entertainment</div>
                <div class="grid">{render_cards(liked_set['ent'], 'ent')}</div>
                <div class="section-title">💡 Deep Dive</div>
                <div class="grid">{render_cards(liked_set['content'], 'content')}</div>
            </div>

            <!-- 3. Discussed (分层) -->
            <div id="discussed" class="tab">
                <div class="section-title">💬 Hot Discussions</div>
                <div class="grid">{render_cards(discuss_set['content'], 'content')}</div>
            </div>

            <!-- 4. Brands -->
            <div id="brands" class="tab">
                <div class="section-title">💎 Brand Zone</div>
                <div class="grid">{render_cards(brands, 'brand')}</div>
            </div>
            
            <!-- 5. Creators -->
            <div id="creators" class="tab">
                <div class="section-title">🎨 Creator Zone</div>
                <div class="grid">{render_cards(creators, 'creator')}</div>
            </div>
        </div>

        <script>
            function show(id, btn) {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                
                document.getElementById(id).classList.add('active');
                btn.classList.add('active');
                
                window.scrollTo({{ top: 200, behavior: 'smooth' }});
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

def render_cards(videos, type):
    if not videos: return "<p style='color:#666'>Searching...</p>"
    html = ""
    for v in videos:
        badges = ""
        # 1. 地区标
        if 'region_flag' in v: badges += f"<div class='badge-item'>{v['region_flag']} Region</div>"
        # 2. 评论标
        if v.get('hot_comment'): badges += f"<div class='badge-item'>💬 Hot</div>"
        # 3. 黑马标
        if type == 'breakout' and 'viral_ratio' in v:
             badges += f"<div class='badge-item' style='color:#d35400'>⚡ {round(v['viral_ratio'], 1)}x Viral</div>"

        # 评论文字
        comm = f"<div class='comment'>“ {v['hot_comment']} ”</div>" if v.get('hot_comment') else ""

        s = v.get('statistics', {})
        view_cnt = int(s.get('viewCount', 0))
        label_view = f"{round(view_cnt/1000, 1)}K Views"
        
        t_zh = v.get('title_dual', {}).get('zh', v['snippet']['title'])
        t_org = v.get('title_dual', {}).get('org', '')
        if t_zh == t_org: t_org = ""

        html += f"""
        <div class="card">
            <div class="cover-wrap" onclick="play(this, '{v['id']}')">
                <img src="{v.get('cover')}" loading="lazy">
                <div class="badge-top-right">
                    {badges}
                </div>
                <div class="play-btn"></div>
            </div>
            <div class="info">
                <div class="title-zh">{t_zh}</div>
                <div class="title-org">{t_org}</div>
                <div class="meta-row">
                    <span class="channel-name">{v['snippet']['channelTitle']}</span>
                    <span>{label_view}</span>
                </div>
                {comm}
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
