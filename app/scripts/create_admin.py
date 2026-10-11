import asyncio
import re
import getpass
from datetime import datetime, timezone
import sys
from app.database import users_collection, client
from app.utils.password_service import password_service



# ── Validators ──
def validate_email(email: str) -> bool:
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password kam se kam 8 characters ka hona chahiye"
    if not any(c.isupper() for c in password):
        return "Password mein ek uppercase letter hona chahiye"
    if not any(c.isdigit() for c in password):
        return "Password mein ek number hona chahiye"
    return None


async def create_admin():
    print("\n" + "="*40)
    print("   NeuralCart — Admin Create Script")
    print("="*40 + "\n")

    # ── Name ──
    while True:
        name = input("Enter admin name: ").strip()
        if not name:
            print("❌ Name empty nahi ho sakta\n")
            continue
        break

    # ── Email ──
    while True:
        email = input("Enter admin email: ").strip().lower()
        if not email:
            print("❌ Email empty nahi ho sakta\n")
            continue
        if not validate_email(email):
            print("❌ Valid email daalo\n")
            continue
        
        # DB mein check karo
        existing = await users_collection.find_one({"email": email})
        if existing:
            print(f"❌ '{email}' pehle se exist karta hai\n")
            continue
        break

    # ── Password ──
    while True:
        password = getpass.getpass("Enter admin password: ")
        error = validate_password(password)
        if error:
            print(f"❌ {error}\n")
            continue

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("❌ Passwords match nahi kar rahe\n")
            continue
        break

    # ── Password hash ──
    # Auth service ka same password_service use karo
    hashed = password_service.hash_password(password)

    # ── Insert ──
    admin = {
        "name": name,
        "email": email,
        "password": hashed,
        "role": "admin",
        "is_active": True,
        "google_id": None,
        "created_at": datetime.now(timezone.utc)
    }

    result = await users_collection.insert_one(admin)

    print(f"\n✅ Admin successfully created!")
    print(f"   ID:    {result.inserted_id}")
    print(f"   Name:  {name}")
    print(f"   Email: {email}")
    print(f"   Role:  admin\n")

    client.close()


if __name__ == "__main__":
    try:
        asyncio.run(create_admin())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled")
        sys.exit(0)