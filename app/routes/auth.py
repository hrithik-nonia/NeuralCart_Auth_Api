from fastapi import APIRouter, HTTPException, status
from app.models.user import UserRegister
from app.utils.password_service import password_service
from app.database import users_collection
from app.utils.otp_and_email_service import otp_and_email_service
from app.redis import redis_client
import json


# created apirouter instance
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Register End Point
@router.post("/register", status_code= status.HTTP_200_OK)
async def register(user_data: UserRegister):
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
        "email": user_data.email,
        "hashed_password": password_service.hash_password(hashed_password),
        "otp": otp
    }
  
  # save temp data on redis
  await redis_client.setex(
        redis_key,
        300,
        json.dumps(temporary_user)
    )
  
  return {"message": "Otp Sended"}