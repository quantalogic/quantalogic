from quantalogic_codeact.version import get_version


async def version_command(shell, args) -> str:
    """Show quantalogic package version."""
    version = get_version()
    return version
