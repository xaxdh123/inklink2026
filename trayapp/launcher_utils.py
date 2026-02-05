import sys
import subprocess
import psutil
from pathlib import Path
from typing import Any, Optional

# Windows 特有库
try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None


def launch_process(
    path: str,
    args: list[Any] = None,
    cwd: Optional[str] = None,
    detach: bool = True,
):
    args = args or []
    exe_path = Path(path).absolute()
    if not exe_path.exists():
        raise FileNotFoundError(f"文件不存在: {exe_path}")

    # 转换工作目录
    if cwd:
        cwd_path = Path(cwd).absolute()
        if not cwd_path.exists():
            cwd_path = None
    else:
        cwd_path = None

    # 1️⃣ 检查是否已启动
    existing_pid = None
    for proc in psutil.process_iter(["pid", "exe", "cmdline"]):
        try:
            # 匹配 exe 路径
            if proc.info["exe"] and Path(proc.info["exe"]).absolute() == exe_path:
                existing_pid = proc.info["pid"]
                break
            # 匹配 Python 脚本
            if exe_path.suffix.lower() == ".py" and proc.info["cmdline"]:
                if any(str(exe_path) in arg for arg in proc.info["cmdline"]):
                    existing_pid = proc.info["pid"]
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
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

    # 3️⃣ 构造命令
    if exe_path.suffix.lower() == ".py":
        cmd = [sys.executable, str(exe_path)] + args
    else:
        cmd = [str(exe_path)] + args

    print("启动命令:", cmd)
    print("工作目录:", cwd_path)

    # 4️⃣ 启动新进程
    try:
        if detach:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )

            subprocess.Popen(
                cmd,
                cwd=str(cwd_path) if cwd_path else None,
                close_fds=True,
                creationflags=creation_flags,
            )
        else:
            subprocess.call(cmd, cwd=str(cwd_path) if cwd_path else None)
    except FileNotFoundError:
        raise
    except Exception as e:
        raise RuntimeError(f"启动失败: {e}")
