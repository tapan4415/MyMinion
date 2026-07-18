async def summarize(text: str, *, max_characters: int = 400) -> str:
    normalized = " ".join(text.split())
    return (
        normalized
        if len(normalized) <= max_characters
        else f"{normalized[: max_characters - 1].rstrip()}…"
    )
