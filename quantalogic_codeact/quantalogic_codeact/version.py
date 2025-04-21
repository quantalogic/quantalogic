import importlib.metadata


def get_version() -> str:
    """Return the current package version."""
    try:
        # Use the project package name as defined in pyproject.toml
        return importlib.metadata.version("quantalogic-codeact")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
