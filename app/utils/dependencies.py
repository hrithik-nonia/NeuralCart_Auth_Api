from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from bson.errors import InvalidId
import os
from dotenv import load_dotenv
from app.database import users_collection
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import jwt as pyjwt
from app.redis import shared_redis
import json

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

bearer_scheme = HTTPBearer()  # missing header pe khud 403/401 de dega


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = creds.credentials
    

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    
    # user_id nikalne ke baad, DB query se pehle:
    user_id = payload.get("sub")
    if user_id is None:           # ← pehle
        raise credentials_exception

    cached = await shared_redis.get(f"user:{user_id}")  # ← phir cache
    if cached:
        return json.loads(cached)
    
    # Cache miss — DB se lo
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        raise credentials_exception

    if user is None:
        raise credentials_exception

    # DB se mila to cache mein daal do
    user_cache_data = {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "is_active": user.get("is_active", True),
    }
    await shared_redis.setex(
        f"user:{user_id}",
        15 * 60,
        json.dumps(user_cache_data)
    )

    return user