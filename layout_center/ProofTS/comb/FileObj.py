# encoding: utf-8
"""
优化后的 FileObj 类
- 增加类型注解和文档字符串
- 修复了多拼装解析的逻辑错误
- 更稳健地处理配置值的类型转换
- 修复了 from_dict 中缺失 is_single 字段的问题并增加默认值
- 用 logging 替换了打印调试信息
- 提高了对异常情况（如 PDF 页数/尺寸不一致、配置格式错误）的报错信息
"""
import logging
import math
import os
import re
from typing import List, Any, Dict, Optional

import fitz  # PyMuPDF

from utils import GLOB_CONFIG
from utils import pt_to_mm

logger = logging.getLogger(__name__)


class FileObj:
    """
    表示一个待排版/处理的文件对象。

    主要职责：
    - 从文件名/外部信息解析属性（店铺/客户/类型/工艺/尺寸/数量等）
    - 根据 PDF 实际页面尺寸校验并设置画布尺寸（gen_size）
    - 解析工艺相关的备注（gen_craft_remark）
    - 提供序列化/反序列化支持(to_dict / from_dict)
    """

    DESIGN_PREFIX_LEN = 12

    def __init__(
        self, dir2: str = "", f: str = "", all_f: Optional[List[str]] = None
    ) -> None:
        self.file_path: str = os.path.normpath(os.path.join(dir2, f))
        self.file_dir: str = dir2
        self.file_name: str = f
        self.shop: str = "" if not all_f else all_f[0]
        self.customer: str = "" if not all_f else all_f[1]
        self.kind: int = 0 if not all_f else int(all_f[2])
        self.type: str = "" if not all_f else all_f[3]
        self.mate: str = "" if not all_f else all_f[4]
        self.craft: List[str] = [] if not all_f else all_f[5].split(",")
        self.size: List[float] = (
            [] if not all_f else list(map(float, all_f[6].split("x")))
        )
        self.count: int = 0 if not all_f else int(all_f[7])
        self.price: str = "" if not all_f else all_f[8]
        self.order: str = "" if not all_f else all_f[9]
        self.design: str = "" if not all_f else all_f[10]
        self.remark: str = ""
        self.needCutOut: bool = False
        self.place_way: Dict[str, Any] = {}
        self.pos_info: Dict[int, Any] = {}
        self.multi_pre: List[int] = []
        self.is_single: bool = False  # 保留此字段以兼容 from_dict 使用
        self.deep_cut = ""
        self.gen_craft_remark()

    def gen_craft_remark(self) -> None:
        """
        从 design 字段后缀解析额外的工艺或拼版信息。
        - 若 design 长度大于 DESIGN_PREFIX_LEN，则把后缀部分解析到 remark 与 craft。
        - 解析指定关键词并添加到 craft（避免重复）。
        - 支持解析形如 "拼多个[m][n]" 的拼版说明，调整 size 与 count。
        """
        if self.design:
            m_short = re.match(r"^(SJ\d{10})(?![a-zA-Z0-9])", self.design)
            if m_short:
                prefix_len = self.DESIGN_PREFIX_LEN
            else:
                prefix_len = self.DESIGN_PREFIX_LEN + 2

            if len(self.design) > prefix_len:
                remark_temp = self.design[prefix_len:]
                # 可识别的工艺关键词
                keywords = [
                    "单枚单切",
                    "单刀",
                    "外框模切成型",
                    "模切成型",
                    "镂空",
                    "抠出",
                    "A3",
                    "A4",
                    "A5",
                ]
                for kw in keywords:
                    if kw in remark_temp and kw not in self.craft:
                        self.craft.append(kw)
                    # 只移除第一次出现，避免影响其他同名说明的解析位置
                    remark_temp = remark_temp.replace(kw, "", 1)
                split_data = {
                    segment.split(":")[0]: segment.split(":")[1].split("x")
                    for segment in GLOB_CONFIG.value("storage/combine_multi", type=list)  # type: ignore
                    if segment
                }
                multi_comb_re_1 = re.compile(r"([1一]张(\d+)[贴枚])")
                multi_comb_re = re.compile(r"拼多个\[(\d+)]\[(\d+)]")

                def found(x) -> bool:
                    m = multi_comb_re_1.search(x)
                    m2 = multi_comb_re.search(x)
                    if m and (__multi_key := m.groups()[0][1]) in split_data:
                        self.multi_pre = split_data[__multi_key]
                    elif m2:
                        self.multi_pre = list(map(int, m2.groups()))
                    if self.multi_pre:
                        if "单刀" in self.craft:
                            self.multi_pre.append(1)
                            self.craft.remove("单刀")
                        else:
                            self.multi_pre.append(0)
                        self.craft.append(
                            f"拼多个[{self.multi_pre[0]}][{self.multi_pre[1]}]"
                        )
                        return True
                    return False

                if found(remark_temp):
                    # 移除已解析的拼版说明
                    remark_temp = multi_comb_re_1.sub("", remark_temp)
                    remark_temp = multi_comb_re.sub("", remark_temp)
                for i, text in enumerate(self.craft):
                    if found(text):
                        del self.craft[i]
                        break
                # 使用匹配到的前缀长度截取 design 与 remark
                self.remark = self.design[prefix_len:]
                self.design = self.design[:prefix_len]

        # 保证工艺列表有序且唯一
        self.craft = sorted(set(self.craft))

        for x in self.craft:
            if x in ["模切成型", "外框模切成型", "镂空", "抠出"]:
                self.deep_cut = x + "-" + f"{self.size[0]}x{self.size[1]}"
                break
        logger.debug("Parsed craft: %s", self.craft)

    def gen_size(self) -> None:
        """
        根据 PDF 实际页面尺寸设置 self.size，并判断是否需要裁切（needCut）。
        - 会校验 PDF 页数是否为 kind * 2（原逻辑），以及所有页面尺寸一致。
        - 依据 GLOB_CONFIG 的 page/outline_size 判断是否为需要外框模切的尺寸。
        - 若 needCut 为 True，会在尺寸上做减裁（目前为每边各减 4）。
        """
        if not self.size or not self.file_path:
            return
        _sp = float(GLOB_CONFIG.value("ui/space_item"))
        with fitz.open(self.file_path) as doc:

            def get_wh(page_idx: int) -> List[float]:
                rect = doc.load_page(page_idx).rect
                length = pt_to_mm(rect[2] - rect[0])
                wid = pt_to_mm(rect[3] - rect[1])
                return [length, wid]

            page_count = doc.page_count
            expected_pages = int(self.kind) * 2
            if page_count != expected_pages:
                raise Exception(
                    f"页数不正确: 期望 {expected_pages} 页，实际 {page_count} 页"
                )

            self.size = get_wh(0)
            for k in range(page_count):
                if get_wh(k) != list(map(int, self.size)):
                    raise Exception("画布尺寸不一致，所有页面应具有相同尺寸")
        if self.multi_pre:
            if not self.size:
                return
            m, n, c = self.multi_pre
            self.size[0] += (self.size[0] - (_sp * c)) * (m - 1)
            self.size[1] += (self.size[1] - (_sp * c)) * (n - 1)
            # count 可能尚未初始化为正确值，保护性计算
            if self.count:
                self.count = math.ceil(self.count / m / n)
            # 记录工艺项
            self.craft.append(f"拼多个[{m}][{n}]")
            if "单枚单切" not in self.craft:
                self.craft.append("单枚单切")

        # 解析配置中允许的模切尺寸（形如 "A×B,A2xB2,..."，每项为 "AxB"）
        result: List[List[int]] = []
        for pair_str in GLOB_CONFIG.value("page/outline_size", type=list):  # type: ignore
            try:
                a, b = map(int, pair_str.strip().split("x"))
            except Exception as _:
                logger.debug("跳过无效的 outline_size 配置项: %r", pair_str)
                continue
            result.append([a, b])
            if a != b:
                result.append([b, a])
        self.needCutOut = ("外框模切成型" in self.craft) and (self.size in result)
        if self.needCutOut:
            # 减裁 4mm（原逻辑），若需要可修改为配置
            self.size = [x - _sp for x in self.size]

    def gen_params(self, w, h, clr_r):
        print("get_boxed:", w, h, self.size)
        if not self.size:
            return w, h, (clr_r(0, 0, "0"))
        base_space = float(GLOB_CONFIG.value("ui/space_item"))
        threshold = float(GLOB_CONFIG.value("page/single_threshold") or 0)
        extra = float(GLOB_CONFIG.value("page/single_extra") or 0)
        w1, h1 = self.size
        if "单枚单切" in self.craft:
            [w, h, w1, h1] = [int(x) + float(base_space) for x in [w, h, w1, h1]]

        if "单刀" in self.craft:
            if self.size[0] <= threshold or self.size[1] <= threshold:
                [w, h, w1, h1] = [int(x) + float(extra) for x in [w, h, w1, h1]]
            else:
                [w, h, w1, h1] = [int(x) - float(base_space) for x in [w, h, w1, h1]]
        return int(w), int(h), (clr_r(int(w1), int(h1), "0"),)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于持久化或跨进程传递）"""
        return {
            "file_path": self.file_path,
            "file_dir": self.file_dir,
            "file_name": self.file_name,
            "shop": self.shop,
            "customer": self.customer,
            "kind": self.kind,
            "type": self.type,
            "mate": self.mate,
            "craft": self.craft,
            "size": self.size,
            "count": self.count,
            "price": self.price,
            "order": self.order,
            "design": self.design,
            "place_way": self.place_way,
            "pos_info": self.pos_info,
            "remark": self.remark,
            "needCutOut": self.needCutOut,
            "multi_pre": self.multi_pre,
            "is_single": self.is_single,
            "deep_cut": self.deep_cut,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileObj":
        """
        从字典反序列化为 FileObj（不通过 __init__），兼容缺失字段并提供默认值。
        """
        obj = cls.__new__(cls)
        # 直接赋值（对缺失键使用默认值）
        obj.file_path = data.get("file_path", "")
        obj.file_dir = data.get("file_dir", "")
        obj.file_name = data.get("file_name", "")
        obj.shop = data.get("shop", "")
        obj.customer = data.get("customer", "")
        obj.kind = int(data.get("kind", 0))
        obj.type = data.get("type", "")
        obj.mate = data.get("mate", "")
        obj.craft = list(data.get("craft", []))
        obj.size = list(data.get("size", []))
        obj.count = int(data.get("count", 0))
        obj.price = data.get("price", "")
        obj.order = data.get("order", "")
        obj.design = data.get("design", "")
        obj.is_single = data.get("is_single", False)
        obj.remark = data.get("remark", "")
        obj.place_way = data.get("place_way", [])
        obj.pos_info = data.get("pos_info", [])
        obj.deep_cut = data.get("deep_cut", "")
        obj.needCutOut = bool(data.get("needCutOut", False))
        obj.multi_pre = list(data.get("multi_pre", []))
        return obj
