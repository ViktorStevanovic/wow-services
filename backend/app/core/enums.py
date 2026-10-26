from enum import StrEnum


class Region(StrEnum):
    """Battle.net regions. Character names and the API are scoped per region."""

    US = "us"
    EU = "eu"
    KR = "kr"
    TW = "tw"
