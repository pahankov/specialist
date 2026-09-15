from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
import asyncio

# Create tables on startup
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

# Import and include routers
from app.api import auth, masters, services, appointments, clients, working_hours

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(masters.router, prefix="/api/v1/masters", tags=["masters"])
app.include_router(services.router, prefix="/api/v1/services", tags=["services"])
app.include_router(working_hours.router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])