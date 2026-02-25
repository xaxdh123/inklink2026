import sys
import subprocess
import traceback
import psutil
from pathlib import Path
from typing import Any, Optional

from trayapp import constant

# Windows 特有库
try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None


def launch_process(
    item: dict[str, Any],
    args: list[Any] = None,
    detach: bool = True,
):
    
    # 1️⃣ 检查是否已启动
    existing_pid = None
    for proc in psutil.process_iter(["pid", "exe", "cmdline"]):
        try:
            # 匹配 exe 路径
            if proc.info["exe"] and item["exe"] in proc.info["exe"]:
                existing_pid = proc.info["pid"]
                break
            # 匹配 Python 脚本
            if proc.info["cmdline"] and  any(item["exe"]  in arg for arg in proc.info["cmdline"]):
                existing_pid = proc.info["pid"]
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            traceback.print_exc()
            continue

    # 2️⃣ 如果已启动，尝试激活窗口
    if existing_pid and win32gui:
        def callback(hwnd, target_pid):
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == target_pid:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    return False
            return True

        try:
            win32gui.EnumWindows(callback, existing_pid)
            print(f"检测到已运行 (PID: {existing_pid})，已尝试激活窗口。")
            return
        except Exception:
            print("已运行但窗口激活失败。")
            return
    elif existing_pid:
        print("已在运行，但缺少 pywin32，无法激活窗口。")
        return
    
    # 启动子包
    app_dir = Path(__file__).parent.parent
    exe_path = app_dir/ constant.DIR_BIN / item["sub_dir"] / item["exe"]
    try:
        args = args or []
        if exe_path.exists():
            cmd = [str(exe_path),item['key']] + args
        else:
            exe_path = app_dir.parent.parent / constant.DIR_BIN / item["sub_dir"] / item["exe"]
            if exe_path.exists():
                cmd = [str(exe_path),item['key']] + args
            else:
                exe_path = app_dir / "sub_module.py"
                if not exe_path.exists():
                    raise FileNotFoundError(f"无法找到可执行文件：{item['exe']} 或 sub_module.py")
                cmd = [sys.executable, str(exe_path),item['key']] + args
        if detach:
            # 4️⃣ 启动新进程
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )

            subprocess.Popen(
                cmd,
                close_fds=True,
                creationflags=creation_flags
            )
            print(f"已启动: {' '.join(cmd)}")
        else:
            subprocess.call(cmd)
    except FileNotFoundError:
        raise
    except Exception as e:
        raise RuntimeError(f"启动失败: {e}")
