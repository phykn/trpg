from typing import Literal

from pydantic import BaseModel


class PlayerInput(BaseModel):
    name: str
    race_id: str
    gender: Literal["male", "female"]
