import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database import engine, Base
from app.routers import devices, readings, system, ingest, mobile, users, profiles_wallets, auth
try:
    from app.routers import coverage_requests
except ImportError:
    coverage_requests = None

load_dotenv()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Network Monitor API",
    description="API for collecting and retrieving network signal data",
    version="2.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router)
app.include_router(readings.router)
app.include_router(system.router)
app.include_router(ingest.router)
app.include_router(mobile.router)
app.include_router(users.router)
if coverage_requests is not None:
    app.include_router(coverage_requests.router)
app.include_router(auth.router)
app.include_router(profiles_wallets.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)