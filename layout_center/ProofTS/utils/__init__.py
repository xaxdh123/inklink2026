import math
from datetime import datetime

from utils.network import ApiClient

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
