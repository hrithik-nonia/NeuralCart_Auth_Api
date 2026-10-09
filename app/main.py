from fastapi import FastAPI

app = FastAPI(title= "Auth API", description="Authentication service for NeuralCart", version="1.0.0", docs_url="/auth-apis")

@app.get("/health")
async def root():
    return {"message": "Auth Service Running"}