import os
import datetime
from googleapiclient.discovery import build

# --- 配置 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 想要监控的品牌频道 ID (例如: Apple, Nike, Sony)
CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', # Apple
    'UC0UBX6y5bL1sU7Oq6wMv0aA', # Example Brand
]

def get_youtube_data():
    if not API_KEY:
        return []
    
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    videos = []
    
    # 1. 获取品牌最新视频
    for channel_id in CHANNELS:
        try:
            res = youtube.search().list(
                channelId=channel_id, part='snippet', order='date', maxResults=2, type='video'
            ).execute()
            for item in res['items']:
                videos.append(item)
        except:
            pass

    # 2. 获取热门视频 (美国区)
    try:
        res = youtube.videos().list(
            chart='mostPopular', regionCode='US', part='snippet,statistics', maxResults=6
        ).execute()
        for item in res['items']:
            item['id'] = {'videoId': item['id']} # 统一格式
            videos.append(item)
    except:
        pass
        
    return videos

def generate_html(videos):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>每日视频精选 - {today}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            h1 {{ text-align: center; color: #333; }}
            .update-time {{ text-align: center; color: #666; margin-bottom: 30px; }}
            .video-card {{ background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 25px; }}
            .video-wrapper {{ position: relative; padding-bottom: 56.25%; height: 0; }}
            .video-wrapper iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; }}
            .video-info {{ padding: 15px; }}
            .video-title {{ font-size: 18px; font-weight: bold; margin: 0 0 10px 0; color: #333; }}
            .video-meta {{ font-size: 14px; color: #888; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 每日热门 & 品牌动态</h1>
            <p class="update-time">更新于: {today}</p>
    """

    for v in videos:
        vid = v['id']['videoId']
        title = v['snippet']['title']
        channel = v['snippet']['channelTitle']
        
        html_content += f"""
            <div class="video-card">
                <div class="video-wrapper">
                    <iframe src="https://www.youtube.com/embed/{vid}" allowfullscreen></iframe>
                </div>
                <div class="video-info">
                    <h3 class="video-title">{title}</h3>
                    <div class="video-meta">频道: {channel}</div>
                </div>
            </div>
        """

    html_content += """
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    data = get_youtube_data()
    if data:
        generate_html(data)
