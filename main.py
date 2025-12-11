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
    """抓取全球热门池 (60个用于筛选)"""
    print("正在扫描全球数据池...")
    videos = []
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
                --accent: #ffffff; /* 极简白作为强调色 */
            }}
            
            body {{
                background-color: var(--bg-color);
                color: var(--text-primary);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                overflow-x: hidden;
            }}

            /* 顶部 Header */
            header {{
                padding: 40px 20px;
                text-align: center;
                background: linear-gradient(to bottom, #000 0%, #0a0a0a 100%);
            }}
            
            h1 {{
                font-weight: 200;
                letter-spacing: 4px;
                text-transform: uppercase;
                margin: 0;
                font-size: 1.8rem;
            }}
            
            .date {{ font-size: 0.8rem; color: var(--text-secondary); margin-top: 10px; letter-spacing: 1px; }}

            /* 导航栏 (Tab) */
            .nav-container {{
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-bottom: 30px;
                padding: 0 20px;
                border-bottom: 1px solid #222;
                position: sticky;
                top: 0;
                background: rgba(10, 10, 10, 0.95);
                backdrop-filter: blur(10px);
                z-index: 100;
            }}

            .tab-btn {{
                background: none;
                border: none;
                color: var(--text-secondary);
                font-size: 0.95rem;
                padding: 15px 5px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 500;
                letter-spacing: 0.5px;
                position: relative;
            }}

            .tab-btn:hover {{ color: var(--text-primary); }}

            .tab-btn.active {{
                color: var(--text-primary);
            }}

            .tab-btn.active::after {{
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                width: 100%;
                height: 2px;
                background-color: var(--accent);
            }}

            /* 内容区域 */
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
                min-height: 80vh;
            }}

            .tab-content {{
                display: none;
                animation: fadeIn 0.5s ease;
            }}
            
            .tab-content.active {{ display: block; }}

            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            /* 网格系统 */
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 30px;
            }}

            /* 卡片设计 */
            .card {{
                background: var(--card-bg);
                border-radius: 12px;
                overflow: hidden;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                border: 1px solid #222;
            }}

            .card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.4);
                border-color: #333;
            }}

            .video-wrapper {{
