import os
from upstash_redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()


redis_client = Redis(
    url=os.getenv("REDIS_URL"),
    token=os.getenv("REDIS_TOKEN")
)