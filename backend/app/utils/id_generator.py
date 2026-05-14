import uuid

def make_id(prefix: str) -> str:
    """
    Generates a prefixed UUID string.
    Example: make_id("usr") → "usr_a3f1c2d4-9b8e-4f7a-b1c2-d3e4f5a6b7c8"
    """
    return f"{prefix}_{uuid.uuid4()}"