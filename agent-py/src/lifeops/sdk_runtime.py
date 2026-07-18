from __future__ import annotations

from typing import Any


class OpenAIMultiAgentRuntime:
    """Lazy OpenAI Agents SDK graph for production orchestration.

    Mock mode uses the deterministic LifeOpsAgent workflow. Production can select this
    runtime after registering the repository's independent tools as SDK function tools.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def build(self, tools_by_agent: dict[str, list[Any]]) -> Any:
        try:
            from agents import Agent
        except ImportError as error:
            raise RuntimeError("Install the 'openai' extra to enable the Agents SDK") from error

        buying = Agent(
            name="Buying Advisor",
            model=self._model,
            instructions=(
                "Research current options, enforce hard constraints, rank with evidence, "
                "persist useful preferences, and require approval before purchase."
            ),
            tools=tools_by_agent.get("buying", []),
        )
        contact = Agent(
            name="Contact Intelligence",
            model=self._model,
            instructions=(
                "Extract interaction facts and commitments, research consent-safe public "
                "context, preserve provenance, and recommend follow-up without sending it."
            ),
            tools=tools_by_agent.get("contact", []),
        )
        trip = Agent(
            name="Trip Planner",
            model=self._model,
            instructions=(
                "Research current travel facts, construct a feasible itinerary, remember "
                "preferences, refresh volatile facts, and require approval before booking."
            ),
            tools=tools_by_agent.get("trip", []),
        )
        return Agent(
            name="MyMinion Supervisor",
            model=self._model,
            instructions=(
                "Retrieve relevant memory, identify the user's outcome, hand off to exactly "
                "one specialist, and return typed progress with a concrete next action."
            ),
            tools=tools_by_agent.get("supervisor", []),
            handoffs=[buying, contact, trip],
        )

    async def run(self, supervisor: Any, message: str) -> str:
        try:
            from agents import Runner
        except ImportError as error:
            raise RuntimeError("Install the 'openai' extra to enable the Agents SDK") from error
        result = await Runner.run(supervisor, message)
        return str(result.final_output)
