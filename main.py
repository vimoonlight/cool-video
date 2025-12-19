import os
import datetime
import re
import html
from googleapiclient.discovery import build

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

# 全球扫描范围与国旗映射
TARGET_REGIONS = {
    'US': '🇺🇸', 'GB': '🇬🇧', 'DE': '🇩🇪', 'FR': '🇫🇷', 
    'JP': '🇯🇵', 'KR': '🇰🇷', 'TW': '🇹🇼', 'IN': '🇮🇳', 
    'BR': '🇧🇷', 'AU': '🇦🇺'
}

def get_youtube_service():
    if not API_KEY: return None
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 辅助功能 ---
def get_seconds(duration_str):
    if not duration_str: return 0
    match = re.match(r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?', duration_str)
    if not match: return 0
    d = match.groupdict()
    return int(d['hours'] or 0)*3600 + int(d['minutes'] or 0)*60 + int(d['seconds'] or 0)

def get_beijing_time_str():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")

# --- 核心逻辑：获取神评论 ---
def attach_hot_comment(youtube, video_item):
    """获取单条最热、简短的评论"""
    try:
        res = youtube.commentThreads().list(
            part="snippet", videoId=video_item['id'], 
            order="relevance", maxResults=1, textFormat="plainText"
        ).execute()
        
        if res['items']:
            comment = res['items'][0]['snippet']['topLevelComment']['snippet']['textDisplay']
            # 简单清洗：去除换行，限制长度
            clean_comment = html.unescape(comment).replace('\n', ' ')
            if len(clean_comment) > 60:
                clean_comment = clean_comment[:58] + "..."
            video_item['hot_comment'] = clean_comment
        else:
            video_item['hot_comment'] = ""
    except:
        video_item['hot_comment'] = ""
    return video_item

# --- 核心逻辑：全球抓取与分层 ---
def fetch_categorized_global_pool(youtube):
    print("正在进行全球分层扫描...")
    raw_videos = []
    seen_ids = set()
    
    # 1. 抓取 (带上地区标记)
    for code, flag in TARGET_REGIONS.items():
        try:
            res = youtube.videos().list(
                chart='mostPopular', regionCode=code,
                part='snippet,statistics,contentDetails', maxResults=15
            ).execute()
            for item in res['items']:
                if item['id'] not in seen_ids:
                    item['region_flag'] = flag # 打上国旗标签
                    raw_videos.append(item)
                    seen_ids.add(item['id'])
        except: pass

    # 2. 分桶 (Music, Ent, Content)
    bucket_music = []
    bucket_ent = []
    bucket_content = []
    
    print(f"原始池 {len(raw_videos)} 个，开始清洗...")
    
    for v in raw_videos:
        # A. 过滤 Shorts
        if get_seconds(v['contentDetails'].get('duration', '')) < 60: continue
        # B. 过滤 黑名单
        cat = v['snippet'].get('categoryId', '0')
        if cat in ['1', '20', '25']: continue
        
        # C. 数据准备
        v['like_cnt'] = int(v['statistics'].get('likeCount', 0))
        thumbs = v['snippet']['thumbnails']
        v['cover'] = thumbs.get('maxres', thumbs.get('high', thumbs.get('medium')))['url']
        
        # D. 归类
        if cat == '10': bucket_music.append(v)
        elif cat == '24': bucket_ent.append(v)
        else: bucket_content.append(v)

    # 3. 排序与截断
    bucket_music.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_ent.sort(key=lambda x: x['like_cnt'], reverse=True)
    bucket_content.sort(key=lambda x: x['like_cnt'], reverse=True)
    
    final_music = bucket_music[:7]     # 7个 MV
    final_ent = bucket_ent[:5]         # 5个 挑战
    final_content = bucket_content[:35] # 35个 优质内容
    
    # 4. 获取评论 (只给入选的视频获取，节省配额)
    print("正在获取神评论...")
    all_selected = final_music + final_ent + final_content
    for v in all_selected:
        attach_hot_comment(youtube, v)
        
    return final_music, final_ent, final_content

# --- 品牌/博主抓取 (复用) ---
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
                    videos.append(v_data)
        except: pass
        
    # 补全数据
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

# --- 网页生成 (分层布局版) ---
def generate_html(music, ent, content, brands, creators):
    today_str = get_beijing_time_str()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VISION | Daily</title>
        <style>
            :root {{ --bg: #050505; --text: #e5e5e5; --accent: #ff3b30; }}
            body {{ background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; margin: 0; padding-bottom: 100px; }}
            
            header {{ padding: 60px 20px 40px; text-align: center; }}
            h1 {{ margin: 0; font-size: 3rem; font-weight: 800; letter-spacing: -1px; }}
            .date {{ color: #666; font-size: 0.8rem; margin-top: 10px; letter-spacing: 2px; text-transform: uppercase; }}
            
            .nav {{ display: flex; justify-content: center; gap: 30px; padding: 20px; border-bottom: 1px solid #222; position: sticky; top: 0; background: rgba(5,5,5,0.95); z-index: 99; overflow-x: auto; }}
            .btn {{ background: none; border: none; color: #666; cursor: pointer; font-size: 0.9rem; font-weight: 600; transition: 0.3s; }}
            .btn:hover, .btn.active {{ color: #fff; }}
            
            .container {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
            .tab {{ display: none; animation: fade 0.6s; }}
            .tab.active {{ display: block; }}
            @keyframes fade {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
            
            /* 分区标题 */
            .section-title {{ display: flex; align-items: center; margin: 60px 0 30px; font-size: 1.5rem; font-weight: 700; color: #fff; }}
            .section-title::before {{ content: ''; width: 4px; height: 24px; background: var(--accent); margin-right: 15px; border-radius: 2px; }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 40px 30px; }}
            
            /* 卡片样式 */
            .card {{ position: relative; }}
            .vid-wrap {{ position: relative; padding-bottom: 56.25%; background: #111; border-radius: 8px; overflow: hidden; cursor: pointer; transition: transform 0.3s; }}
            .vid-wrap:hover {{ transform: scale(1.02); z-index: 10; }}
            .vid-wrap img {{ position: absolute; top:0; left:0; width:100%; height:100%; object-fit: cover; opacity: 0.9; }}
            .vid-wrap:hover img {{ opacity: 1; }}
            
            /* 国旗标签 */
            .flag-badge {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 1.2rem; backdrop-filter: blur(4px); z-index: 2; }}
            
            /* 播放按钮 */
            .play-icon {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; background: rgba(0,0,0,0.5); border-radius: 50%; border: 2px solid #fff; display: flex; justify-content: center; align-items: center; opacity: 0.8; }}
            .play-icon::after {{ content: ''; border: 8px solid transparent; border-left: 12px solid #fff; margin-left: 4px; }}
            
            .info {{ padding-top: 12px; }}
            .title {{ font-weight: 600; font-size: 0.95rem; margin-bottom: 6px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
            .meta {{ color: #888; font-size: 0.8rem; display: flex; justify-content: space-between; margin-bottom: 8px; }}
            
            /* 神评论样式 */
            .comment {{ font-size: 0.8rem; color: #666; background: #111; padding: 8px 12px; border-radius: 6px; line-height: 1.4; font-style: italic; border-left: 2px solid #333; }}
            .comment::before {{ content: '“'; color: #444; margin-right: 4px; }}
        </style>
    </head>
    <body>
        <header>
            <h1>VISION</h1>
            <div class="date">{today_str} • WORLD EDITION</div>
        </header>
        <nav class="nav">
            <button class="btn active" onclick="show('global', this)">Global Trends</button>
            <button class="btn" onclick="show('brands', this)">Brand Zone</button>
            <button class="btn" onclick="show('creators', this)">Creator Zone</button>
        </nav>

        <div class="container">
            <!-- 全球趋势：分层展示 -->
            <div id="global" class="tab active">
                
                <div class="section-title">🎵 Top Music Videos (全球热播MV)</div>
                <div class="grid">{render_section(music, 'music')}</div>
                
                <div class="section-title">🎪 Viral Challenges (挑战与娱乐)</div>
                <div class="grid">{render_section(ent, 'ent')}</div>
                
                <div class="section-title">💡 Must-Watch Stories (精选优质内容)</div>
                <div class="grid">{render_section(content, 'content')}</div>
                
            </div>

            <div id="brands" class="tab"><div class="grid">{render_section(brands, 'brand')}</div></div>
            <div id="creators" class="tab"><div class="grid">{render_section(creators, 'creator')}</div></div>
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

def render_section(videos, type):
    if not videos: return "<p style='color:#444'>Loading...</p>"
    html = ""
    for v in videos:
        # 国旗逻辑
        flag_html = f"<div class='flag-badge'>{v['region_flag']}</div>" if 'region_flag' in v else ""
        # 评论逻辑
        comment_html = f"<div class='comment'>{v['hot_comment']}</div>" if v.get('hot_comment') else ""
        
        # 数据显示
        s = v.get('statistics', {})
        cnt = int(s.get('viewCount', 0)) if type=='brand' else int(s.get('likeCount', 0))
        label = f"👁️ {round(cnt/1000,1)}K" if type=='brand' else f"♥ {round(cnt/1000,1)}K"
        
        html += f"""
        <div class="card">
            <div class="vid-wrap" onclick="play(this, '{v['id']}')">
                <img src="{v.get('cover')}" loading="lazy">
                {flag_html}
                <div class="play-icon"></div>
            </div>
            <div class="info">
                <div class="title">{v['snippet']['title']}</div>
                <div class="meta">
                    <span>{v['snippet']['channelTitle']}</span>
                    <span>{label}</span>
                </div>
                {comment_html}
            </div>
        </div>
        """
    return html

def main():
    youtube = get_youtube_service()
    if not youtube: return
    
    # 1. 抓取分层全球数据
    music, ent, content = fetch_categorized_global_pool(youtube)
    
    # 2. 抓取关注列表
    brands = fetch_channel_videos(youtube, BRAND_CHANNELS)
    creators = fetch_channel_videos(youtube, CREATOR_CHANNELS)
    
    generate_html(music, ent, content, brands, creators)

if __name__ == "__main__":
    main()
