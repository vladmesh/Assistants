import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.settings import Settings
from src.api.routes import router
from src.services.rest_service import RestService

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger().bind(service="calendar")

# Create settings instance
settings = Settings()

# Create FastAPI app
app = FastAPI(
    title="Google Calendar Service",
    description="Service for working with Google Calendar",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create REST service client
rest_service = RestService(settings)
app.state.rest_service = rest_service

# Include router
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Log startup event"""
    logger.info("Starting Google Calendar service")

@app.on_event("shutdown")
async def shutdown_event():
    """Close REST service client"""
    await rest_service.close()
    logger.info("Shutting down Google Calendar service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 