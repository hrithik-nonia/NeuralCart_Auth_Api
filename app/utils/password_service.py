from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

class PasswordService:
  # hash password 
  def hash_password(self, password: str) -> str:
    return password_hash.hash(password)
  
  # verify password
  def verify_password(
      self,
      plain_password: str,
      hashed_password: str
  ) -> bool:
      return password_hash.verify(
          plain_password,
          hashed_password
      )
      
password_service = PasswordService()