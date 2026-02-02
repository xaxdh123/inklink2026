# encoding: utf-8
import glob
import io
import os
from datetime import datetime
import time
import re
import shutil
import traceback
from PySide6.QtCore import QRunnable, QThreadPool, QObject, Signal
import fitz
from utils import GLOB_CONFIG, GLOB_NETWORK

from PIL import Image
from PIL.Image import Resampling
import qrcode
import clr

clr.AddReference("System.Core")  # type: ignore
clr.AddReference(rf"resources\out-pdf\ClassLibrary1")  # type: ignore
clr.AddReference(rf"resources\out-pack\Pack")  # type: ignore
from ClassLibrary1 import Class1  # type: ignore
from System.Collections.Generic import List  # type: ignore
from System import String, Byte, Array  # type: ignore

STATIC_QR = 8
STATIC_L = 5
STATIC_T = 19
STATIC_SPACE = 6
STATIC_W = 320 - 2 * STATIC_L
STATIC_H = 464 - 2 * STATIC_T


class MyReusableTask(QObject, QRunnable):
    signal = Signal(str)

    def __init__(self, task_id, data_to_process):
        QObject.__init__(self)
        QRunnable.__init__(self)
        self.setAutoDelete(False)
        self.task_id = task_id
        self.clr_addText_stamp = Class1.AddTextStamp
        self.clr_addImg_stamp = Class1.AddQRStamp
        self.data_to_process = data_to_process
        self.needStop = False
        self.ts_no = self.data_to_process["data"][0]
        print(f"Task {self.task_id} (Data: {self.data_to_process}) initialized.")

    def stop(self):
        self.needStop = True

    def run(self):
        self.signal.emit("start")
        thread_name = QThreadPool.globalInstance().objectName() or "UnnamedThread"
        print(
            f"[{thread_name}] Task {self.task_id} (Data: {self.data_to_process}) started."
        )
        if (
            not self.data_to_process.get("size")
            or not self.data_to_process.get("pName")
            or not self.data_to_process.get("cName")
            or not self.data_to_process.get("data")
        ):
            self.signal.emit("检查 尺寸/文件/大版 信息")
            self.signal.emit("finish")
            return
        self.signal.emit("start")
        try:
            pri_path = os.path.join(
                GLOB_CONFIG.value("ui/slow_src_path"), self.data_to_process["pName"]
            )
            cut_path = os.path.join(
                GLOB_CONFIG.value("ui/slow_src_mv_path"),
                self.data_to_process["cName"],
            )
            new_name = os.path.join(
                GLOB_CONFIG.value("ui/slow_src_path"),
                f"{'-'.join(self.data_to_process['data'] + [self.data_to_process['remark']])}_手动排版.pdf",
            )
            new_name_c = os.path.join(
                GLOB_CONFIG.value("ui/slow_src_mv_path"),
                f"{self.ts_no}.pdf",
            )
            if pri_path != new_name:
                os.rename(pri_path, new_name)
            if cut_path != new_name_c:
                os.rename(cut_path, new_name_c)
            if self.needStop:
                self.signal.emit(self.ts_no + ":手动中断")
                return
            self.signal.emit(self.ts_no + ":附加 Title")
            new_name = self.place_title_A3(
                new_name,
                self.data_to_process["size"],
                [x.split("-")[0] for x in self.data_to_process["orders"]],
                self.data_to_process["remark"],
            )
            if self.needStop:
                self.signal.emit(self.ts_no + ":手动中断")
                return
            self.signal.emit(self.ts_no + ":附加 大版码")
            new_name = self.place_qr_A3_page(new_name, self.data_to_process["size"])
            if self.needStop:
                self.signal.emit(self.ts_no + ":手动中断")
                return
            self.signal.emit(self.ts_no + ":附加 订单码")
            new_name = self.place_qr_A3(
                new_name,
                self.data_to_process["size"],
                self.data_to_process["orders"][0].split("-")[0],
            )
            if self.needStop:
                self.signal.emit(self.ts_no + ":手动中断")
                return
            self.signal.emit(self.ts_no + ":移动文件至目标文件夹")
            msg = self.clr_move_file2_A3(
                int(self.data_to_process["data"][5][:-1]),
                new_name,
                new_name_c,
                self.data_to_process["orders"],
            )
            print("clr_move_file2_A3", msg)
            for path in glob.iglob(
                os.path.join(
                    GLOB_CONFIG.value("ui/slow_src_path"),
                    f"{self.ts_no}*.pdf",
                )
            ):
                if os.path.exists(path):
                    os.remove(path)
            for path in glob.iglob(
                os.path.join(
                    GLOB_CONFIG.value("ui/slow_src_mv_path"),
                    f"{self.ts_no}*.pdf",
                )
            ):
                if os.path.exists(path):
                    os.remove(path)
            self.signal.emit(f"{self.ts_no} 提交成功")
        except Exception as e:
            traceback.print_exc()
            self.signal.emit(self.ts_no + ":异常中断  " + str(e))
        print(f"[{thread_name}] Task {self.task_id} completed: {1}")
        self.signal.emit("finish")

    # 画标题
    def place_title_A3(self, r_pri, size, orders, remark):
        relation = ""
        strf_time = datetime.now().strftime("%Y-%m-%d")
        date_order_kv = GLOB_CONFIG.value("storage/data_order_no", strf_time)
        GLOB_CONFIG.beginGroup("data_order_no")
        if date_order_kv != strf_time:
            GLOB_CONFIG.setValue("storage/data_order_no", strf_time)
            for key in GLOB_CONFIG.childKeys():  # 删除每个键
                GLOB_CONFIG.remove(key)
        for order in orders:
            data_order_no: str = GLOB_CONFIG.value(order) or ""
            if not order in data_order_no.split(","):
                relation = order + ":" + data_order_no
                data_order_no = self.ts_no
            else:
                data_order_no += "," + self.ts_no
            GLOB_CONFIG.setValue(order, data_order_no)
        GLOB_CONFIG.endGroup()

        text1 = os.path.splitext(os.path.basename(r_pri))[0].split("@")[0]

        doc = fitz.open(r_pri)
        len_page = len(doc)
        try:
            STATIC_H_A3 = 420 - 2 * STATIC_T
            STATIC_W_A3 = 297 - 2 * STATIC_L
            if size == "297X420":
                x_tx, y_tx = (
                    STATIC_L + STATIC_W_A3 // 2,
                    STATIC_H_A3 + STATIC_T + STATIC_SPACE + 3,
                )
            else:
                x_tx, y_tx = (
                    STATIC_L + STATIC_W // 2,
                    STATIC_H + STATIC_T + STATIC_SPACE + 3,
                )

            text_data = List[String]()
            text_page = List[String]()
            text_remark = List[String]()

            # 准备文本数据
            if len_page > 1:
                for i in range(len_page):
                    text_data.Add(text1.replace(self.ts_no, f"{self.ts_no}_{i + 1}"))
                    text_page.Add(f"总页{len_page}  第{i + 1}页")
            else:
                text_data.Add(text1)
                text_page.Add("")  # 单页时添加空字符串

            # 准备备注文本
            for i in range(len_page):
                remark_text = remark if remark else ""
                remark_text += f"-->{relation}"
                text_remark.Add(remark_text)

            # 按顺序添加文本，确保操作符配对
            r_1 = self.clr_addText_stamp(r_pri, x_tx, y_tx, text_data)
            if r_1:
                r_2 = self.clr_addText_stamp(r_1, x_tx, y_tx - 4, text_remark)
                if r_2:
                    r_3 = self.clr_addText_stamp(r_2, x_tx, STATIC_T // 2, text_page)
                    return r_3
            return r_pri
        except:
            traceback.print_exc()
        finally:
            doc.close()
        return r_pri

    def _get_qr_bytes(self, data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=20,
            border=0,
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill="black", back_color="white")
        qr_img = qr_img.resize((200, 200), Resampling.NEAREST)
        qr_img = qr_img.convert("CMYK")
        new_data = []
        cmyk_image = Image.new("CMYK", (200, 200), (0, 0, 0, 0))
        for pix in qr_img.getdata():
            if pix[3] > 10:
                new_data.append((254, 254, 254, 254))
            else:
                new_data.append((0, 0, 0, 0))
        cmyk_image.putdata(new_data)
        byte_array = io.BytesIO()
        cmyk_image.save(byte_array, format="TIFF")
        return byte_array.getvalue()

    def place_qr_A3_page(self, r_pri, size):
        STATIC_H_A3 = 420 - 2 * STATIC_T
        if size == "297X420":
            x_no, y_no = STATIC_L + 9, STATIC_H_A3 + STATIC_T
        else:
            x_no, y_no = STATIC_L + 9, STATIC_H + STATIC_T

        doc = fitz.open(r_pri)
        len_page = len(doc)
        try:
            img_data = List[Array[Byte]]()
            if len_page > 1:
                for i in range(len_page):
                    net_bytes = Array[Byte](
                        self._get_qr_bytes(
                            f"{self.ts_no}_{i + 1}"[-10:].replace("0", "O")
                        )
                    )
                    img_data.Add(net_bytes)
            else:
                net_bytes = Array[Byte](
                    self._get_qr_bytes(self.ts_no[-10:].replace("0", "O"))
                )
                img_data.Add(net_bytes)
            r_pri = self.clr_addImg_stamp(r_pri, x_no, y_no, 8, 8, img_data)
        except:
            traceback.print_exc()
        doc.close()
        return r_pri

    # 画二维码
    def place_qr_A3(self, r_pri, size, order):
        if size == "297X420":
            STATIC_H_A3 = 420 - 2 * STATIC_T
            STATIC_W_A3 = 297 - 4 - 2 * STATIC_L
            x_so, y_so = STATIC_W_A3 - STATIC_QR, STATIC_H_A3 + STATIC_T
        else:
            x_so, y_so = STATIC_W - 4 - STATIC_QR, STATIC_H + STATIC_T
        doc = fitz.open(r_pri)
        len_page = len(doc)
        try:
            img_data = List[Array[Byte]]()
            for _ in range(len_page):
                net_bytes = Array[Byte](self._get_qr_bytes(f"{order}"))
                img_data.Add(net_bytes)
            r_pri = self.clr_addImg_stamp(r_pri, x_so, y_so, 8, 8, img_data)
        except:
            traceback.print_exc()
        doc.close()
        return r_pri

    def clr_move_file2_A3(self, num, r_pri, r_cut, history):
        strf_time = datetime.now().strftime("%Y-%m-%d")
        if num <= 2:
            last_path = "1张到2张"
        elif num <= 10:
            last_path = "3张到10张"
        elif num <= 30:
            last_path = "11张到30张"
        else:
            last_path = "大于30张"
        material = "80克铜版纸不干胶" if "80克铜版纸不干胶" in r_pri else "其他材料"
        print(material, num)
        dest_path = GLOB_CONFIG.value("ui/slow_dest_path")
        dest_path_count = os.path.join(
            dest_path, strf_time, "打印", material, last_path
        )
        if not os.path.exists(dest_path_count):
            os.makedirs(dest_path_count)
        name1, ext1 = os.path.splitext(os.path.basename(r_pri))
        goal_path = os.path.join(dest_path_count, name1.split("@")[0] + ext1)
        if os.path.exists(goal_path):
            os.remove(goal_path)
        shutil.copy(r_pri, goal_path)
        os.remove(r_pri)
        dest_path_date_dao = os.path.join(dest_path, strf_time, "刀版")
        name2, ext2 = os.path.splitext(os.path.basename(r_cut))
        if not os.path.exists(dest_path_date_dao):
            os.makedirs(dest_path_date_dao)
        cut_dest = os.path.join(dest_path_date_dao, name2.split("@")[0] + ext2)
        if os.path.exists(cut_dest):
            os.remove(cut_dest)
        shutil.copy(r_cut, cut_dest)
        os.remove(r_cut)
        dest_dao_path = GLOB_CONFIG.value("ui/slow_dest_dao_path")
        deep_cut = {}
        history = [f.split("-")[1] for f in history]
        for f in history:
            if "外框模切成型" in f:
                pattern = r"\d+x\d+"
                match1 = re.search(pattern, f)
                if match1:
                    if "外框模切成型" not in deep_cut:
                        deep_cut["外框模切成型"] = match1.group()
                    else:
                        deep_cut["外框模切成型"] += "," + match1.group()
                    f = f.replace("外框模切成型", "")
            for a in ["镂空", "模切成型", "抠出"]:
                if a in f:
                    deep_cut[a] = ""
        c_text = "-".join([x + y for x, y in deep_cut.items()])

        with fitz.open(cut_dest) as doc:
            if len(doc) == 1:
                name = name2.split("@")[0][-10:].replace("0", "O")
                if c_text:
                    name += "-" + c_text
                shutil.copy(cut_dest, os.path.join(dest_dao_path, f"{name}{ext2}"))
            else:
                for i in range(len(doc)):
                    name = f"{name2.split('@')[0]}_{i + 1}"
                    name = name[-10:].replace("0", "O")
                    if c_text:
                        name += "-" + c_text
                    output_path = os.path.join(dest_dao_path, f"{name}{ext2}")
                    with fitz.open() as new_doc:
                        new_doc.insert_pdf(doc, from_page=i, to_page=i)
                        new_doc.save(output_path)
            params = {
                "filePath": re.sub(
                    r"[A-Z]:\\新城打样",
                    lambda m: r"\\192.168.110.252\h\新城打样",
                    r_pri,
                ),
                "typesetNo": self.ts_no,
                "material": self.data_to_process["data"][2],
                "crafts": "印刷版",
                "remark": self.data_to_process["remark"],
                "width": self.data_to_process["size"].split("X")[0],
                "height": self.data_to_process["size"].split("X")[1],
                "total": num,
                "designList": [
                    {"fileName": k.split("-")[-1], "num": 1}
                    for k in self.data_to_process["orders"]
                ],
            }
            resp2 = GLOB_NETWORK.urllib_post(
                "production-api/typesettingNew/saveStickerProofingTypesetting", params
            )
            print("上传新系统返回:", resp2, params)
            if resp2["code"] != 200:
                self.signal.emit(f"新系统上传{self.ts_no}失败: {resp2.get('msg')}")
            else:
                self.signal.emit(f"为 {self.ts_no} 上传新系统 成功")

        return r_cut + " 相关大版文件已移动至对应路径"


class ApplicationManager(QObject):
    def __init__(self, func, parent=None):
        super().__init__(parent)
        # 获取全局线程池实例
        self.thread_pool = QThreadPool.globalInstance()
        print(
            f"Global Thread Pool initialized. Max thread count: {self.thread_pool.maxThreadCount()}"
        )
        self.task_count = 0
        self.task_list = []
        self.func = func

    def submit_new_task(self, data):
        """
        提交一个新的任务到线程池。
        每次调用都会创建一个新的 MyReusableTask 实例，
        并将其提交给线程池。
        """
        self.task_count += 1
        task = MyReusableTask(self.task_count, data)
        task.signal.connect(self.func)
        self.task_list.append(task)
        # 提交任务到线程池
        self.thread_pool.start(task)
        print(f"Submitted Task {self.task_count} to the thread pool.")

    def shutdown_pool(self):
        for t in self.task_list:
            t.stop()
