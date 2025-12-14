from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared_models import LogEventType, configure_logging, get_logger

from api.routes import router
from config.settings import Settings
from services.calendar import GoogleCalendarService
from services.redis_service import RedisService
from services.rest_service import RestService

# Create settings instance
settings = Settings()

# Configure logging
configure_logging(
    service_name="google_calendar_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)

# Create services (can be created outside lifespan if they don't need
# startup/shutdown logic intrinsically)
rest_service = RestService(settings)
calendar_service = GoogleCalendarService(settings)
redis_service = RedisService(settings)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Google Calendar service", event_type=LogEventType.STARTUP)
    app.state.rest_service = rest_service
    app.state.calendar_service = calendar_service
    app.state.redis_service = redis_service
    yield
    logger.info(
        "Shutting down Google Calendar service", event_type=LogEventType.SHUTDOWN
    )
    await rest_service.close()
    await redis_service.close()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Google Calendar Service",
    description="Service for working with Google Calendar",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
