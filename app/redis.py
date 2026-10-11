import os
from upstash_redis.asyncio import Redis
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()


# Auth ka apna Upstash Redis (pehle se hai, touch nahi kiya)
redis_client = Redis(
    url=os.getenv("REDIS_URL"),
    token=os.getenv("REDIS_TOKEN")
)

# Shared Redis (root Docker wala, user cache ke liye)
shared_redis = aioredis.from_url(
    os.getenv("SHARED_REDIS_URL", "redis://localhost:6379"),
    decode_responses=True
)