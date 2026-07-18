from lifeops.memory import MemoryManager
from lifeops.models import MemoryCandidate, MemoryRecord


async def save_memory(
    user_id: str, candidate: MemoryCandidate, manager: MemoryManager
) -> MemoryRecord | None:
    return await manager.save(user_id, candidate) if manager.should_store(candidate) else None
