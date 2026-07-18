"""Feed the dummy conversations through the real ScribeEnricher to populate Moss.

Simulates the live Scribe listening to `conversations.md`. Run from the repo root:
    $env:PYTHONPATH="agent-py/src"; agent-py/.venv/Scripts/python test-data/seed_scribe.py
"""

import asyncio
import re
import sys
from pathlib import Path

from lifeops.config import get_settings
from lifeops.dependencies import get_bright_data, get_moss
from lifeops.memory import MemoryManager
from lifeops.research import ResearchManager
from lifeops.scribe import ScribeEnricher

# Match the live Companion/Scribe user so voice recall finds these memories.
USER_ID = "demo-user"


def load_chunks(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    chunks: list[tuple[str, str]] = []
    for part in re.split(r"(?m)^### ", text):
        part = part.strip()
        if not part or part.startswith("#"):  # skip the file preamble
            continue
        title, _, body = part.partition("\n")
        body = body.strip()
        if body:
            chunks.append((title.strip(), body))
    return chunks


async def main() -> None:
    settings = get_settings()
    moss = get_moss()
    enricher = ScribeEnricher(
        MemoryManager(moss),
        ResearchManager(get_bright_data(), moss),
        moss=moss,
        user_id=USER_ID,
        openai_api_key=settings.openai_api_key,
        model=settings.scribe_model,
    )
    filename = sys.argv[1] if len(sys.argv) > 1 else "conversations.md"
    chunks = load_chunks(Path(__file__).with_name(filename))
    print(f"Source: {filename}")
    print(f"Seeding {len(chunks)} conversation chunks as user_id={USER_ID!r}\n")
    total_saved = total_research = 0
    for title, body in chunks:
        result = await enricher.enrich(body)
        total_saved += len(result.memories)
        total_research += len(result.research)
        print(f"### {title}  ->  saved {len(result.memories)}, researched {len(result.research)}")
        for memory in result.memories:
            print(f"    [{memory.kind.value}] {memory.content}")
    print(f"\nTOTAL: {total_saved} memories + {total_research} research docs written to Moss.")


asyncio.run(main())
