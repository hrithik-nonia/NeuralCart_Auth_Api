import secrets
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

class OtpAndEmailService:
  # create otp
  def otp(self):
    return f"{secrets.randbelow(900000) + 100000}"
  
  # send email
  async def send_otp_email(self, email: str, otp: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": os.getenv("BREVO_API_KEY"),
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json={
                "sender": {
                    "name": "NeuralCart",
                    "email": os.getenv("BREVO_SENDER_EMAIL"),
                },
                "to": [{"email": email}],
                "subject": "Your NeuralCart OTP",
                "textContent": f"Your OTP is {otp}. It expires in 5 minutes.",
            },
        )

        response.raise_for_status()
  
otp_and_email_service = OtpAndEmailService()