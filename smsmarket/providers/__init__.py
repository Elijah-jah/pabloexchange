from .instantnums import InstantNumsProvider


def get_provider():
    """Single global provider: InstantNums."""
    return InstantNumsProvider()