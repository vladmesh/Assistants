from typing import Optional, Dict, Any, List
import aiohttp
import structlog
from config.settings import settings

logger = structlog.get_logger()

class RestClient:
    """Async client for REST API."""
    
    def __init__(self):
        self.base_url = settings.rest_service_url
        self.api_prefix = "/api"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to API."""
        if not self.session:
            raise RuntimeError("Session is not initialized. Use 'async with' context manager.")
            
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        logger.debug("Making request", url=url, method=method)
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error("Request error", url=url, method=method, error=str(e))
            raise
            
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram_id."""
        try:
            response = await self._make_request(
                "GET",
                "/users/",
                params={"telegram_id": telegram_id}
            )
            
            if not response:
                return None
                
            if isinstance(response, list):
                return response[0] if response else None
                
            return response
            
        except aiohttp.ClientError as e:
            logger.error("Error getting user", telegram_id=telegram_id, error=str(e))
            return None
            
    async def create_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Create new user."""
        return await self._make_request(
            "POST",
            "/users/",
            json={
                "telegram_id": telegram_id,
                "username": username
            }
        )
        
    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Get or create user."""
        try:
            # Try to find user
            user = await self.get_user(telegram_id)
            if user:
                logger.info("Found existing user", telegram_id=telegram_id)
                return user
                
            # Create new user if not found
            logger.info("Creating new user", telegram_id=telegram_id)
            return await self.create_user(telegram_id, username)
            
        except aiohttp.ClientError as e:
            logger.error("Error in get_or_create_user", telegram_id=telegram_id, error=str(e))
            # Return basic user info in case of error
            return {
                "id": telegram_id,
                "telegram_id": telegram_id,
                "username": username
            }
            
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by user_id."""
        try:
            return await self._make_request(
                "GET",
                f"/users/{user_id}"
            )
        except aiohttp.ClientError as e:
            logger.error("Error getting user by id", user_id=user_id, error=str(e))
            return None 