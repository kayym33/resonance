from ..cookbook_page import CookbookPage
from . import HubApp

APP = HubApp(
    name="cookbook",
    build=CookbookPage,
    order=50,
    description="recipes for one or two, with a cooking mode",
)
