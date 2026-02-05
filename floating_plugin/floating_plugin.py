import os
import json
from pathlib import Path
import time
from PySide6 import QtWidgets
from trayapp import constant
from web.get_module_urls import ModuleUrlsThreads
from web.web_browser_widget import BrowserWidget
from typing import Callable
from trayapp import cos_utils


class FloatingPlugin(BrowserWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        args = self.get_sys_args()
        self.token = args.get("user_name", None) or ""
        profile_name = "FloatingPlugin"
        self.presets: dict[str, str | Callable[[], QtWidgets.QWidget]] = {
            "报价器": constant.FLOAT_QUO_URL
        }
        super().__init__(self.presets, parent, profile_name, self.token)
        self.setWindowTitle("浮窗插件")
        self.last_request_time = 0
        self.register_js_handler("报价器", "quoteMethod", self.quoteMethod)
        if "jump_page" in args:
            self._switch_to_feature(args["jump_page"])
        self.work = ModuleUrlsThreads(profile_name)
        self.work.resp_name_urls.connect(self.add_more)
        self.work.start()

    def add_more(self, data):
        for k, v in data.items():
            self.add_feature(k, v)

    def parse_attr(self, attr):
        _res = {"name": attr["attr_name"], "value": attr["attr_value"]}
        _key = attr["attr_code"]
        label = []
        for _item in attr["select_item_list"]:
            if _item["attr_limit_develop_value"] in _res["value"].split(","):
                label.append(_item["attr_limit_display_value"])
            _res["label"] = ",".join(label)
        label = []
        for _sku in attr["select_sku_list"]:

            if _sku["origin_material_sku_code"] in _res["value"].split(","):
                label.append(_sku["material_sku_name"])
            _res["label"] = ",".join(label)
            _key = "材质"
        label = []
        for _attr in attr["select_attr_list"]:
            if _attr["attr_code"] in _res["value"].split(","):
                label.append(_attr["attr_name"])
                for k, v in self.parse_attr(_attr).items():
                    _res[k] = v
            _res["label"] = ",".join(label)
        label = []
        for _craft in attr["select_craft_list"]:
            _craft_key = _craft["effect_craft_code"]
            if _craft_key in _res["value"].split(","):
                label.append(_craft["effect_craft_name"])
                _attrs = _craft["required_attr"] + _craft["own_attr"]
                if len(_attrs):
                    _res[_craft_key] = {}
                    for _a in _attrs:
                        for k, v in self.parse_attr(_a).items():
                            _res[_craft_key][k] = v
            _res["label"] = ",".join(label)
            _key = "工艺"
        label = []
        for _prod in attr["select_product_list"]:
            _prod_key = _prod["prod_code"]
            if _prod_key in _res["value"].split(","):
                label.append(_prod["prod_name"])
                _attrs = _prod["own_attr"] + _prod["mate_attr"] + _prod["craft_attr"]
                if len(_attrs):
                    _res[_prod_key] = {}
                    for _a in _attrs:
                        for k, v in self.parse_attr(_a).items():
                            _res[_prod_key][k] = v
            _res["label"] = ",".join(label)
            for _wid in _prod["widget_list"]:
                _wid_key = _wid["prod_code"]
                _wid_res = {"name": _wid["attr_name"]}
                for _a in _wid["own_attr"] + _wid["mate_attr"] + _wid["craft_attr"]:
                    for k, v in self.parse_attr(_a).items():
                        _wid_res[k] = v
                _res[_wid_key] = _wid_res
            _key = "产品"
        return {_key: _res}

    def quoteMethod(self, data):
        if not data:
            return
        feature_name = next(iter(self.presets))
        app_dir = Path(__file__).parent.parent
        local_path = app_dir / constant.DIR_JAVASCRIPT
        remote_path = app_dir / constant.DIR_JAVASCRIPT_REMOTE
        file_name = data[0]["prod_code"] + ".js"
        if time.time() - self.last_request_time >= 60:
            remote_md5 = (
                cos_utils.get_single_file(str(remote_path / file_name))["ETag"].strip(
                    '"'
                )
                if cos_utils.object_exists(str(remote_path / file_name))
                else None
            )
            local_md5 = (
                cos_utils.md5_single(local_path / file_name)
                if os.path.exists(local_path / file_name)
                else None
            )
            if remote_md5 and remote_md5 != local_md5:
                cos_utils.download_single_file(remote_path / file_name, local_path)
            self.last_request_time = time.time()

        if not os.path.exists(local_path / file_name):
            self.call_js(
                feature_name, "window.setQuoteResult('报价中...');", callback=print
            )
            return

        params = {}
        for single in data:
            for attr in single["own_attr"] + single["craft_attr"] + single["mate_attr"]:
                for k, v in self.parse_attr(attr).items():
                    params[k] = v
            for _wid in single["widget_list"]:
                _wid_key = _wid["prod_code"]
                _wid_res = {"name": _wid["attr_name"]}
                for _a in _wid["own_attr"] + _wid["mate_attr"] + _wid["craft_attr"]:
                    for k, v in self.parse_attr(_a).items():
                        _wid_res[k] = v
                params[_wid_key] = _wid_res
        if os.getenv("INKLINK_DEBUG") == "1":
            print(params)

        try:
            json_content = json.dumps(params, indent=4, ensure_ascii=False)
            js_content = f"window.xx = {json_content};\n"
            with open(local_path / file_name, "r", encoding="utf-8") as f:
                script = f.read()
                js_content += script
                js_content += "\n"
            js_content += "window.setQuoteResult(result);"
            self.call_js(feature_name, js_content, callback=print)

        except Exception as e:
            print(f"读取或执行 JS 文件时出错: {e}")
