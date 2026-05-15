from typing import Literal


HpState = Literal["healthy", "hurt", "critical"]
MpState = Literal["ready", "strained", "drained"]


def hp_state(current: int, maximum: int) -> HpState:
    if maximum <= 0:
        return "healthy"
    if current <= 0:
        return "critical"
    ratio = current / maximum
    if ratio <= 0.25:
        return "critical"
    if ratio <= 0.65:
        return "hurt"
    return "healthy"


def mp_state(current: int, maximum: int) -> MpState | None:
    if maximum <= 0:
        return None
    if current <= 0:
        return "drained"
    ratio = current / maximum
    if ratio <= 0.20:
        return "drained"
    if ratio <= 0.50:
        return "strained"
    return "ready"
