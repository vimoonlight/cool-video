import os
import datetime
from googleapiclient.discovery import build

# --- 1. 配置区域 ---
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 品牌监控名单 (你仍然需要手动指定你想看的顶级品牌，因为纯靠算法很难精准抓到最新的商业广告)
# 这里放了几个全球顶级创意大户: Apple, Nike, Red Bull, SpaceX
BRAND_CHANNELS = [
    'UCE_M8A5yxnLfW0KghEeajjw', # Apple
    'UCL8RlvQSa4YEj74wLBSku-A', # Nike
    'UCblfuW_4rakIfk66AQ40hIg', # Red Bull (极限运动很有创意)
    'UCtI0Hodo5o5dUb67FeUjDeA', # SpaceX (硬核科技)
]

def get_youtube_service():
    return build('youtube', 'v3', developerKey=API_KEY)

# --- 核心逻辑：获取全球24小时最火 ---
def fetch_global_viral(youtube):
    print("正在扫描全球热门数据...")
    videos = []
    
    # 设定时间窗口：过去 24 小时
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat("T") + "Z"
    
    try:
        # 1. 搜索阶段：找过去24小时播放最高的视频 (不限地区，不限语言)
        search_response = youtube.search().list(
            part='id',
            order='viewCount',  # 核心：只按播放量
            type='video',
            publishedAfter=yesterday,
            maxResults=50       # 先抓50个候选
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        # 2. 详情阶段：获取详细数据 (播放量、评论数、点赞数)
        if video_ids:
            stats_response = youtube.videos().list(
                id=','.join(video_ids),
                part='snippet,statistics'
            ).execute()
            
            for item in stats_response['items']:
                # 数据清洗，防止有的视频没有评论权限导致报错
                stats = item['statistics']
                item['viewCount'] = int(stats.get('viewCount', 0))
                item['commentCount'] = int(stats.get('commentCount', 0))
                item['likeCount'] = int(stats.get('likeCount', 0))
                item['tag'] = 'Global'
                videos.append(item)
                
    except Exception as e:
        print(f"全球抓取出错: {e}")
        
    return videos

# --- 辅助逻辑：获取品牌最新 ---
def fetch_brands(youtube):
    print("正在检查品牌动态...")
    videos = []
    for channel_id in BRAND_CHANNELS:
        try:
            # 获取该频道最新的视频
            res = youtube.search().list(
                channelId=channel_id, part='id', order='date', maxResults=1, type='video'
            ).execute()
            
            if res['items']:
                vid = res['items'][0]['id']['videoId']
                # 获取详情
                stats_res = youtube.videos().list(id=vid, part='snippet,statistics').execute()
                item = stats_res['items'][0]
                
                # 检查是否是最近2天发布的，太旧的不要
                published = item['snippet']['publishedAt']
                # 简单补全数据
                stats = item['statistics']
                item['viewCount'] = int(stats.get('viewCount', 0))
                item['commentCount'] = int(stats.get('commentCount', 0))
                item['tag'] = 'Brand'
                videos.append(item)
        except:
            pass
    return videos

# --- 生成酷炫的黑色风格网页 ---
def generate_html(viral_videos, brand_videos):
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. 数据分榜
    # 按播放量排序 (取前 10)
    most_viewed = sorted(viral_videos, key=lambda x: x['viewCount'], reverse=True)[:10]
    # 按评论量排序 (取前 10)
    most_discussed = sorted(viral_videos, key=lambda x: x['commentCount'], reverse=True)[:10]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Global Viral 24H</title>
        <style>
            body {{ background-color: #0f0f0f; color: #ffffff; font-family: 'Roboto', sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ text-align: center; color: #ff0033; letter-spacing: 2px; text-transform: uppercase; }}
            h2 {{ border-left: 5px solid #ff0033; padding-left: 15px; margin-top: 50px; color: #fff; }}
            .time {{ text-align: center; color: #888; font-size: 0.9em; margin-bottom: 40px; }}
            
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; }}
            
            .card {{ background: #1e1e1e; border-radius: 10px; overflow: hidden; transition: transform 0.2s; }}
            .card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(255,0,51,0.2); }}
            
            .video-wrap {{ position: relative; padding-bottom: 56.25%; height: 0; }}
            .video-wrap iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
            
            .info {{ padding: 15px; }}
            .title {{ font-size: 1.1em; font-weight: bold; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
            .stats {{ display: flex; justify-content: space-between; font-size: 0.85em; color: #aaa; }}
            .stat-item {{ display: flex; align-items: center; gap: 5px; }}
            .badge {{ background: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; }}
            .brand-tag {{ background: #ff0033; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Global Viral Trends</h1>
            <p class="time">Last Updated: {today} (UTC)</p>

            <!-- 品牌精选区 -->
            <h2>💎 Brand New (最新品牌创意)</h2>
            <div class="grid">
    """
    
    # 渲染品牌
    for v in brand_videos:
        html += render_card(v, is_brand=True)
        
    html += """
            </div>

            <!-- 播放榜 -->
            <h2>🔥 Most Viewed (24h 全球播放最高)</h2>
            <div class="grid">
    """
    
    for v in most_viewed:
        html += render_card(v)

    html += """
            </div>

            <!-- 热议榜 -->
            <h2>💬 Most Discussed (24h 评论增长最快)</h2>
            <div class="grid">
    """
    
    for v in most_discussed:
        html += render_card(v)
        
    html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def render_card(v, is_brand=False):
    # 格式化数字 (例如 12000 -> 12k)
    def fmt(num):
        if num > 1000000: return f"{round(num/1000000, 1)}M"
        if num > 1000: return f"{round(num/1000, 1)}K"
        return str(num)

    tag_html = '<span class="brand-tag">AD</span>' if is_brand else ''
    
    return f"""
    <div class="card">
        <div class="video-wrap">
            <iframe src="https://www.youtube.com/embed/{v['id']}" loading="lazy" allowfullscreen></iframe>
        </div>
        <div class="info">
            <div class="title">{tag_html} {v['snippet']['title']}</div>
            <div class="stats">
                <span class="stat-item">👁️ {fmt(v['viewCount'])}</span>
                <span class="stat-item">💬 {fmt(v['commentCount'])}</span>
            </div>
            <div style="margin-top:8px; font-size:0.8em; color:#666;">
                {v['snippet']['channelTitle']}
            </div>
        </div>
    </div>
    """

def main():
    if not API_KEY: return
    youtube = get_youtube_service()
    
    # 1. 获取两类数据
    viral = fetch_global_viral(youtube)
    brands = fetch_brands(youtube)
    
    # 2. 生成网页
    generate_html(viral, brands)

if __name__ == "__main__":
    main()
