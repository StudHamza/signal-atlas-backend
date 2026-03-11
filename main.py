import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database import engine, Base
from app.routers import system, ingest, mobile

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Network Monitor API",
    description="API for collecting and retrieving network signal data",
    version="2.0.0",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(ingest.router)
app.include_router(mobile.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)