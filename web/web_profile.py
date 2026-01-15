"""Web profile with persistent cache, storage, and form data recovery."""

from pathlib import Path
from PySide6.QtWebEngineCore import QWebEngineProfile

# Keep global reference to prevent premature deletion
_profiles = {}


def create_persistent_profile(
    profile_name: str = "default", cache_path: str = None
) -> QWebEngineProfile:
    """Create a QWebEngineProfile with persistent cache, storage, and form data.

    Args:
        profile_name: name for the profile
        cache_path: optional custom cache directory; if None, uses %APPDATA%/InkLink/cache

    Returns:
        Configured QWebEngineProfile (held in global registry to prevent deletion)

    Note:
        Form data, local storage, session storage, and DOM data are persisted automatically
        through QWebEngineProfile's storage mechanisms.
    """
    # Return cached profile if already created
    if profile_name in _profiles:
        return _profiles[profile_name]

    if cache_path is None:
        import os

        appdata = os.getenv("APPDATA") or str(Path.home())
        cache_path = str(Path(appdata) / "InkLink" / "web_cache")

    # Create cache directory
    cache_dir = Path(cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create or get default profile
    profile = QWebEngineProfile(profile_name)

    # Set cache paths for persistent storage
    cache_subdir = cache_dir / profile_name
    cache_subdir.mkdir(parents=True, exist_ok=True)

    profile.setCachePath(str(cache_subdir / "cache"))
    profile.setPersistentStoragePath(str(cache_subdir / "storage"))

    # Configure cache settings for form data persistence
    settings = profile.settings()
    settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(settings.WebAttribute.LocalStorageEnabled, True)
    settings.setAttribute(settings.WebAttribute.PluginsEnabled, False)  # security
    settings.setAttribute(
        settings.WebAttribute.JavascriptCanOpenWindows, False  # security
    )

    # HTTP cache settings for static resources
    settings.setAttribute(settings.WebAttribute.AutoLoadIconsForPage, True)

    # Enable form suggestions (helps with form data recovery)
    settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, True)

    # DNS prefetch disabled for privacy
    settings.setAttribute(settings.WebAttribute.DnsPrefetchEnabled, False)

    # Store in global registry to prevent garbage collection
    _profiles[profile_name] = profile
    return profile
