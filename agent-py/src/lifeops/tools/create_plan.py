from lifeops.models import Journey
from lifeops.planner import Planner


async def generate_plan(goal: str, planner: Planner) -> Journey:
    return await planner.create_journey(goal)


create_plan = generate_plan
