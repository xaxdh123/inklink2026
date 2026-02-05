import math
from datetime import datetime
import traceback
from datetime import datetime
from PySide6.QtCore import QSettings

from utils.network import ApiClient

GLOB_CONFIG = QSettings("config.ini", QSettings.Format.IniFormat)
GLOB_NETWORK = ApiClient("https://private.qiyinbz.com:31415/")
# GLOB_NETWORK = ApiClient("http://192.168.22.247/")


def _now():
    return datetime.now().strftime("%m-%d %H:%M:%S")


def pt_to_mm(pt):
    _unit_mm = pt * 25.4 / 72
    i = round(_unit_mm)
    if i - 0.1 < _unit_mm < i + 0.1:
        _unit_mm = i
    else:
        _unit_mm = math.ceil(_unit_mm)
    return int(_unit_mm)


default_vals = {
    "ui/slow_src_path": "C:\\",
    "ui/slow_src_mv_path": "C:\\",
    "ui/slow_dest_path": "C:\\",
    "ui/slow_dest_dao_path": "C:\\",
    "ui/src_path": "C:\\",
    "ui/src_mv_path": "C:\\",
    "ui/dest_path": "C:\\",
    "ui/dest_2_path": "C:\\",
    "ui/dest_dao_path": "C:\\",
    "ui/delay_time": "60",
    "ui/over_time": "1440",
    "ui/space_item": "4",
    "storage/can_work_list": ["单枚单切", "单刀", r"拼多个\[\d+\]\[\d+\]"],
    "storage/combine_multi": ["4:1x4", "10:2x5"],
    "page/outline_size": ["289x214", "999x999"],
    "page/half_cut_threshold": 10,
    "page/single_threshold": 20,
    "page/single_extra": 10,
    "rect/single": "310x426",
    "rect/half": "310x210",
    "rect/quart": "152x202",
    "auth/qiyinbz_username": "苏成如",
    "auth/qiyinbz_user_password": "Aa123456",
    "auth/juheyou_username": "",
    "auth/juheyou_user_password": "",
}
try:
    for key, val in default_vals.items():
        if not GLOB_CONFIG.contains(key) or type(GLOB_CONFIG.value(key)) != type(val):
            GLOB_CONFIG.setValue(key, val)
except:
    traceback.print_exc()
