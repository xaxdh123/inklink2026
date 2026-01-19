import json
from typing import Callable
import sys
from PySide6 import QtCore, QtNetwork


class QNetworkHttpClient(QtCore.QObject):
    """
    基于 QNetworkAccessManager 的简单 GET 客户端：
    - 支持 timeout
    - 自动尝试 JSON 解析
    - 可选 ignore_ssl_errors（默认 False，不建议开启；除非你们内网是自签证书）
    """

    def __init__(self, token="", parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.token = token
        self._mgr = QtNetwork.QNetworkAccessManager(self)

    def get_json(
        self,
        url: str,
        timeout_ms: int = 8000,
        headers: dict[str, str] | None = None,
        ignore_ssl_errors: bool = True,
        done=None,
        **kwargs,
        # done: Callable[[bool, object, int | None], None]
    ) -> QtNetwork.QNetworkReply:
        if kwargs:
            url += "?" + "&".join(f"{k}={v}" for k, v in kwargs.items())
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        req.setHeader(
            QtNetwork.QNetworkRequest.KnownHeaders.UserAgentHeader, "InkLink/2026"
        )
        req.setRawHeader(
            "Authorization".encode("utf-8"),
            f"Bearer {self.token}".encode("utf-8"),
        )
       
        if headers:
            for k, v in headers.items():
                req.setRawHeader(k.encode("utf-8"), v.encode("utf-8"))
      
        reply = self._mgr.get(req)

        if ignore_ssl_errors:
            # 注意：忽略 SSL 错误有安全风险，仅建议内网自签证书临时使用
            reply.sslErrors.connect(lambda _errors: reply.ignoreSslErrors())

        timer = QtCore.QTimer(reply)
        timer.setSingleShot(True)

        def _on_timeout():
            reply.abort()

        timer.timeout.connect(_on_timeout)
        timer.start(timeout_ms)

        def _on_finished():
            timer.stop()

            status = reply.attribute(
                QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            status_code = int(status) if status is not None else None

            if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
                err = reply.errorString()
                if done:
                    done(None, err, status_code)
                reply.deleteLater()
                return
            if done:
                raw_data = reply.readAll().data() 
                text = raw_data.decode('utf-8', errors="replace")
                try:
                    data = json.loads(text)
                    status_code = data['code'] if 'code' in data else 500
                    if status_code ==200 :
                        done(True, data, status_code)
                    else:
                        done(False, data['msg'], status_code)
                except Exception:
                    done(None, text, status_code)
            reply.deleteLater()
        reply.finished.connect(_on_finished)
        return reply
