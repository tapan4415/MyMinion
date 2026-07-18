from typing import Any


async def compare(options: list[dict[str, Any]], weights: dict[str, float]) -> list[dict[str, Any]]:
    def score(option: dict[str, Any]) -> float:
        return sum(float(option.get(key, 0)) * weight for key, weight in weights.items())

    return sorted(
        ({**option, "score": score(option)} for option in options),
        key=lambda item: item["score"],
        reverse=True,
    )


async def rank_options(
    options: list[dict[str, Any]], weights: dict[str, float]
) -> list[dict[str, Any]]:
    return await compare(options, weights)
