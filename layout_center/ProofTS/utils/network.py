import json
import os
import re
import traceback
from typing import Optional, Dict, Any
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
import uuid

import wmi
from PySide6.QtCore import QObject, QUrl, QStandardPaths, QDir, QSettings
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

GLOB_CONFIG = QSettings("config.ini", QSettings.Format.IniFormat)

import urllib3


class ApiClient(QObject):
    DIANSAN_URL = "http://ys.diansan.com/app-web/router/rest.json?"

    # 创建全局连接池
    http_pool = urllib3.PoolManager(
        maxsize=10,  # 连接池最大连接数
        retries=urllib3.Retry(3),  # 自动重试3次
        timeout=urllib3.Timeout(connect=5.0, read=10.0),  # 连接超时5秒，读取超时10秒
    )

    def __init__(self, base_url: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.shopNames = []
        self.base_url = base_url.rstrip("/")  # 确保没有末尾斜杠
        self.network_manager = QNetworkAccessManager(self)
        self.cache_dir = os.path.join(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.CacheLocation
            ),
            "image_cache",
        )
        QDir().mkpath(self.cache_dir)
        self.login_mine()

    def login_mine(self):
        try:
            mac = uuid.UUID(int=uuid.getnode()).hex[-12:].upper()
            for board in wmi.WMI().Win32_BaseBoard():
                if board.SerialNumber:
                    mac += board.SerialNumber
                    break
            self.current_mac_address = str(mac)
            resp = self.urllib_get(
                f"permission-api/loginQyMac",
                params={"mac": self.current_mac_address},
            )
            print("loginQyMac: ", resp)
            if resp.get("code") == 200:
                self.token = resp.get("token", "")
            else:
                GLOB_CONFIG.setValue("auth/mac", mac)
        except Exception as e:
            traceback.print_exc()
        pass

    @property
    def token(self) -> Optional[str]:
        """从缓存中获取 Token"""
        return GLOB_CONFIG.value("auth/token")

    @token.setter
    def token(self, value: str):
        """设置并缓存 Token"""
        GLOB_CONFIG.setValue("auth/token", value)

    def clear_token(self):
        """清除 Token"""
        GLOB_CONFIG.remove("auth/token")

    def get_cached_path(self, url):
        return os.path.join(self.cache_dir, str(hash(url)))

    def get_image(self, url, resp):
        cached_path = self.get_cached_path(url)
        if os.path.exists(cached_path):
            resp(cached_path)
        else:
            request = QNetworkRequest(QUrl(url))
            reply = self.network_manager.get(request)

            def handle_reply():
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    data = reply.readAll()
                    with open(cached_path, "wb") as f:
                        f.write(data.data())
                    resp(cached_path)
                else:
                    print("图片请求错误：", reply.errorString())
                reply.deleteLater()

            reply.finished.connect(handle_reply)

    def _create_request(self, endpoint: str) -> QNetworkRequest:
        """创建带有 Token 的请求头"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )
        request.setRawHeader(b"Authorization", f"Bearer {self.token}".encode())
        return request

    def safe_json_parse(self, response_data):
        # 尝试直接解析
        try:
            return json.loads(response_data)
        except json.JSONDecodeError as e:
            # 如果是引号问题，尝试修复
            if "Expecting ',' delimiter" in str(e):
                # 查找所有字段

                fields = re.findall(r'"([^"]+)":("[^"]+"|[^"]+,)', response_data)
                if fields:
                    print(fields)
                    kv = [
                        f'''"{k}":"{v.replace('"', '').replace(',', '')}"'''
                        for k, v in fields
                    ]
                    fixed = "{" + ",".join(kv) + "}"
                    return json.loads(fixed)
            raise  # 重新抛出其他错误

    def _handle_response(self, reply, resp):
        """统一处理响应"""
        # reply: QNetworkReply = self.sender()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            response_data = reply.readAll().data().decode("utf-8")
            resp(self.safe_json_parse(response_data))
        else:
            error_msg = reply.errorString()
            resp({"code": 500, "msg": error_msg})
        reply.deleteLater()

    def get(self, endpoint: str, resp, params: Optional[Dict[str, Any]] = None):
        """发送 GET 请求"""
        request = self._create_request(endpoint)
        if params:
            url = request.url().toString() + "?" + urlencode(params)
            request.setUrl(url)
        print(request.url().toString())
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._handle_response(reply, resp))

    def post(self, endpoint: str, resp, data: Optional[Dict[str, Any]] = None):
        """发送 POST 请求"""
        request = self._create_request(endpoint)
        payload = json.dumps(data).encode() if data else b""
        reply = self.network_manager.post(request, payload)
        reply.finished.connect(lambda: self._handle_response(reply, resp))

    def urllib_get(
        self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15
    ) -> Dict[str, Any]:
        """同步阻塞的 GET（基于 urllib），在非 GUI 线程安全使用，返回解析后的 JSON dict。
        若请求或解析失败会抛出 Exception。
        """
        # 构建 URL
        if not url.lower().startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        if params:
            url = url + "?" + urlencode(params)

        headers = {"Content-Type": "application/json"}
        token = GLOB_CONFIG.value("auth/token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as e:
            raise Exception(f"HTTPError: {e.code} {e.reason}")
        except URLError as e:
            raise Exception(f"URLError: {e.reason}")
        except Exception as e:
            raise

        # 使用已有的 safe_json_parse 做解析与简单修复
        return self.safe_json_parse(body)

    def urllib_post(
        self, url: str, data: Optional[Dict[str, Any]] = None, timeout: int = 15
    ) -> Dict[str, Any]:
        """同步阻塞的 POST（基于 urllib），在非 GUI 线程安全使用，发送 JSON body 并返回解析后的 JSON dict。
        若请求或解析失败会抛出 Exception。
        """
        # 构建 URL
        if not url.lower().startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        headers = {"Content-Type": "application/json"}
        token = GLOB_CONFIG.value("auth/token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body_bytes = json.dumps(data).encode("utf-8") if data is not None else b""

        req = Request(url, data=body_bytes, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as e:
            raise Exception(f"HTTPError: {e.code} {e.reason}")
        except URLError as e:
            raise Exception(f"URLError: {e.reason}")
        except Exception:
            raise

        # 使用已有的 safe_json_parse 做解析与简单修复
        return self.safe_json_parse(body)

    def d3_post(self, url, data, isT3=False, rpt=0):
        try:
            headers = {
                "Cookie": f'token={GLOB_CONFIG.value("auth/qiyinbz_token" if isT3 else "auth/juheyou_token", "")}',
                "Content-Type": "application/json",
            }

            # 使用全局连接池发送请求
            response = self.http_pool.request(
                "POST",
                self.DIANSAN_URL + url,
                headers=headers,
                body=json.dumps(data).encode("utf-8"),
            )

            # 解析响应
            resp = json.loads(response.data.decode("utf-8"))
            if "code" in resp and resp["code"] == 403 and rpt < 3:
                self.login(isT3)
                return self.d3_post(url, data, isT3, rpt + 1)
            return resp
        except Exception as e:
            traceback.print_exc()
            print(f"请求URL: {self.DIANSAN_URL + url}:{e}")
            return {"code": 500, "msg": f"网络请求失败: {str(e)}"}

    def login(self, isT3=False):
        try:
            url = f"{self.DIANSAN_URL}method=auth.user.login&mac=00:00:00:00:00:00"
            tenantName = "起印包装" if isT3 else "聚和优"
            userName = (
                GLOB_CONFIG.value("auth/qiyinbz_username")
                if isT3
                else GLOB_CONFIG.value("auth/juheyou_username")
            )
            userPass = (
                GLOB_CONFIG.value("auth/qiyinbz_user_password")
                if isT3
                else GLOB_CONFIG.value("auth/juheyou_user_password")
            )
            authHost = (
                f"{url}&tenantName={tenantName}&userName={userName}&userPass={userPass}"
            )
            # 使用全局连接池发送请求
            response = self.http_pool.request("GET", authHost)
            # 解析响应
            resp = json.loads(response.data.decode("utf-8"))
            print("login: ", authHost, str(resp))
            GLOB_CONFIG.setValue(
                "auth/qiyinbz_token" if isT3 else "auth/juheyou_token",
                (
                    resp["data"]["token"]
                    if ("data" in resp and "token" in resp["data"])
                    else ""
                ),
            )
        except Exception as e:
            print("login error", e)
            GLOB_CONFIG.setValue(
                "auth/qiyinbz_token" if isT3 else "auth/juheyou_token", ""
            )
