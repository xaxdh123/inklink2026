# encoding: utf-8

import copy
from PySide6.QtCore import QThread, Signal
from layout_center.ProofTS.comb.MainWorker import MainWorker
from layout_center.ProofTS.comb.FileObj import FileObj
import time
import debugpy
from utils import GLOB_CONFIG


class AutoThread(QThread):
    __sign_auto = Signal(object, name="auto")

    def __init__(self, worker: MainWorker, func):
        super(AutoThread, self).__init__()
        self.__sign_auto.connect(func)
        self.needStop = False
        self.worker = worker

    def stop(self):
        self.needStop = True

    def run(self):
        try:
            debugpy.debug_this_thread()
        except Exception:
            # Don't fail if no debugpy server is available. Continue normally.
            pass
        self.needStop = False
        while True:
            time.sleep(5)
            if self.needStop:
                self.__sign_auto.emit({"msg": "手动停止监听。", "auto_done": True})
                return
            over_time_val = int(GLOB_CONFIG.value("ui/over_time") or 3600)
            threshold = time.time() - over_time_val

            # 1. 快速读取待处理任务，缩短锁定时间
            to_process = []
            GLOB_CONFIG.beginGroup("half_quarter_page")
            try:
                keys = GLOB_CONFIG.childKeys()
                for key in keys:
                    file_kv = GLOB_CONFIG.value(key)
                    if not file_kv:
                        continue
                    min_time = min(file_kv.keys()) / 10
                    file_vs = [FileObj.from_dict(x) for x in file_kv.values()]
                    usePage = sum([x.place_way["count"] for x in file_vs])

                    if min_time <= threshold or usePage >= 1:
                        to_process.append((key, file_vs))
            finally:
                GLOB_CONFIG.endGroup()

            # 2. 在锁之外执行耗时的排版操作
            for key, file_vs in to_process:
                self.comb_files(file_vs)
                # 处理完后再移除
                GLOB_CONFIG.beginGroup("half_quarter_page")
                GLOB_CONFIG.remove(key)
                GLOB_CONFIG.endGroup()

    def comb_files(self, files: list[FileObj]):
        """
        处理文件对象，核心规则：
        1. 每个文件仅被处理一次，不重复使用；
        2. 按0.75→0.5→0.25优先级分组，每组count累加尽量补全到1；
        3. 利用迭代器“单向消耗”特性，保证元素仅遍历一次。
        """
        # 1. 生成一次性迭代器（filter返回的迭代器天然保证元素仅用一次）
        iter_075 = filter(lambda x: x.place_way["count"] == 0.75, files)
        iter_05 = filter(lambda x: x.place_way["count"] == 0.5, files)
        iter_025 = filter(lambda x: x.place_way["count"] == 0.25, files)

        # 2. 处理0.75组：1个0.75 + 1个0.25 = 1（每个元素仅取一次）
        while True:
            # 取出下一个0.75文件（取过的元素不会再被取出）
            file_075 = next(iter_075, None)
            if not file_075:
                break
            # 放置0.75文件（该文件仅被放置一次）
            last_file = self.worker.placed_file(file_075, None)
            # 尝试取1个0.25文件补全（仅取一次，取到则用，取不到则放弃）
            file_025 = next(iter_025, None)
            if file_025:
                last_file = self.worker.placed_file(file_025, last_file)
            self.worker.place_end(last_file)

        # 3. 处理0.5组：优先2个0.5=1，否则0.5+2个0.25=1（元素仅取一次）
        while True:
            # 取出第一个0.5文件（仅取一次）
            file_05 = next(iter_05, None)
            if not file_05:
                break

            # 尝试取第二个0.5文件（仅取一次）
            file_05_2 = next(iter_05, None)
            if file_05_2:
                last_file = self.worker.placed_file(file_05, None)
                last_file = self.worker.placed_file(file_05_2, last_file)
            else:
                # 取2个0.25文件补全（每个仅取一次）
                file_025 = next(iter_025, None)
                if file_025:
                    last_file = self.worker.placed_file(file_05, None)
                    last_file = self.worker.placed_file(file_025, last_file)
                    file_025_2 = next(iter_025, None)
                    if file_025_2:
                        last_file = self.worker.placed_file(file_025_2, last_file)
                else:
                    if len(file_05.pos_info) < 2:
                        file_05.pos_info[1] = copy.deepcopy(file_05.pos_info[0])
                    else:
                        file_05.pos_info[2] = copy.deepcopy(file_05.pos_info[0])
                        file_05.pos_info[3] = copy.deepcopy(file_05.pos_info[1])
                    file_05.place_way["more"] += len(file_05.pos_info[0]["print"])
                    last_file = self.worker.placed_file(file_05, None)
            self.worker.place_end(last_file)
        # 4. 处理剩余0.25组：4个一组=1（元素仅取一次）
        while True:
            # 取出第一个0.25文件（仅取一次）
            file_025 = next(iter_025, None)
            if not file_025:
                break
            iter_1b = next(iter_025, None)
            if iter_1b:
                iter_1c = next(iter_025, None)
                if iter_1c:
                    last_file = self.worker.placed_file(file_025, None)
                    last_file = self.worker.placed_file(iter_1b, last_file)
                    last_file = self.worker.placed_file(iter_1c, last_file)
                    iter_1d = next(iter_025, None)
                    if iter_1d:
                        last_file = self.worker.placed_file(iter_1d, last_file)
                else:
                    file_025.pos_info[1] = file_025.pos_info[0].copy()
                    file_025.place_way["more"] += len(file_025.pos_info[0]["print"])
                    last_file = self.worker.placed_file(file_025, None)
                    iter_1b.pos_info[1] = file_025.pos_info[0].copy()
                    iter_1b.place_way["more"] += len(iter_1b.pos_info[0]["print"])
                    last_file = self.worker.placed_file(iter_1b, last_file)
            else:
                # 循环赋值pos_info[1/2/3]，消除重复copy()
                for idx in [1, 2, 3]:
                    file_025.pos_info[idx] = file_025.pos_info[0].copy()
                # 计算more值（保持原逻辑，简化变量引用）
                file_025.place_way["more"] += len(file_025.pos_info[0]["print"]) * 3
                last_file = self.worker.placed_file(file_025, None)
            self.worker.place_end(last_file)
