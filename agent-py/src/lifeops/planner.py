from __future__ import annotations

from abc import ABC, abstractmethod

from lifeops.journeys import TEMPLATES, JourneyTemplate
from lifeops.models import Journey, JourneyTask


class Planner(ABC):
    @abstractmethod
    async def create_journey(self, goal: str) -> Journey: ...


class RuleBasedPlanner(Planner):
    """Offline planner used in development and as a safe model fallback."""

    def classify(self, goal: str) -> JourneyTemplate | None:
        normalized = goal.lower()
        return next(
            (
                template
                for template in TEMPLATES
                if any(trigger in normalized for trigger in template.triggers)
            ),
            None,
        )

    async def create_journey(self, goal: str) -> Journey:
        template = self.classify(goal)
        tasks = (
            template.instantiate_tasks()
            if template
            else [
                JourneyTask(
                    title="Clarify the outcome",
                    description="Define success, constraints, timing, and budget.",
                ),
                JourneyTask(
                    title="Research the landscape",
                    description="Gather current evidence and viable options.",
                ),
                JourneyTask(
                    title="Choose the next step",
                    description="Compare options and make concrete progress.",
                ),
            ]
        )
        dependencies = {tasks[index].id: [tasks[index - 1].id] for index in range(1, len(tasks))}
        return Journey(
            goal=goal,
            kind=template.kind if template else "general",
            tasks=tasks,
            dependencies=dependencies,
            missing_information=list(template.missing_information)
            if template
            else ["desired outcome", "constraints", "timing"],
            next_action=tasks[0].title,
        )
