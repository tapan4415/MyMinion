from lifeops.memory import MemoryManager
from lifeops.models import MemoryRecord


async def retrieve_memory(user_id: str, query: str, manager: MemoryManager) -> list[MemoryRecord]:
    return await manager.retrieve(user_id, query)
