"""Web profile with persistent cache, storage, and performance optimizations."""
import os
from pathlib import Path
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

# Keep global reference to prevent premature deletion
_profiles = {}

def create_persistent_profile(
    profile_name: str = "default", cache_path: str = None
) -> QWebEngineProfile:
    """
    创建并配置 QWebEngineProfile，针对低配 Windows 平台进行性能优化。
    """
    if profile_name in _profiles:
        return _profiles[profile_name]

    if cache_path is None:
        appdata = os.getenv("APPDATA") or str(Path.home())
        cache_path = str(Path(appdata) / "InkLink" / "web_cache")

    cache_dir = Path(cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 创建持久化 Profile
    profile = QWebEngineProfile(profile_name)
    
    # 设置持久化路径
    cache_subdir = cache_dir / profile_name
    cache_subdir.mkdir(parents=True, exist_ok=True)
    profile.setPersistentStoragePath(str(cache_subdir / "storage"))
    profile.setCachePath(str(cache_subdir / "cache"))

    # --- 性能优化配置 ---
    
    # 1. 强制使用磁盘缓存并增大容量 (500MB)
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setHttpCacheMaximumSize(500 * 1024 * 1024) 

    # 2. 优化渲染设置
    settings = profile.settings()
    
    # 启用硬件加速特性
    settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
    
    # 启用本地存储与缓存
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    
    # 启用 DNS 预解析，加快网络连接
    settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, True)
    
    # 针对低配机器禁用平滑滚动，减少渲染开销
    settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)
    
    # 禁用不必要的插件
    settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)

    # 3. 资源预加载优化
    # 允许静默加载图标
    settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadIconsForPage, True)

    _profiles[profile_name] = profile
    return profile
