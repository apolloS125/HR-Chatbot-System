import os
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .admin import router as admin_router
from .auth import router as auth_router
from .chatbot import router as chatbot_router
from .liff import router as liff_router
from .core import cache, db, lifespan

app = FastAPI(title="HR Chatbot API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("LIFF_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(chatbot_router)
app.include_router(liff_router)
app.include_router(admin_router)

@app.get("/health")
async def health(database=Depends(db), redis=Depends(cache)):
    await database.command("ping")
    await redis.ping()
    return {"status": "ok"}
