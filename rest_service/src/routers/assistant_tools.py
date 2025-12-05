from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.api_schemas import AssistantToolLinkCreate, ToolRead
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.assistant_tool as assistant_tool_crud
from database import get_session
from models.assistant import AssistantToolLink, Tool  # Keep Tool for response_model

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter()


@router.get("/assistants/{assistant_id}/tools", response_model=list[ToolRead])
async def list_assistant_tools_route(
    assistant_id: UUID, session: SessionDep
) -> list[Tool]:
    """Get all tools linked to a specific assistant."""
    logger.info("Listing tools for assistant", assistant_id=str(assistant_id))
    try:
        tools = await assistant_tool_crud.get_assistant_tools(
            db=session, assistant_id=assistant_id
        )
        logger.info(
            f"Found {len(tools)} tools for assistant", assistant_id=str(assistant_id)
        )
        return tools
    except ValueError as exc:
        logger.error(
            "Failed to list assistant tools: Assistant not found",
            assistant_id=str(assistant_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found"
        ) from exc
    except Exception as exc:
        logger.exception(
            "Failed to list assistant tools due to unexpected error",
            assistant_id=str(assistant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.post(
    "/assistants/{assistant_id}/tools/{tool_id}",
    response_model=AssistantToolLinkCreate,
    status_code=status.HTTP_201_CREATED,
)
async def add_tool_to_assistant_route(
    assistant_id: UUID, tool_id: UUID, session: SessionDep
) -> AssistantToolLink:
    """Link a tool to an assistant."""
    logger.info(
        "Attempting to link tool to assistant",
        assistant_id=str(assistant_id),
        tool_id=str(tool_id),
    )
    link_data = AssistantToolLinkCreate(assistant_id=assistant_id, tool_id=tool_id)
    try:
        link = await assistant_tool_crud.add_tool_to_assistant(
            db=session, link_in=link_data
        )
        logger.info(
            "Tool linked successfully",
            assistant_id=str(assistant_id),
            tool_id=str(tool_id),
        )
        return link  # Return the created link object (or just the IDs)
    except ValueError as exc:
        logger.error(
            "Failed to link tool: Invalid input",
            assistant_id=str(assistant_id),
            tool_id=str(tool_id),
            error=str(exc),
        )
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        elif "already linked" in detail:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        logger.exception(
            "Failed to link tool due to unexpected error",
            assistant_id=str(assistant_id),
            tool_id=str(tool_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.delete(
    "/assistants/{assistant_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_tool_from_assistant_route(
    assistant_id: UUID, tool_id: UUID, session: SessionDep
) -> None:
    """Unlink a tool from an assistant."""
    logger.info(
        "Attempting to unlink tool from assistant",
        assistant_id=str(assistant_id),
        tool_id=str(tool_id),
    )
    deleted = await assistant_tool_crud.remove_tool_from_assistant(
        db=session, assistant_id=assistant_id, tool_id=tool_id
    )
    if not deleted:
        logger.warning(
            "Link not found for deletion",
            assistant_id=str(assistant_id),
            tool_id=str(tool_id),
        )
        # It's common to return 404 if the link doesn't exist.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool link not found"
        )
    logger.info(
        "Tool unlinked successfully",
        assistant_id=str(assistant_id),
        tool_id=str(tool_id),
    )
    return None  # Return None for 204 No Content
