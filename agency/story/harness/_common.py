"""Shared atoms for the story-team harness."""

import re


ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


TRIGGER_TARGET_KIND = {
    "character_death": "character",
    "character_defeat": "character",
    "location_enter": "location",
    "item_obtained": "item",
    "item_use": "item",
    "social_check": "character",
}


class EntityWriterError(Exception):
    """Raised on semantic-validation failures or on-disk conflicts."""
