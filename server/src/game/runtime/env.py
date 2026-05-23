import os


def env_float(name: str, default: float) -> float:
    return float(os.environ.get(name) or str(default))


def env_nonnegative_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default
