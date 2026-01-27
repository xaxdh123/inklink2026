import traceback
from datetime import datetime
from PySide6.QtCore import QSettings

GLOB_CONFIG = QSettings("config.ini", QSettings.Format.IniFormat)
default_vals = {
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


def get_center(key):
    center = [160, 232]
    if key == 2:
        half: str = GLOB_CONFIG.value("rect/half")
        y_offset = 3 + int(half.split("x")[1]) / 2
        t_c = [center[0], center[1] + y_offset]
        b_c = [center[0], center[1] - y_offset]
        return [t_c, b_c]
    elif key == 4:
        quart: str = GLOB_CONFIG.value("rect/quart")
        x_offset = 3 + int(quart.split("x")[0]) / 2
        y_offset = 3 + int(quart.split("x")[1]) / 2
        t_l_c = [center[0] - x_offset, center[1] + y_offset]
        t_r_c = [center[0] + x_offset, center[1] + y_offset]
        b_l_c = [center[0] - x_offset, center[1] - y_offset]
        b_r_c = [center[0] + x_offset, center[1] - y_offset]
        return [t_l_c, t_r_c, b_l_c, b_r_c]
    else:
        return [center]


def get_fixed_qr(key: int):
    rt = [320 - 14 - 8, 464 - 11 - 8]
    rb = [320 - 14 - 8, 11]
    lt = [80 - 3 - 8, 464 - 11 - 8]
    lb = [80 - 3 - 8, 11]

    if key == 2:
        return [rt, rb]
    elif key == 4:
        return [lt, rt, lb, rb]
    else:
        return [rt]


def get_typeset_no():
    strf_time = datetime.now().strftime(r"%Y%m%d")

    if not GLOB_CONFIG.contains("typeset_no"):
        time_ts = f"TS{strf_time}0001"
        GLOB_CONFIG.setValue("typeset_no", time_ts)
        return time_ts
    else:
        value = GLOB_CONFIG.value("typeset_no")
        if strf_time == value[2:10]:
            try:
                seq = int(value[10:]) + 1
            except Exception:
                seq = 1
            time_ts = f"TS{strf_time}{str(seq).zfill(4)}"
            GLOB_CONFIG.setValue("typeset_no", time_ts)
            return time_ts
        else:
            time_ts = f"TS{strf_time}0001"
            GLOB_CONFIG.setValue("typeset_no", time_ts)
            return time_ts
