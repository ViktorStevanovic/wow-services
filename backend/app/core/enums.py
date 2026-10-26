from enum import StrEnum


class Region(StrEnum):
    """Battle.net regions. Character names and the API are scoped per region."""

    US = "us"
    EU = "eu"
    KR = "kr"
    TW = "tw"


class Ruleset(StrEnum):
    """Forever has no realms: each ruleset is one large realm per region (spec §4)."""

    NORMAL = "normal"
    PVP = "pvp"
    RP = "rp"
    HARDCORE = "hardcore"


class Faction(StrEnum):
    """Always read from character data, never inferred from race (Skyborne can be either)."""

    ALLIANCE = "alliance"
    HORDE = "horde"


class CharacterClass(StrEnum):
    WARRIOR = "warrior"
    PALADIN = "paladin"
    HUNTER = "hunter"
    ROGUE = "rogue"
    PRIEST = "priest"
    SHAMAN = "shaman"
    MAGE = "mage"
    WARLOCK = "warlock"
    DRUID = "druid"
