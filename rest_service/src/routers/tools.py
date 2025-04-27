from typing import List
from uuid import UUID

import crud.tool as tool_crud
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models.assistant import Tool
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import ToolCreate, ToolRead, ToolUpdate

logger = structlog.get_logger()
router = APIRouter()


@router.get("/tools/", response_model=List[ToolRead])
async def list_tools_route(
    session: AsyncSession = Depends(get_session), skip: int = 0, limit: int = 100
) -> List[Tool]:
    """Get a list of all tools."""
    logger.info("Listing tools", skip=skip, limit=limit)
    tools = await tool_crud.get_tools(db=session, skip=skip, limit=limit)
    logger.info(f"Found {len(tools)} tools")
    return tools


@router.get("/tools/{tool_id}", response_model=ToolRead)
async def get_tool_route(
    tool_id: UUID, session: AsyncSession = Depends(get_session)
) -> Tool:
    """Get a specific tool by its ID."""
    logger.info("Getting tool by ID", tool_id=str(tool_id))
    tool = await tool_crud.get_tool(db=session, tool_id=tool_id)
    if not tool:
        logger.warning("Tool not found", tool_id=str(tool_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
        )
    logger.info("Tool found", tool_id=str(tool_id), name=tool.name)
    return tool


@router.post("/tools/", response_model=ToolRead, status_code=status.HTTP_201_CREATED)
async def create_tool_route(
    tool_in: ToolCreate, session: AsyncSession = Depends(get_session)
) -> Tool:
    """Create a new tool."""
    logger.info("Attempting to create tool", name=tool_in.name, type=tool_in.tool_type)
    try:
        tool = await tool_crud.create_tool(db=session, tool_in=tool_in)
        logger.info("Tool created successfully", tool_id=str(tool.id))
        return tool
    except ValueError as e:
        logger.error("Failed to create tool: Invalid input", error=str(e))
        # Check if it's a duplicate name error or enum error
        detail = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "already exists" in detail:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        logger.exception("Failed to create tool due to unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/tools/{tool_id}", response_model=ToolRead)
async def update_tool_route(
    tool_id: UUID, tool_update: ToolUpdate, session: AsyncSession = Depends(get_session)
) -> Tool:
    """Update an existing tool."""
    logger.info("Attempting to update tool", tool_id=str(tool_id))
    try:
        updated_tool = await tool_crud.update_tool(
            db=session, tool_id=tool_id, tool_in=tool_update
        )
        if not updated_tool:
            logger.warning("Tool not found for update", tool_id=str(tool_id))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
            )
        logger.info("Tool updated successfully", tool_id=str(updated_tool.id))
        return updated_tool
    except ValueError as e:
        logger.error(
            "Failed to update tool: Invalid input", tool_id=str(tool_id), error=str(e)
        )
        detail = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "already exists" in detail:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        logger.exception(
            "Failed to update tool due to unexpected error", tool_id=str(tool_id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool_route(
    tool_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Delete a tool."""
    logger.info("Attempting to delete tool", tool_id=str(tool_id))
    deleted = await tool_crud.delete_tool(db=session, tool_id=tool_id)
    if not deleted:
        logger.warning("Tool not found for deletion", tool_id=str(tool_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
        )
    logger.info("Tool deleted successfully", tool_id=str(tool_id))
    return None  # Return None for 204 No Content
