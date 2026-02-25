# --- 配置常量 ---
# 对应你的目录结构
import os


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
COMPONENT_MAP: list[dict[str, str | list[str]]] = [
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
        "key": "SystemSetting",
        "sub_dir": "system_setting",
        "exe": "system_setting.exe",
        "show_type": ["tray"],
    },
]

THIRD_PARTY_URL = "https://private.qiyinbz.com:31415/foundation-api/global/getConfig"
API_LOGIN_URL = "https://private.qiyinbz.com:31415/permission-api/loginQyMac"
SETTING_USER_URL = "https://admin.qiyinbz.com/permission/user/profile"
SETTING_MSG_URL = "https://admin.qiyinbz.com/permission/index"
FLOAT_QUO_URL = "https://admin.qiyinbz.com/quotate-page/quotate-pageIndex"
DESIGN_CENTER_URL = "https://admin.qiyinbz.com/erp/design/designSheetList"
TEMP_AI_PATH = os.path.abspath("resources/template.ai")
TEMP_CDR_PATH = os.path.abspath("resources/template.cdr")
JS_MERGE_PATH = os.path.abspath("resources/megre_aicanvas.jsx")
MERGE_DESIGN_SCRIPT = """
            var srcPath = "%SRC%";
            var cols = %COLS%;
            var rows = %ROWS%;
            var margin = %MARGIN%;
            var keepOriginalAtTopLeft = true;
            var names = %NAMES%; // 来自 Python 的名称列表

            function main() {
                var f = new File(srcPath);
                if (!f.exists) {
                    alert("源文件不存在: " + srcPath);
                    return;
                }
                app.open(f);
                var doc = app.activeDocument;
                doc.documentColorSpace = DocumentColorSpace.CMYK
                if (doc.artboards.length < 1) {
                    alert("文档中没有画板。");
                    doc.close(SaveOptions.DONOTSAVECHANGES);
                    return;
                }

                var refArt = doc.artboards[0];
                var rect = refArt.artboardRect;
                var width = rect[2] - rect[0];
                var height = rect[1] - rect[3];
                var startLeft = rect[0];
                var startTop = rect[1];

                var created = 0;
                var totalBefore = doc.artboards.length;
                var nameIndex = 0;

                for (var r = 0; r < rows; r++) {
                    for (var c = 0; c < cols; c++) {
                        if (keepOriginalAtTopLeft && r === 0 && c === 0) {
                            // 改名第一个原始画板
                            if (nameIndex < names.length) {
                                doc.artboards[0].name = names[nameIndex++];
                            }
                            continue;
                        }
                        var left = startLeft + c * (width + margin);
                        var top = startTop - r * (height + margin);
                        var newRect = [left, top, left + width, top - height];
                        var newArtboard = doc.artboards.add(newRect);
                        if (nameIndex < names.length) {
                            newArtboard.name = names[nameIndex++];
                        } else {
                            newArtboard.name = "Artboard_" + (totalBefore + created + 1);
                        }
                        created++;
                    }
                }

                try { doc.save(); } catch(e) { $.writeln("保存出错：" + e); }
                //alert("完成：新增 " + created + " 个画板。总数：" + doc.artboards.length);
            }
            main();
            """
