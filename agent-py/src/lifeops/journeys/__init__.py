from lifeops.journeys.base import JourneyTemplate
from lifeops.journeys.insurance import INSURANCE
from lifeops.journeys.job_search import JOB_SEARCH
from lifeops.journeys.moving import MOVING
from lifeops.journeys.shopping import SHOPPING
from lifeops.journeys.travel import TRAVEL

TEMPLATES: tuple[JourneyTemplate, ...] = (MOVING, SHOPPING, TRAVEL, INSURANCE, JOB_SEARCH)

__all__ = ["TEMPLATES", "JourneyTemplate"]
