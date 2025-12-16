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
    """获取北京时间 (UTC+8) 的日期字符串"""
    utc_now = datetime.datetime.utcnow()
    beijing_now = utc_now + datetime.timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d")

# --- 核心逻辑 1: 智能分拣全球热门 ---
def fetch_filtered_global_pool(youtube):
    print("正在进行全球深度扫描与清洗...")
    raw_videos = []
    seen_ids = set()
    
    # 1. 第一步：海量抓取
    for region in TARGET_REGIONS:
        try:
            res = youtube.videos().list(
                chart='mostPopular',
                regionCode=region,
                part='snippet,statistics,contentDetails', 
                maxResults=20
            ).execute()
            for item in res['items']:
                if item['id'] not in seen_ids:
                    raw_videos.append(item)
                    seen_ids.add(item['id'])
        except: pass

    # 2. 第二步：定义三个桶
    bucket_music = []         # MV (Cat 10)
    bucket_entertainment = [] # 娱乐 (Cat 24)
    bucket_content = []       # 优质内容 (其他)
    
    # 3. 第三步：清洗与分拣
    for v in raw_videos:
        # A. 过滤 Shorts (<60s)
        duration = v['contentDetails'].get('duration', '')
        if get_seconds(duration) < 60: continue

        # B. 过滤 黑名单 (动画/游戏/新闻)
        cat_id = v['snippet'].get('categoryId', '0')
        if cat_id in ['1', '20', '25']: continue
        
        # C. 填充数据
        v['like_count'] = int(v['statistics'].get('likeCount', 0))
        v['comment_count'] = int(v['statistics'].get('commentCount', 0))
        
        # D. 分桶
        if cat_id == '10': # Music
            bucket_music.append(v)
        elif cat_id == '24': # Entertainment
            bucket_entertainment.append(v)
        else: # Tech, Vlog, etc
            bucket_co
