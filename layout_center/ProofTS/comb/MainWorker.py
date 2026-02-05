# encoding: utf-8
import glob
import itertools
import math
import os
import re
import shutil
import time
import traceback
import datetime
from copy import deepcopy
import fitz
import clr
import debugpy
from PySide6.QtCore import QObject, Signal, Slot
from layout_center.ProofTS import comb
from layout_center.ProofTS.comb.FileObj import FileObj
from utils import _now, GLOB_NETWORK, GLOB_CONFIG

clr.AddReference("System.Core")
clr.AddReference(rf"resources\out-pdf\ClassLibrary1")
clr.AddReference(rf"resources\out-pack\Pack")
from ClassLibrary1 import Class1  # type: ignore
from Pack import R, Result, Utils  # type: ignore
from System.Collections.Generic import Dictionary, List  # type: ignore

file_re = re.compile(
    r"(.+)\^(.+)\^(\d+)\^(.+)\^(.+)\^(.+)\^(\d+x\d+)\^(.*)\^(\d+)\^(.+)\^(.+).pdf"
)


class MainWorker(QObject):
    message_signal = Signal(object, name="worker")
    _do_next = False

    def __init__(self):
        """初始化Worker线程，连接日志信号"""
        super(MainWorker, self).__init__()
        self.wait_for = []
        self.waiting_dir = None
        self.clr_addFiles = Class1.AddFilesV2
        self.clr_addImg = Class1.AddQRV2
        self.clrPack = Utils.SinglePack
        self.clr_R = R
        self.clr_line = Class1.AddLine
        self.clr_setNo = Class1.SetTypesetNo
        self.clr_Result = Result
        # 初始化用于按材质分发目标目录的映射（由 config.ini 中的 mate_folder 填充）
        self.map_mate = {}

    def stop(self):
        """停止主循环：设置停止标志。

        由外部 UI 调用以请求线程停止。不会立即终止正在进行的文件处理操作，
        但后续循环会检查 `_do_next` 并优雅退出。
        """
        self._do_next = False
        print("stop", self._do_next)

    @Slot()
    def start(self):
        """启动主循环。
        1) 尝试将当前线程注册到 debugpy（如果可用），
        2) 初始化内部状态并循环扫描输入目录。
        """
        try:
            debugpy.debug_this_thread()
        except Exception:
            # 非调试状态下忽略
            pass
        self._do_next = True
        if not self.waiting_dir:
            self.waiting_dir = os.path.join(GLOB_CONFIG.value("ui/src_path"), "待出版")
            os.makedirs(self.waiting_dir, exist_ok=True)
        GLOB_CONFIG.beginGroup("mate_folder")
        self.map_mate = {
            k: list(GLOB_CONFIG.value(k).split(",")) for k in GLOB_CONFIG.childKeys()
        }
        GLOB_CONFIG.endGroup()
        self.message_signal.emit(
            {"msg": f"开始查找：{GLOB_CONFIG.value('ui/src_path')}"}
        )
        while True:
            if not self._do_next:
                time.sleep(0.5)
                continue
            self.wait_for.clear()

            # 主线程运行循环：监听并处理PDF文件,等待延迟时间后再开始扫描
            loop_res = self.loop_find_file()
            if not loop_res:
                self.message_signal.emit({"msg": "排版已停止", "done": True})
                return

            if not len(self.wait_for) and self._do_next:
                self.message_signal.emit({"next": True})
                continue
            # 以 customer+mate+craft 为分组键
            for k, v in itertools.groupby(self.wait_for, self.__format_type):
                try:
                    res_handle = self.handle_files(k, v)
                    if not res_handle:
                        self.message_signal.emit({"msg": "排版已停止", "done": True})
                        return
                except Exception as e:
                    traceback.print_exc()
                    self.message_signal.emit(
                        {"msg": "排版已停止" + str(e), "done": True}
                    )
            self.message_signal.emit({"msg": "拼版完成", "next": True})
            # 本轮结束
            self._do_next = False

    def handle_files(self, k, v):
        """处理同一分组（customer+mate+craft）的一组文件。

        - 对组内文件按放置优先级排序，尝试合并/拼版（调用 `placed_file`），
        - 若拼版产生完整版面则调用 `place_end` 完成后续移动/写文件操作。
        """
        iter_file = sorted(v, key=lambda x: x.place_way["key"], reverse=True)
        print(_now(), k, "张数", len(iter_file), iter_file[0].place_way["count"])
        if len(iter_file) == 1 and iter_file[0].place_way["count"] < 1:
            if not self._do_next:
                return False
            f: FileObj = iter_file.pop()
            self.__move_wait(f)
            key = self.__format_type(f, False)
            GLOB_CONFIG.beginGroup("half_quarter_page")
            try:
                cache: dict = GLOB_CONFIG.value(key) or {}
                cache[int(time.time() * 10)] = f.to_dict()
                GLOB_CONFIG.setValue(key, cache)
            finally:
                GLOB_CONFIG.endGroup()
            time.sleep(0.1)
        else:
            _last_file = []
            while len(iter_file):
                if not self._do_next:
                    return False
                f: FileObj = iter_file.pop()
                self.__move_wait(f)
                for _last in _last_file:
                    if _last.place_way["count"] + f.place_way["count"] <= 1:
                        print(_now(), f.file_name, "<1 合拼")
                        print(_last.place_way["count"], f.place_way["count"])
                        f = self.placed_file(f, _last)
                        _last_file.remove(_last)
                        break
                else:
                    print(_now(), f.file_name, ">=1 / nil  创建")
                    f = self.placed_file(f, None)
                if f.place_way["count"] >= 1:
                    self.place_end(f)
                else:
                    _last_file.append(f)
            for f in _last_file:
                new_f = deepcopy(f)
                new_f.place_way["count"] = 1
                f = self.placed_file(f, f)
                self.place_end(f)
        return True

    def loop_find_file(self):
        """扫描 `ui/src_path` 目录，匹配符合命名规则的 PDF 并加入待处理队列。

        - 读取配置中的延迟时间；在延迟期内如果文件夹没有变化则认为收集完成。
        - 对文件名不合法或解析失败的文件移动到异常目录。
        """
        _src_path = GLOB_CONFIG.value("ui/src_path")
        _delay_time = int(GLOB_CONFIG.value("ui/delay_time"))
        print(_now(), "_src_path", _src_path, "_delay_time", _delay_time)
        _loop_run_time = time.time() + _delay_time
        join = os.path.join(_src_path, "*.pdf")
        file_count = sum(1 for _ in glob.iglob(join))
        if file_count > 0:
            self.message_signal.emit({"msg": f"找到{file_count}个文件"})
        for f in glob.iglob(join):
            print("stop", self._do_next)
            if not self._do_next:
                return False
            if self.__exist_in_wait(f):
                continue
            f_all = file_re.findall(
                "".join([char for char in os.path.basename(f) if char.isprintable()])
            )
            if not f_all:
                obj_err = FileObj(*os.path.split(f))
                self.__move_error(obj_err, "文件名不合法")
                continue
            obj = {}
            try:
                os.chmod(f, 0o666)
                if not os.access(f, os.R_OK | os.W_OK):
                    continue
                obj = FileObj(*os.path.split(f), f_all[0])
                obj.gen_size()
                #  核心 计算排版位置 方法
                w1, h1 = map(int, GLOB_CONFIG.value("rect/single").split("x"))
                w2, h2 = map(int, GLOB_CONFIG.value("rect/half").split("x"))
                w4, h4 = map(int, GLOB_CONFIG.value("rect/quart").split("x"))
                _judge_fixed = self.judge_fixed(obj)
                if not _judge_fixed:
                    w, h, boxes = obj.gen_params(w1, h1, self.clr_R)
                    res_single = self.clrPack(self.clr_R(w, h), True, True, True, boxes)
                    w, h, boxes = obj.gen_params(w2, h2, self.clr_R)
                    result_half = self.clrPack(
                        self.clr_R(w, h), True, True, True, boxes
                    )
                    w, h, boxes = obj.gen_params(w4, h4, self.clr_R)
                    result_quart = self.clrPack(
                        self.clr_R(w, h), True, True, True, boxes
                    )
                    _judge_same = self.judge_same(
                        obj, res_single, result_half, result_quart
                    )
                    if not _judge_same:
                        _judge_page = self.judge_page(
                            obj, res_single, result_half, result_quart
                        )
                        if not _judge_page:
                            self.gen_ways(obj, result_quart, 4, True)
                self.wait_for.append(obj)
                self.message_signal.emit(
                    {"msg": f"为 {obj.design} 计算位置:版面 {obj.place_way['key']} "}
                )
                print(_now(), obj.to_dict())
            except Exception as e:
                traceback.print_exc()
                self.__move_error(obj, e)
            time.sleep(0.1)
        while time.time() < _loop_run_time:
            if not self._do_next:
                return False
            time.sleep(1)

        if sum(1 for x in glob.iglob(join) if not self.__exist_in_wait(x)):
            return self.loop_find_file()
        elif len(self.wait_for):
            strMsg = f"{_delay_time}秒内文件夹没有变化,文件总个数：{len(self.wait_for)}"
            self.message_signal.emit({"msg": strMsg})
        return True

    def judge_fixed(self, obj: FileObj):
        if "A3" in obj.craft:
            w, h, boxes = obj.gen_params(320, 420, self.clr_R)
            result = self.clrPack(self.clr_R(w, h), True, True, True, boxes)
            if not result:
                raise Exception("A3一份也放不下")
            self.gen_ways(obj, result, 1, True)
            return True
        elif "A4" in obj.craft:
            w, h, boxes = obj.gen_params(210, 300, self.clr_R)
            result = self.clrPack(self.clr_R(w, h), True, True, True, boxes)
            if not result:
                raise Exception("A4一份也放不下")
            self.gen_ways(obj, result, 2, True)
            return True
        elif "A5" in obj.craft:
            w, h, boxes = obj.gen_params(210, 148, self.clr_R)
            result = self.clrPack(self.clr_R(w, h), True, True, True, boxes)
            if not result:
                raise Exception("A5一份也放不下")
            self.gen_ways(obj, result, 4, True)
        else:
            return False

    def judge_same(self, obj: FileObj, _r1, _r2, _r4):
        if not _r2:
            self.gen_ways(obj, _r1, 1, True)
            return True

        # 针对单份(kind==1)的优先规则（尽量用更小尺寸放置以提高合版率），并记录原因
        if obj.kind == 1:
            half_cut_threshold = float(GLOB_CONFIG.value("page/half_cut_threshold"))
            if _r4 and _r4.GetRepeat() >= obj.count:
                self.gen_ways(obj, _r4, 4, True)
            elif _r2.GetRepeat() >= obj.count:
                self.gen_ways(obj, _r2, 2, True)
            elif _r1.GetRepeat() >= obj.count:
                self.gen_ways(obj, _r1, 1, True)
            elif (
                _r2.GetRepeat() * 2 * half_cut_threshold >= obj.count
                and "单枚单切" not in obj.craft
            ):
                self.gen_ways(obj, _r2, 2, True)
            else:
                self.gen_ways(obj, _r1, 1, True)
            return True
        if not _r4:
            self.gen_ways(obj, _r2, 2, True)
            return True
        return False

    def judge_page(self, obj, _r1, _r2, _r4):
        count_kind1_4 = math.ceil(obj.count / _r4.GetRepeat()) * math.ceil(obj.kind / 4)
        count_kind1_2 = math.ceil(obj.count / _r2.GetRepeat()) * math.ceil(obj.kind / 2)
        count_kind1_1 = math.ceil(obj.count / _r1.GetRepeat()) * obj.kind
        if obj.kind <= _r4.GetRepeat() and count_kind1_4 <= count_kind1_2:
            count_allin_4 = math.ceil(obj.count / 4)
            self.gen_ways(obj, _r4, 4, count_kind1_4 <= count_allin_4)
            return True
        if obj.kind <= _r2.GetRepeat() and count_kind1_2 <= count_kind1_1:
            count_allin_2 = math.ceil(obj.count / 2)
            self.gen_ways(obj, _r2, 2, count_kind1_2 <= count_allin_2)
            return True
        if obj.kind <= _r1.GetRepeat():
            count_allin_1 = obj.count
            self.gen_ways(obj, _r1, 1, count_kind1_1 <= count_allin_1)
            return True
        return False

    def gen_ways(self, obj: FileObj, _res, _type, is_one_kind):
        need_flip1 = _type in [1, 4] and _res.GetBin().R.W > _res.GetBin().R.H
        need_flip2 = _type == 2 and _res.GetBin().R.W < _res.GetBin().R.H

        if need_flip1 or need_flip2:
            # 调整尺寸以适应翻转
            _max = (
                [_res.GetUseY(), _res.GetUseX()]
                if is_one_kind or obj.deep_cut
                else [0, 0]
            )
            _pd = []
            for d in _res.GetPlaced():
                d.X, d.Y = d.Y, d.X
                d.R.W, d.R.H = d.R.H, d.R.W
                _pd.append(d)
        else:
            # 使用原始尺寸
            _max = (
                [_res.GetUseX(), _res.GetUseY()]
                if is_one_kind or obj.deep_cut
                else [0, 0]
            )
            _pd = [d for d in _res.GetPlaced()]

        _space = float(GLOB_CONFIG.value("ui/space_item"))
        repeat = _res.GetRepeat() if is_one_kind or obj.deep_cut else 1
        count = math.ceil(obj.count / repeat)
        more = count * repeat - obj.count
        pos_data = {}

        # 分支 1：单一种类或需要完整画线（逐位置分配）
        if is_one_kind or obj.deep_cut:
            # 使用引擎返回的使用尺寸作为最大画布边界
            _max = [_res.GetUseX(), _res.GetUseY()]
            count1 = count * math.ceil(obj.kind / _type)
            count2 = obj.kind * math.ceil(count / _type)
            if count1 <= count2:
                for i in range(obj.kind):
                    prints, lines = [], []
                    for d in _res.GetPlaced():
                        ps, ls = self.__trans_pos_data(d, obj, _space, i, _max)
                        prints.extend(ps)
                        lines.extend(ls)
                    pos_data[i] = {"print": prints, "lines": lines}
                # 如果只有一份但 kind 小于版面槽位数，调整计数以反映占用比
                if count == 1 and obj.kind < _type:
                    count = obj.kind / _type
            else:
                i = 0
                for _i in range(obj.kind):
                    for _ in range(_type):
                        prints, lines = [], []
                        for d in _res.GetPlaced():
                            ps, ls = self.__trans_pos_data(d, obj, _space, _i, _max)
                            prints.extend(ps)
                            lines.extend(ls)
                        pos_data[i] = {"print": prints, "lines": lines}
                        i += 1
                count = math.ceil(count / _type)

        else:
            # 分支 2：混合放置（使用统一模板并根据需要重复）
            # 先计算放置单元在 X/Y 方向上的最大占用范围（仅考虑前 obj.kind 个放置）
            _max = [0, 0]
            for i, d in enumerate(_res.GetPlaced()):
                if i < obj.kind:
                    _max[0] = max(_max[0], d.X + d.R.W)
                    _max[1] = max(_max[1], d.Y + d.R.H)
            # 将前 obj.kind 个放置单元转换为统一的 prints/lines 模板
            prints, lines = [], []
            for i, d in enumerate(_res.GetPlaced()):
                if i < obj.kind:
                    ps, ls = self.__trans_pos_data(d, obj, _space, i, _max)
                    prints.extend(ps)
                    lines.extend(ls)
            # 根据需要画满多少槽位，将相同的模板填入 pos_data
            for i in range(min(count, _type)):
                pos_data[i] = {"print": prints, "lines": lines}
            # 若实际 count 小于槽位数，记录为占用比（便于后续合并/more 计算）
            if count < _type:
                count = count / _type

        # 填充 place_way 与 pos_info，index 初始化为 0
        obj.place_way = dict(
            key=_type,
            count=count,
            total=count * _res.GetRepeat(),
            max=_max,
            more=more,
            index=0,
        )
        obj.pos_info = pos_data

    def placed_file(self, cur_file: FileObj, last_file):
        try:
            path_data = List[str]()
            config = Dictionary[str, int]()
            data = Dictionary[int, Dictionary[str, List[str]]]()
            path_data.Add(cur_file.file_path)
            # 使用局部集合 `customers` 暂存客户集合，稍后统一赋回到 cur_file.place_way
            customers = {cur_file.customer}
            deep_cuts = {cur_file.deep_cut}
            design_ls = {cur_file.design}
            file_list = {cur_file.file_name: cur_file.place_way["total"]}
            if not last_file:
                no = comb.get_typeset_no()
                config["index"] = 0
                self.message_signal.emit({"typeset": no})
                path_data.Add(os.path.join(cur_file.file_dir, no + "-print.pdf"))
                path_data.Add(os.path.join(cur_file.file_dir, no + ".pdf"))
            else:
                no = last_file.place_way["no"]
                self.message_signal.emit({"typeset": no})
                if last_file.place_way["key"] == 2 and cur_file.place_way["key"] == 4:
                    _index = 2
                elif (
                    last_file.place_way["index"] % 4 != 3
                    and last_file.place_way["key"] == 4
                    and cur_file.place_way["key"] == 2
                ):
                    _index = 1
                else:
                    _index = last_file.place_way["index"] or 0
                config["index"] = _index
                path_data.Add(last_file.place_way["src_print"])
                path_data.Add(last_file.place_way["src_lines"])
                [customers.add(c) for c in last_file.place_way["customers"]]
                [deep_cuts.add(c) for c in last_file.place_way["deep_cuts"]]
                [design_ls.add(c) for c in last_file.place_way["design_ls"]]
                for k, v in last_file.place_way["file_list"].items():
                    file_list[k] = v
            cur_file.place_way["customers"] = customers
            cur_file.place_way["deep_cuts"] = deep_cuts
            cur_file.place_way["design_ls"] = design_ls
            cur_file.place_way["file_list"] = file_list
            key = cur_file.place_way["key"]
            for i in range(min(key, int(key * cur_file.place_way["count"]))):
                if i not in cur_file.pos_info and i > cur_file.place_way["index"]:
                    cur_file.pos_info[i] = cur_file.pos_info[1 if i == 3 else 0].copy()
                    cur_file.place_way["more"] += len(cur_file.pos_info[i]["print"])
            for i, pos in cur_file.pos_info.items():
                data[i] = Dictionary[str, List[str]]()
                _index = (i + config["index"]) % key
                print(_now(), "index", _index, comb.get_center(key)[_index])
                data[i]["center"] = self.__new_list(comb.get_center(key)[_index])
                data[i]["print"] = self.__new_list(
                    ",".join(map(str, p)) for p in pos["print"]
                )
                data[i]["lines"] = self.__new_list(
                    ",".join(map(str, l)) for l in pos["lines"]
                )
                data[i]["center_order"] = self.__new_list(
                    comb.get_fixed_qr(key)[_index]
                )
                data[i]["order_qr"] = self.__new_list([cur_file.order])
                data[i]["customer"] = self.__new_list(
                    [f"+{cur_file.place_way['more']} {cur_file.customer}"]
                )
                cur_file.place_way["index"] = _index + 1
            config["key"] = key
            print(_now(), "clr_addFiles", path_data, data, config)
            result: Dictionary[str, str] = self.clr_addFiles(path_data, data, config)
            cur_file.place_way["src_print"] = self.clr_line(
                result["print"], 11, 232, 320 - 11, 232
            )
            if last_file:
                if (
                    cur_file.customer not in last_file.place_way["customers"]
                    and config["index"] == 3
                ):
                    cur_file.place_way["src_print"] = self.clr_line(
                        cur_file.place_way["src_print"], 160, 20, 160, 464 - 20
                    )
                cur_file.place_way["count"] += last_file.place_way["count"] or 0
            cur_file.place_way["no"] = no
            cur_file.place_way["src_print"] = result["print"]
            cur_file.place_way["src_lines"] = result["lines"]
            strf_time = datetime.datetime.now().strftime("%Y-%m-%d")
            src_mv_path = GLOB_CONFIG.value("ui/src_mv_path")
            src_mv_path_date = os.path.join(src_mv_path, strf_time)
            dest_src_moved = os.path.join(
                src_mv_path_date, os.path.basename(cur_file.file_path)
            )
            if os.path.exists(dest_src_moved):
                os.remove(dest_src_moved)
                # 使用 safe move，处理文件被占用的情况
            moved1 = self._safe_move(cur_file.file_path, dest_src_moved)
            if not moved1:
                raise Exception(
                    f"移动源文件失败: {cur_file.file_path} -> {dest_src_moved}"
                )
            os.makedirs(src_mv_path_date, exist_ok=True)
            self.message_signal.emit(
                {
                    "msg": f"为 {cur_file.design}=>{cur_file.place_way['no']} 生成拼版文件"
                }
            )
        except Exception as e:
            traceback.print_exc()
            self.message_signal.emit({"msg": "排版异常 继续" + str(e)})
            self.__move_error(cur_file, e)
        return cur_file

    def place_end(self, file: FileObj):
        crafts = file.craft[:]
        if len(file.place_way["customers"]) > 1:
            crafts.append("多订单合拼")
        if "当天" in file.file_name:
            crafts.append("当天")
        if "加急" in file.file_name:
            crafts.append("加急")
        data = Dictionary[str, str]()
        data["no"] = file.place_way["no"]
        print("place_end", file.file_name, file.place_way["no"])
        try:
            if len(file.design) != FileObj.DESIGN_PREFIX_LEN:
                resp = GLOB_NETWORK.urllib_get(
                    "production-api/typesettingNew/creatAdhesiveTypesettingNo"
                )
                if resp["code"] == 200:
                    data["no"] = resp["data"]
                else:
                    print("creatAdhesiveTypesettingNo", resp)
                    self.message_signal.emit(
                        {
                            "msg": f"获取排版号失败，使用临时排版号: {data['no']} error: {resp['msg']}"
                        }
                    )
            else:
                jsonString = {
                    "orderInfos": list(file.place_way["design_ls"]),
                    "dto": {"num": math.ceil(file.place_way["count"])},
                    "type": "proofing",
                }
                resp = GLOB_NETWORK.d3_post(
                    "method=custom.produce.produceWorkCustom.addByDetail",
                    data=jsonString,
                    isT3=True,
                )
                if resp["code"] == 200:
                    data["no"] = resp["data"]["code"]
                else:
                    print("addByDetail", resp)
                    self.message_signal.emit(
                        {
                            "msg": f"获取排版号失败，使用临时排版号: {data['no']} error: {resp['msg']}"
                        }
                    )
        except:
            traceback.print_exc()
        data["material"] = file.mate
        data["count"] = str(math.ceil(file.place_way["count"])) + "张"
        data["crafts"] = ",".join(crafts)
        data["remark"] = file.remark
        strf_time = datetime.datetime.now().strftime("%Y-%m-%d")
        date_order_kv = GLOB_CONFIG.value("storage/data_order_no", strf_time)
        GLOB_CONFIG.beginGroup("data_order_no")
        if date_order_kv != strf_time:
            GLOB_CONFIG.setValue("storage/data_order_no", strf_time)
            for key in GLOB_CONFIG.childKeys():  # 删除每个键
                GLOB_CONFIG.remove(key)
        data_order_no: str = GLOB_CONFIG.value(file.order) or ""
        if not file.order in data_order_no.split(","):
            data["relate"] = file.order + ":" + data_order_no
            data_order_no = data["no"]
        else:
            data["relate"] = ""
            data_order_no += "," + data["no"]
        GLOB_CONFIG.setValue(file.order, data_order_no)
        GLOB_CONFIG.endGroup()
        title_pos = [187, 451] if file.place_way["key"] == 4 else [160, 451]
        file.place_way["src_print"] = self.clr_addImg(
            file.place_way["src_print"],
            self.__new_list([14, 445]),
            self.__new_list(title_pos),
            data,
        )
        self.message_signal.emit({"msg": f"为{data['no']} 添加附加信息"})
        dest_path = GLOB_CONFIG.value("ui/dest_path")
        dest_2_path = GLOB_CONFIG.value("ui/dest_2_path")
        dest_dao_path = GLOB_CONFIG.value("ui/dest_dao_path")
        try:
            dest_2_path_date = os.path.join(dest_2_path, strf_time)
            os.makedirs(dest_2_path_date, exist_ok=True)
            for k, v in self.map_mate.items():
                if file.mate in v:
                    dest_path = os.path.join(dest_path, k)
                    os.makedirs(dest_path, exist_ok=True)
                    break
            src_name = f"{data['no']}-{','.join(file.place_way['customers'])}-{file.mate}-{data['crafts']}-320X464-{data['count']}_自动拼版.pdf"
            dest_print_pdf = os.path.join(dest_path, src_name)
            dest_lines_pdf = os.path.join(dest_2_path_date, f"{data['no']}.pdf")
            try:
                if os.path.exists(dest_print_pdf):
                    os.remove(dest_print_pdf)
                if os.path.exists(dest_lines_pdf):
                    os.remove(dest_lines_pdf)
            except Exception as e:
                traceback.print_exc()
                print("删除存在", e)
                pass

            moved2 = self._safe_move(file.place_way["src_print"], dest_print_pdf)
            if not moved2:
                raise Exception(
                    f"移动 print 文件失败: {file.place_way['src_print']} -> {dest_print_pdf}"
                )
            moved3 = self._safe_move(file.place_way["src_lines"], dest_lines_pdf)
            if not moved3:
                raise Exception(
                    f"移动 lines 文件失败: {file.place_way['src_lines']} -> {dest_lines_pdf}"
                )

            with fitz.open(dest_lines_pdf) as doc:

                def copy(page=""):
                    if file.place_way["deep_cuts"]:
                        deep = ",".join(file.place_way["deep_cuts"])
                        for i in range(1, len(file.place_way["deep_cuts"])):
                            deep += (
                                "," + list(file.place_way["deep_cuts"])[i].split("-")[1]
                            )
                    else:
                        deep = ""
                    deep = "-" + deep if deep else ""
                    name = f"{(data['no']+page)[-10:].replace('0', 'O')}{deep}.pdf"
                    dest_dao_pdf = os.path.join(dest_dao_path, name)
                    if os.path.exists(dest_dao_pdf):
                        os.remove(dest_dao_pdf)
                    return dest_dao_pdf

                if len(doc) == 1:
                    shutil.copy(dest_lines_pdf, copy())
                else:
                    for i in range(len(doc)):
                        with fitz.open() as new_doc:
                            new_doc.insert_pdf(doc, from_page=i, to_page=i)
                            new_doc.save(copy(f"_{i+1}"))
            try:
                for _file in glob.iglob(
                    os.path.join(self.waiting_dir or "", file.place_way["no"] + "*.pdf")
                ):
                    os.remove(_file)
            except:
                pass
            payload = dict(
                designNo=file.design,
                material=file.mate,
                count=math.ceil(file.place_way["count"]),
                remark=file.remark,
                ts_no=data["no"],
                file_list=file.place_way["file_list"],
                dest_print_pdf=dest_print_pdf,
                src_name=src_name,
            )

            print("upload_to_system", payload)
            self.upload_to_system(payload)

            self.message_signal.emit({"msg": f"为 {data['no']} 移动文件"})
        except Exception as e:
            traceback.print_exc()
            print("upload_to_system", e)
        return file

    def upload_to_system(self, payload):
        try:
            self.message_signal.emit({"typeset": payload["ts_no"]})
            if len(payload["designNo"]) == FileObj.DESIGN_PREFIX_LEN:
                self.clr_setNo(
                    re.sub(
                        r"[A-Z]:\\新城打样",
                        lambda m: r"H:\\新城打样",
                        payload["dest_print_pdf"],
                    ),
                    payload["ts_no"],
                )
                resp = GLOB_NETWORK.d3_post(
                    "method=custom.app.produce.appCusProduceCustom.getPage&bizType=ALL",
                    {
                        "qo": {
                            "likeCode": payload["ts_no"],
                            "pageNo": 1,
                            "pageSize": 30,
                        }
                    },
                    True,
                )
                if resp["code"] == 200:
                    resp = resp["data"]["content"][0]
                    url = "method=custom.app.produce.appCusProduceWork.updateWorkName&bizType=ALL&_prdCode=custom&_pageCode=custom.custom.purchase.production.index"
                    data = {"dto": {"id": resp["id"], "name": payload["src_name"]}}
                    resp = GLOB_NETWORK.d3_post(url, data, True)
                    print("http_post", resp)
                else:
                    raise Exception(
                        f"T3系统 {payload['ts_no']} 返回错误: {resp.get('msg')}"
                    )
                print(_now(), str(resp))
            else:
                resp2 = GLOB_NETWORK.urllib_post(
                    "production-api/typesettingNew/saveStickerProofingTypesetting",
                    {
                        "filePath": re.sub(
                            r"[A-Z]:\\新城打样",
                            lambda m: r"\\192.168.110.252\h\新城打样",
                            payload["dest_print_pdf"],
                        ),
                        "typesetNo": payload["ts_no"],
                        "material": payload["material"],
                        "crafts": "印刷版",
                        "remark": payload["remark"],
                        "width": 320,
                        "height": 464,
                        "total": payload["count"],
                        "designList": [
                            {"fileName": k, "num": v}
                            for k, v in payload["file_list"].items()
                        ],
                    },
                    timeout=60,
                )
                if resp2["code"] != 200:
                    raise Exception(
                        f"新系统上传{payload['ts_no']}失败: {resp2.get('msg')}"
                    )
                else:
                    return self.message_signal.emit(
                        {"msg": f"为 {payload['ts_no']} 上传新系统 成功"}
                    )
        except Exception as e:
            traceback.print_exc()
            self.message_signal.emit(
                {
                    "msg": f"上传失败: {str(e)}",
                    "action": "RETRY_UPLOAD",
                    "payload": payload,  # 将数据原封不动发给 UI，重试时用
                }
            )

    def __move_error(self, _f, err):
        """移动异常文件到错误目录"""
        try:
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", str(err))
            if len(safe_name) > 20:
                errShort = safe_name[:20] + "-省略-"
            else:
                errShort = safe_name
            self.message_signal.emit({"msg": f"{_f.file_path} {err}"})
            goal_dir = os.path.join(_f.file_dir, "异常", errShort)
            os.makedirs(goal_dir, exist_ok=True)
            # 使用 _safe_move 将异常文件移动到异常目录
            dest = os.path.join(goal_dir, os.path.basename(_f.file_path))
            if not self._safe_move(_f.file_path, dest):
                # 如果移动失败，仍然记录日志但不抛出异常
                self.message_signal.emit(
                    {"msg": f"移动到异常目录失败：{_f.file_path} -> {dest}"}
                )
        except:
            traceback.print_exc()
            self.message_signal.emit({"msg": f"{_f.file_path} {err} 移动失败"})

    def __move_wait(self, f: FileObj):
        if f.file_dir != self.waiting_dir:
            _dest = os.path.join(self.waiting_dir or "", f.file_name)
            if os.path.exists(_dest):
                os.remove(_dest)
            i = 0
            while i < 10:
                try:
                    # 尝试直接移动，若抛出异常则交由 _safe_move 处理
                    dest = os.path.join(
                        self.waiting_dir or "", os.path.basename(f.file_path)
                    )
                    if self._safe_move(f.file_path, dest):
                        # 移动成功后更新 FileObj 的路径信息并返回
                        f.file_dir = self.waiting_dir or ""
                        f.file_path = dest
                        return True
                    else:
                        # 若 _safe_move 失败，休眠重试
                        time.sleep(0.5)
                        i += 1
                        continue
                except Exception as e:
                    i += 1
                    time.sleep(0.5)
            # 多次尝试仍失败则返回 False，不修改 FileObj
            return False

    def __exist_in_wait(self, path):
        xs = [x for x in self.wait_for if x.file_path == os.path.normpath(path)]
        return len(xs) > 0

    @staticmethod
    def __trans_pos_data(_d, file, _space, offset, _max):
        pos = []
        flip = 1 if (_d.R.W > _d.R.H) != (file.size[0] > file.size[1]) else 0
        is_max_x = _d.X + _d.R.W == _max[0]
        is_max_y = _d.Y + _d.R.H == _max[1]
        new_d = [_d.X, _d.Y, _d.R.W, _d.R.H]
        space_craft = (
            1 if "单枚单切" in file.craft else -1 if "单刀" in file.craft else 0
        )
        new_d[0] += (-_max[0] / 2) + _space / 2 * space_craft
        new_d[1] += (-_max[1] / 2) + _space / 2 * space_craft
        new_d[2] -= _space * space_craft
        new_d[3] -= _space * space_craft
        if file.multi_pre:
            mt, nt, ct = file.multi_pre
            old_w = (file.size[0] + _space * ct * (mt - 1)) / mt
            old_h = (file.size[1] + _space * ct * (nt - 1)) / nt
            for m in range(file.multi_pre[0]):
                for n in range(file.multi_pre[1]):
                    nor_pos = [new_d[0], new_d[1], old_w, old_h]
                    if flip == 1:
                        nor_pos[0] += (old_h - _space * ct) * n
                        nor_pos[1] += (old_w - _space * ct) * m
                        nor_pos[2], nor_pos[3] = nor_pos[3], nor_pos[2]
                    else:
                        nor_pos[0] += (old_w - _space * ct) * m
                        nor_pos[1] += (old_h - _space * ct) * n
                    pos.append(nor_pos + [flip, offset])
        else:
            pos.append(new_d + [flip, offset])

        lines = []
        if space_craft == 1:
            # _w, _h = (new_d[2], new_d[3]) if flip == 0 else (new_d[3], new_d[2])
            _w, _h = (new_d[2], new_d[3])
            _w, _h = _w + _space / 2, _h + _space / 2
            if not is_max_x:
                lines.append(
                    [new_d[0] + _w, new_d[1] - _space / 2, new_d[0] + _w, new_d[1] + _h]
                )
            if not is_max_y:
                lines.append(
                    [new_d[0] - _space / 2, new_d[1] + _h, new_d[0] + _w, new_d[1] + _h]
                )
        return pos, lines

    @staticmethod
    def __format_type(file: FileObj, need_customer=True):
        _cache_craft = GLOB_CONFIG.value("storage/can_work_list", type=list)
        craft = file.craft[:]
        for c in file.craft:
            for cc in _cache_craft:
                if re.compile(cc).search(c):
                    craft.remove(c)
        if need_customer:
            return "@@".join([file.customer, file.mate, ",".join(craft)])
        else:
            return "@@".join([file.mate, ",".join(craft)])

    @staticmethod
    def __new_list(data) -> List[str]:
        clr_list = List[str]()
        for item in data:
            clr_list.Add(str(item))
        return clr_list

    def _safe_move(
        self, src: str, dst: str, *, retries: int = 8, delay: float = 0.5
    ) -> bool:
        """
        尝试安全地移动文件，处理文件被占用的情况。

        - 优先使用 os.replace（尽量原子操作），再 fallback 到 shutil.move。
        - 如果遇到 PermissionError（文件被占用），会重试若干次。
        - 重试结束后尝试复制并删除源文件作为回退手段（best-effort）。
        - 返回 True 表示最终成功（移动或复制成功），False 表示失败。

        目的：缓解因外部程序（PDF 阅读器、杀毒、或 .NET 侧处理）短暂占用句柄导致的移动失败。
        """
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        except Exception:
            # 目录创建失败（例如 dst 没有父目录），继续让后续操作报告错误
            pass

        for attempt in range(1, retries + 1):
            try:
                try:
                    os.replace(src, dst)
                except Exception:
                    shutil.move(src, dst)
                return True
            except PermissionError:
                err_msg = f"目标文件被占用，移动重试 {attempt}/{retries}: {os.path.basename(src)}"
                self.message_signal.emit({"msg": err_msg})
                time.sleep(delay)
                continue
            except FileNotFoundError:
                # 源不存在，若目标已存在则认为成功
                if os.path.exists(dst):
                    return True
                return False
            except Exception as e:
                # 其它异常中断重试，转入复制回退
                self.message_signal.emit({"msg": f"移动失败：{e}，尝试复制回退"})
                break

        # 复制回退：若移动始终失败，尝试复制目标并保留源（或删除源）
        try:
            shutil.copy2(src, dst)
            # 尝试删除源文件（可能仍然被占用）
            try:
                os.remove(src)
            except Exception:
                self.message_signal.emit(
                    {
                        "msg": f"复制成功但无法删除源文件（仍被占用）：{os.path.basename(src)}"
                    }
                )
            return True
        except Exception as e:
            self.message_signal.emit({"msg": f"复制回退失败：{e}"})
            return False
