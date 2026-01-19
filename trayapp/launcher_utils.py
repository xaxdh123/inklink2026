import sys
import subprocess
import psutil
from pathlib import Path
from typing import Any, Optional

# 如果是 Windows，需要安装: pip install pywin32
try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None


def launch_process(
    path: str,
    args: list[Any] = [] ,
    cwd ='',
    detach: bool = True,
):
    args = args or []
    abs_path = str(Path(path).absolute())

    # 1. 检查进程是否已经启动
    existing_pid = None
    for proc in psutil.process_iter(["pid", "exe", "cmdline"]):
        try:
            # 匹配可执行文件路径
            if proc.info["exe"] and str(Path(proc.info["exe"]).absolute()) == abs_path:
                existing_pid = proc.info["pid"]
                break
            # 如果是 Python 脚本，匹配命令行参数
            if path.lower().endswith(".py") and proc.info["cmdline"]:
                if any(path in arg for arg in proc.info["cmdline"]):
                    existing_pid = proc.info["pid"]
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 2. 如果已启动，尝试激活窗口
    if existing_pid:
        if win32gui:

            def callback(hwnd, target_pid):
                if win32gui.IsWindowVisible(hwnd):
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == target_pid:
                        # 找到窗口，取消最小化并激活
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        return False  # 停止遍历
                return True

            try:
                win32gui.EnumWindows(callback, existing_pid)
                print(f"检测到已运行 (PID: {existing_pid})，已尝试激活窗口。")
                return  # 成功激活后退出
            except Exception:
                pass  # 有时 EnumWindows 会因为返回 False 抛出异常，忽略即可
        else:
            print("已在运行，但缺少 pywin32 库，无法激活窗口。")
            return

    # 3. 如果未启动，执行原有的启动逻辑
    if path.lower().endswith(".py"):
        cmd = [sys.executable, path] + args
    else:
        cmd = [path] + args

    try:
        if detach:
            # 使用 creationflags 确保 Windows 下完全分离
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )

            subprocess.Popen(cmd, cwd=cwd, close_fds=True, creationflags=creation_flags)
        else:
            subprocess.call(cmd, cwd=cwd)
    except Exception:
        raise
