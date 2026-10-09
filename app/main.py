from fastapi import FastAPI
from app.routes.auth import router as auth_router
from contextlib import asynccontextmanager
from app.database import client, users_collection

# lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
  # MongoDB connect
  await client.admin.command("ping")
  print("✅ MongoDB connected")

  # Redis connect
  # await redis_client.ping()
  print("✅ Redis connected")

  # Index banao
  await users_collection.create_index("email", unique=True)

  yield

  # Cleanup
  client.close()
  # await redis_client.close()
  print("🔴 Connections closed")

# create app instance
app = FastAPI(title= "Auth API", lifespan=lifespan, description="Authentication service for NeuralCart", version="1.0.0", docs_url="/auth-apis")

# include auth router
app.include_router(auth_router)

# test route
@app.get("/health")
async def root():
    return {"message": "Auth Service Running"}