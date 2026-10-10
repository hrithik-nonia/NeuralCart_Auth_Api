from fastapi import APIRouter, HTTPException, status, Request, Response
from app.models.user import UserRegister, UserLoginResponse, UserLoginInput, LoginResponse, LoginUser
from app.utils.password_service import password_service
from app.database import users_collection, refresh_tokens_collection
from app.utils.otp_and_email_service import otp_and_email_service
from app.redis import redis_client
import json
import hmac
from app.utils.limiter import limiter
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone
from app.utils.jwt_helper import jwt_service, ACCESS_MIN
from bson import ObjectId
import jwt


# created apirouter instance
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Register End Point
@router.post("/register", status_code= status.HTTP_200_OK)
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserRegister):
  # check user hai ya nahi
  is_user = await users_collection.find_one(
      {"email": user_data.email},
      {"_id": 1}
  )
  
  # if user exist
  if is_user:
    raise HTTPException(status_code= status.HTTP_409_CONFLICT, detail="User already exists")
  
  # check in redis
  redis_key = f"register:{user_data.email}"
  is_pending = await redis_client.exists(redis_key)
  
  # if register in redis
  if is_pending:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="OTP already sent. Please verify your email."
    )
  
  # do password hash
  hashed_password = password_service.hash_password(user_data.password)
  
  # create otp
  otp = otp_and_email_service.otp()
  
  # send email
  await otp_and_email_service.send_otp_email(user_data.email, otp)
  
  # temp user
  temporary_user = {
        "name":user_data.name,
        "email": user_data.email,
        "hashed_password": hashed_password,
        "otp": otp,
        "role": "user",
        "google_id": None,
        "attempts": 0
    }
  
  # save temp data on redis
  await redis_client.setex(
        redis_key,
        300,
        json.dumps(temporary_user)
    )
  
  return {"message": "Otp Sended"}


# Verify Otp End Point
@router.post("/verify-otp", status_code= status.HTTP_200_OK)
@limiter.limit("5/minute")
async def verify_otp(request: Request, otp: int, email: str)-> UserLoginResponse:
  # convert email into lower case
  email = email.lower()
  
  # create redis key
  redis_key = f"register:{email}"
  
  # get redis row data
  raw = await redis_client.get(redis_key)
  if not raw:
    raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST, detail="OTP expired or invalid")
  
  
  # convert row data into json data
  data = json.loads(raw)
  
  # attempts limit
  if data.get("attempts", 0) >= 5:
      await redis_client.delete(redis_key)
      raise HTTPException(status_code= status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts, register again")
    
  # otp match
  if not hmac.compare_digest(str(data["otp"]), str(otp)):
    data["attempts"] = data.get("attempts", 0) + 1
    await redis_client.set(redis_key, json.dumps(data), keepttl=True)
    raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST, detail= "Invalid OTP")
  
  # sahi otp: pehle Redis se hatao
  await redis_client.delete(redis_key)
  
  # insert data from db
  try:
    await users_collection.insert_one({
        "name": data["name"],
        "email": data["email"],
        "password": data["hashed_password"],
        "role": data["role"],
        "is_active": True,
        "google_id": data["google_id"],
        "created_at": datetime.now(timezone.utc),
    })
  except DuplicateKeyError:
        raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST, detail= "User already exists")
      
  return UserLoginResponse(
      message="Account verified",
      name=data["name"],
      email=data["email"],
  )
  
  
# Login End Point
@router.post("/login", status_code= status.HTTP_200_OK)
@limiter.limit("5/minute")
async def login(request: Request,response: Response,  user_data: UserLoginInput)-> LoginResponse:
  # user + password hash dono lo
  user = await users_collection.find_one(
      {"email": user_data.email},
      {"name": 1, "email": 1, "password": 1, "role": 1, "is_active": 1},
  )
  
  
  # user ye pass missing
  if not user or not user.get("password"):
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
  

  # password chack
  if not password_service.verify_password(
      user_data.password, user["password"]
  ):
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

  if not user.get("is_active", True):
      raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account disabled")
      
      
  user_id = str(user["_id"])
  access_token = jwt_service.create_access_token(user_id, user["role"])
  refresh_token = jwt_service.create_refresh_token(user_id, user["role"])
  
  # ✅ JTI nikalo
  refresh_payload = jwt_service.decode(refresh_token, expected_type="refresh")
  
  # ✅ Refresh token data — quotes fix kiye
  refresh_token_data = {
      "user_id": user["_id"],
      "jti": refresh_payload["jti"],
      "is_revoked": False,
      "expires_at": datetime.fromtimestamp(
          refresh_payload["exp"], tz=timezone.utc
      ),
      "created_at": datetime.now(timezone.utc)
  }
  
  # ✅ DB mein save karo
  await refresh_tokens_collection.insert_one(refresh_token_data)
  
  # refresh token httpOnly cookie me
  response.set_cookie(
      "refresh_token", refresh_token,
      httponly=True, secure=False,  # production me True
      samesite="lax", max_age=7 * 24 * 3600, path="/auth",
  )
  
  return LoginResponse(
      access_token=access_token,
      expires_in=ACCESS_MIN * 60,
      user=LoginUser(name=user["name"], email=user["email"]),
  )
  
  
# Refresh Token End Point
@router.post("/refrest", status_code= status.HTTP_200_OK)
@limiter.limit("5/15minute")
async def refresh(request: Request, response: Response):
  # 1. Cookie se refresh token lo
  refresh_token = request.cookies.get("refresh_token")
  if not refresh_token:
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Refresh token missing"
      )
    
  # 2. Token verify karo + expiry check
  try:
      payload = jwt_service.decode(refresh_token, expected_type="refresh")
  except jwt.ExpiredSignatureError:
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Refresh token expire ho gaya"
      )
  except jwt.InvalidTokenError:
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Invalid refresh token"
      )
  
  # 3. User ID nikalo
  user_id = payload.get("sub")
  jti = payload.get("jti")  # token ki unique id
  
  
  # 4. DB mein token validate karo
  stored_token = await refresh_tokens_collection.find_one({
      "user_id": ObjectId(user_id),
      "jti": jti,
      "is_revoked": False
  })
  if not stored_token:
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Token revoked ya exist nahi karta"
      )
  
  # 5. User check karo
  user = await users_collection.find_one({"_id": ObjectId(user_id)})
  if not user or not user.get("is_active"):
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="User nahi mila ya inactive hai"
      )
  
  
  # 6. Naye tokens banao
  new_access_token = jwt_service.create_access_token(user_id, user["role"])
  new_refresh_token = jwt_service.create_refresh_token(user_id, user["role"])
  
  # 7. Naye refresh token ka payload decode karo — jti chahiye
  new_refresh_payload = jwt_service.decode(new_refresh_token, expected_type="refresh")

  # 8. Purana token revoke karo, naya save karo
  await refresh_tokens_collection.update_one(
      {"jti": jti},
      {"$set": {"is_revoked": True}}
  )
  await refresh_tokens_collection.insert_one({
      "user_id": ObjectId(user_id),
      "jti": new_refresh_payload["jti"],
      "is_revoked": False,
      "expires_at": datetime.fromtimestamp(
          new_refresh_payload["exp"], tz=timezone.utc
      ),
      "created_at": datetime.now(timezone.utc)
  })
  
  
  # 9. Cookie mein naya refresh token set karo
  response.set_cookie(
      key="refresh_token",
      value=new_refresh_token,
      httponly=True,
      secure=False,    # Production mein True
      samesite="lax",
      max_age=7 * 24 * 60 * 60  # 7 days
  )

  return {
      "access_token": new_access_token,
      "token_type": "bearer"
  }
  


  