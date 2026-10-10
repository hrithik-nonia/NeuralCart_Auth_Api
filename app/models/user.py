from pydantic import BaseModel, EmailStr, Field, field_validator

    
class UserRegister(BaseModel):
  name: str = Field(min_length=2, max_length=50)
  email: EmailStr
  password: str = Field(min_length=8, max_length=128)
    
class UserLoginResponse(BaseModel):
  message: str = Field(min_length= 2, max_length= 100)
  name: str = Field(min_length=2, max_length=50)
  email: EmailStr
  
class UserLoginInput(BaseModel):
  email: EmailStr
  password: str

  @field_validator("email")
  @classmethod
  def lowercase_email(cls, v: str) -> str:
      return v.lower()
    
class LoginUser(BaseModel):
  name: str
  email: str
  
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LoginUser