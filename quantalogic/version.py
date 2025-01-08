import importlib.metadata


def get_version() -> str:
    return importlib.metadata.version("quantalogic")
