class ModifierValidationError(ValueError):
    """Raised when verb.modifiers fail _MODIFIER_SCHEMAS check.

    Caught by classify/runner.py retry loop for self-correction.
    """
