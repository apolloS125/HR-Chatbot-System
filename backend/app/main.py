from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI

from .admin import router as admin_router
from .auth import router as auth_router
from .chatbot import router as chatbot_router
from .core import db, lifespan


app = FastAPI(title="HR Chatbot API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(chatbot_router)
app.include_router(admin_router)


@app.get("/health")
async def health(pool: Annotated[asyncpg.Pool, Depends(db)]):
    await pool.fetchval("SELECT 1")
    return {"status": "ok"}
