import redis
from app.config import settings
 
def get_redis_client():
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)