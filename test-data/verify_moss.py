"""Directly verify Moss extraction — the biggest worry.

Runs the same MemoryManager.retrieve() the Companion uses, for a set of queries,
and prints what comes back. Run from the repo root:
    $env:PYTHONPATH="agent-py/src"; agent-py/.venv/Scripts/python test-data/verify_moss.py
"""

import asyncio

from lifeops.dependencies import get_moss
from lifeops.memory import MemoryManager

USER_ID = "demo-user"

QUERIES = [
    "where do I live and what is my job",
    "what am I building",
    "NewsFlow news aggregator",
    "3D printer purchase budget",
    "3D printing parametric textiles",
    "noise cancelling headphones budget",
    "FIFA match tomorrow Sunnyvale",
    "Formula 1 racing",
    "board games score logging",
    "photography cameras lenses",
    "vegetarian food coffee",
    "travel luggage style",
    "Lake Tahoe glamping August plans",
    "May family trip New York Denver",
    "my wife architect",
    "my brother ophthalmology",
    "Varuni Microsoft",
    "Sarah Acme partnership",
]


async def main() -> None:
    memory = MemoryManager(get_moss())
    for query in QUERIES:
        records = await memory.retrieve(USER_ID, query, limit=4)
        print(f"\nQ: {query}  ->  {len(records)} hit(s)")
        for record in records:
            src = record.metadata.get("source")
            print(f"   [{record.kind.value}] {record.content}  ({record.created_at.date()}, src={src})")


asyncio.run(main())
