"""
WebChannel 桥接对象
用于在 JavaScript 和 Python 之间进行双向通信
参考 Qt WebChannel 标准用法
"""

import json
import traceback
from typing import Callable, Dict
from PySide6 import QtCore
import debugpy


class WebChannelBridge(QtCore.QObject):
    """WebChannel 桥接对象

    用于在 JavaScript 和 Python 之间通信
    JavaScript 可以通过这个对象调用 Python 方法和信号
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handlers: Dict[str, Callable] = {}

    @QtCore.Slot(str)
    def on_web_button_clicked(self, data: str):
        try:
            debugpy.debug_this_thread()
        except Exception:
            # 非调试状态下忽略
            pass
        """JavaScript 调用：按钮点击事件

        Args:
            data: JSON 字符串或普通字符串
        """
        try:
            _j_data = json.loads(data)
            method = _j_data["event"]
            params = _j_data["data"]
            self.call(method, params)
        except:
            traceback.print_exc()

    @QtCore.Slot(str, result=str)
    def call(self, method: str, arg) -> str:
        try:
            debugpy.debug_this_thread()
        except Exception:
            # 非调试状态下忽略
            pass
        """JavaScript 调用 Python 方法

        Args:
            method: 方法名称
            *args: 方法参数（JSON 字符串）

        Returns:
            返回值的 JSON 字符串
        """
        try:
            # 调用处理器
            if method in self._handlers:
                handler = self._handlers[method]
                result = handler(arg)

                # 返回 JSON 字符串
                try:
                    return json.dumps(result) if result is not None else json.dumps({})
                except:
                    return str(result) if result is not None else "{}"
            else:
                print(f"警告：未找到方法处理器 '{method}'")
                return json.dumps({"error": f"Method '{method}' not found"})
        except Exception as e:
            print(f"调用方法 '{method}' 时出错：{e}")
            import traceback

            traceback.print_exc()
            import json

            return json.dumps({"error": str(e)})

    def register_handler(self, method: str, handler: Callable):
        """注册方法处理器

        Args:
            method: 方法名称（JavaScript 中调用的名称）
            handler: Python 函数或方法
        """
        self._handlers[method] = handler

    def unregister_handler(self, method: str):
        """取消注册方法处理器"""
        if method in self._handlers:
            del self._handlers[method]
