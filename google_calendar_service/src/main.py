from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config.logger import get_logger
from src.config.settings import Settings
from src.services.calendar import GoogleCalendarService
from src.services.redis_service import RedisService
from src.services.rest_service import RestService

# Get configured logger
logger = get_logger(__name__)

# Create settings instance
settings = Settings()

# Create FastAPI app
app = FastAPI(
    title="Google Calendar Service",
    description="Service for working with Google Calendar",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create services
rest_service = RestService(settings)
calendar_service = GoogleCalendarService(settings)
redis_service = RedisService(settings)

# Add services to app state
app.state.rest_service = rest_service
app.state.calendar_service = calendar_service
app.state.redis_service = redis_service

# Include API routes
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting Google Calendar service")


@app.on_event("shutdown")
async def shutdown_event():
    """Close service connections"""
    await rest_service.close()
    await redis_service.close()
    logger.info("Shutting down Google Calendar service")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
