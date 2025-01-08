
import requests
from packaging import version

from quantalogic.version import get_version


def check_if_is_latest_version() -> (bool,str|None):
    """Check if the current version is the latest version on PyPI.
    
    Returns:
        bool: True if the current version is the latest, False otherwise
    """
    try:
        current_version = get_version()
        response = requests.get("https://pypi.org/pypi/quantalogic/json", timeout=5)
        response.raise_for_status()
        latest_version = response.json()["info"]["version"]
        has_new_version = version.parse(current_version) < version.parse(latest_version)
        return has_new_version, latest_version
    except (requests.RequestException, KeyError):
        return False, None


def main():
    """Test the version checking functionality."""
    is_latest, latest_version = check_if_is_latest_version()
    if is_latest:
        print("✅ You're running the latest version")
    elif latest_version:
        print(f"⚠️ Update available: {latest_version}")
    else:
        print("❌ Could not check version")

if __name__ == "__main__":
    main()


