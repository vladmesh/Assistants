import asyncio
from database import AsyncSessionLocal
from models import Tool
from sqlmodel import select


async def main():
    session = AsyncSessionLocal()
    print("Tools in database:")
    tools = await session.exec(select(Tool))
    for tool in tools:
        print(f"- {tool.name} ({tool.tool_type})")
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
