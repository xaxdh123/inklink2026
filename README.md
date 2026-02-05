# Inklink 主程序与子程序

## 概述
本项目包含 1 个主程序与 7 个子程序。主程序负责登录、托盘与悬浮窗入口，子程序按模块独立打包运行。

## 运行（开发）
1. 创建虚拟环境并安装依赖：

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2. 运行主程序：

```powershell
python main.py
```

## 模块列表
| 模块 | 子目录（sub_dir） | 可执行文件 | 入口脚本/说明 |
| --- | --- | --- | --- |
| 主程序 | `main` | `main.exe` | `main.py`（启动 `trayapp.TrayApp`） |
| 浮窗插件 | `floating_plugin` | `floating_plugin.exe` | `floating_plugin.py` |
| 客服中心 | `customer_service` | `customer_service.exe` | `customer_service.py` |
| 设计中心 | `design_center` | `design_center.exe` | `design_center/README.md` |
| 三方工具 | `third_party` | `third_party.exe` | `third_party/README.md` |
| 排版中心 | `layout_center` | `layout_center.exe` | `layout_center/README.md` |
| 审核中心 | `audit_center` | `audit_center.exe` | `audit_center/README.md` |
| 系统设置 | `system_setting` | `system_setting.exe` | 代码在 `system_setting/`（目录名与配置不一致） |

## 打包/运行路径
- 打包输出目录：`./bin`
- 子程序运行路径：`./bin/<sub_dir>/<exe>`

## 补丁包路径
- 补丁目录：`./new_version/<sub_dir>/`
- 版本清单：`ver-info.json`（从 COS 下载到本地）

## 地址列表
### COS 配置（来源：`trayapp/constant.py`）
- Region：`ap-shanghai`
- Bucket：`inklink-1324665643`
- 主清单：`ver-info.json`
- 升级脚本：`upgradle.bat`

### 远端服务 URL（来源：`trayapp/constant.py`）
- 登录：`https://private.qiyinbz.com:31415/permission-api/loginQyMac`
- 系统设置-用户：`https://admin.qiyinbz.com/permission/user/profile`
- 系统设置-消息：`https://admin.qiyinbz.com/permission/index`
- 浮窗报价：`https://admin.qiyinbz.com/quotate-page/quotate-pageIndex`


