from ..habits_page import HabitsPage
from . import HubApp

APP = HubApp(
    name="habits",
    build=HabitsPage,
    order=35,
    description="daily habits and streaks",
)
