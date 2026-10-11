import httpx
import os
from dotenv import load_dotenv 
from fastapi import APIRouter, HTTPException, status, Response
from app.redis import shared_redis
from datetime import datetime, timezone
from fastapi.responses import RedirectResponse
from app.database import users_collection, refresh_tokens_collection
import json
from app.utils.jwt_helper import jwt_service
from urllib.parse import urlencode

load_dotenv()

router = APIRouter(tags=["Google OAuth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


@router.get("/google")
async def google_login():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(google_auth_url)
  
  
@router.get("/google/callback")
async def google_callback(code: str, response: Response):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Google authentication failed"
    )

    async with httpx.AsyncClient() as client:
        # Code se Google access token lo
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        token_data = token_response.json()
        if "error" in token_data:
            raise credentials_exception

        # Google se user info lo
        user_info_response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        user_info = user_info_response.json()

    email = user_info.get("email")
    name = user_info.get("name")

    if not email:
        raise credentials_exception

    # DB mein check karo
    user = await users_collection.find_one({"email": email})

    if not user:
        # Naya user banao
        new_user = {
            "name": name,
            "email": email,
            "password": None,
            "role": "user",
            "is_active": True,
            "auth_provider": "google",
            "google_id": user_info.get("sub"),  # Google ka unique ID
        }
        result = await users_collection.insert_one(new_user)
        user = await users_collection.find_one({"_id": result.inserted_id})
    else:
        # Existing user — google_id aur auth_provider update karo
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "google_id": user_info.get("sub"),
                "auth_provider": "google",
            }}
        )

    user_id = str(user["_id"])
    access_token = jwt_service.create_access_token(user_id, user["role"])
    refresh_token = jwt_service.create_refresh_token(user_id, user["role"])

    # Refresh token DB mein save karo
    refresh_payload = jwt_service.decode(refresh_token, expected_type="refresh")
    await refresh_tokens_collection.insert_one({
        "user_id": user["_id"],
        "jti": refresh_payload["jti"],
        "is_revoked": False,
        "expires_at": datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        "created_at": datetime.now(timezone.utc)
    })

    # Shared Redis mein cache karo
    user_cache_data = {
        "id": user_id,
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

    # Refresh token cookie mein
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=False,
        samesite="lax", max_age=7 * 24 * 3600, path="/auth",
    )

    # Frontend pe redirect karo access token ke saath
    from fastapi.responses import RedirectResponse
    # Frontend pe redirect karo access token ke saath
    redirect = RedirectResponse(
        url=f"http://localhost:3000/oauth/callback?access_token={access_token}",
        status_code=302
    )
    redirect.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=False,
        samesite="lax", max_age=7 * 24 * 3600, path="/auth",
    )
    return redirect