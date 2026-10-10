from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

# MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
# MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

# MONGODB_URI = (
#     MONGODB_URI
#     .replace("<db_username>", MONGODB_USERNAME)
#     .replace("<db_password>", MONGODB_PASSWORD)
# )

client = AsyncIOMotorClient(MONGODB_URI,
                            maxPoolSize=50,
                            minPoolSize=10,
                            maxIdleTimeMS=60000,
                            serverSelectionTimeoutMS=5000
                            )

database = client[DATABASE_NAME]

users_collection = database["users"]
refresh_tokens_collection = database["refresh_tokens"]