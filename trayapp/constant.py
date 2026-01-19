# --- 配置常量 ---
# 对应你的目录结构
DIR_JAVASCRIPT = "./javascript"
# 对应你的目录结构
DIR_JAVASCRIPT_REMOTE = "报价脚本"
DIR_NEW_VERSION = "./new_version"
DIR_BIN = "./bin"
COS_SECRET_ID = "AKIDV5avFeG2mH0hmrpeo7a1uX7onuAe7du9"  # 用户的 SecretId，
COS_SECRET_KEY = "W9iAa7W6wkrBVo2AEXyV4oeWQKB9AEIM"  # 用户的 SecretKey，
COS_REGION = "ap-shanghai"  # 替换为用户的 region，已创建桶归属的 region
COS_BUCKET = "inklink-1324665643"
COS_MAIN_FILE = "ver-info.json"
COS_UPGRADLE = "upgradle.bat"
# 组件配置列表 (显示名称, QSettings中的键名, 对应的new_version子目录名, 对应的执行文件名)
# 注意：这里假设了一些英文键名和路径，你可以根据实际情况修改
COMPONENT_MAP: list[dict[str, str | list[str]]]= [
    {
        "name": "主程序",
        "key": "MainApp",
        "sub_dir": "main",
        "exe": "main.exe",
        "show_type": [],
    },
    {
        "name": "浮窗插件",
        "key": "FloatingPlugin",
        "sub_dir": "floating_plugin",
        "exe": "floating_plugin.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "客服中心",
        "key": "CustomerService",
        "sub_dir": "customer_service",
        "exe": "customer_service.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "设计中心",
        "key": "DesignCenter",
        "sub_dir": "design_center",
        "exe": "design_center.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "三方工具",
        "key": "ThirdParty",
        "sub_dir": "third_party",
        "exe": "third_party.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "排版中心",
        "key": "LayoutCenter",
        "sub_dir": "layout_center",
        "exe": "layout_center.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "审核中心",
        "key": "AuditCenter",
        "sub_dir": "audit_center",
        "exe": "audit_center.exe",
        "show_type": ["float", "tray"],
    },
    {
        "name": "系统设置",
        "key": "SystemSettings",
        "sub_dir": "system_settings",
        "exe": "system_settings.exe",
        "show_type": ["tray"],
    },
]

THIRD_PARTY_URL = "https://private.qiyinbz.com:31415/foundation-api/global/getConfig"
API_LOGIN_URL = "https://private.qiyinbz.com:31415/permission-api/loginQyMac"
SETTING_USER_URL = "https://admin.qiyinbz.com/permission/user/profile"
SETTING_MSG_URL = "https://admin.qiyinbz.com/permission/index"
FLOAT_QUO_URL = "https://admin.qiyinbz.com/quotate-page/quotate-pageIndex"