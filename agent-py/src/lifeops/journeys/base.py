from dataclasses import dataclass

from lifeops.models import JourneyKind, JourneyTask


@dataclass(frozen=True)
class JourneyTemplate:
    kind: JourneyKind
    triggers: tuple[str, ...]
    tasks: tuple[tuple[str, str], ...]
    missing_information: tuple[str, ...]
    research_queries: tuple[str, ...]
    memory_hooks: tuple[str, ...]
    ui_card: str

    def instantiate_tasks(self) -> list[JourneyTask]:
        return [
            JourneyTask(title=title, description=description) for title, description in self.tasks
        ]
