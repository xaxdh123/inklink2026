# -*- coding: utf-8 -*-
"""
run.py（PySide6 工程GUI版：子进程运行算法 + 子进程贴二维码）
- 子进程运行算法 + 子进程矢量贴码（show_pdf_page）
- 说明/停止/清空日志
- 日志高亮 + 解析 PROGRESS: a / b 更新进度条

✅ 仅使用 PySide6（已去掉 PyQt5）
"""

import os
import sys
import time
import shutil
import traceback
import subprocess
import re
from datetime import datetime

import fitz  # PyMuPDF

# ====== 两个算法脚本（必须同目录）======
import get_best5
import get_best6

# ---- 强制本进程输出编码，避免混码导致子进程/父进程互相坑 ----
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT_NAME_P1 = "over_test_p1.pdf"
OUT_NAME_P2 = "over_test_p2.pdf"

# -------------------------
# Qt imports (ONLY PySide6)
# -------------------------
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLineEdit, QPushButton, QLabel, QTextEdit, QFileDialog,
    QMessageBox, QProgressBar, QSplitter, QRadioButton, QButtonGroup,
    QFrame, QDialog
)


# -------------------------
# 工具函数
# -------------------------
def mm_to_pt(mm):
    return mm * 72.0 / 25.4


def ensure_dir(path):
    if path and (not os.path.isdir(path)):
        os.makedirs(path)


def is_output_like_pdf(filename_lower):
    if filename_lower.startswith("over_test") and filename_lower.endswith(".pdf"):
        return True
    if filename_lower.endswith("_tmp_qr.pdf"):
        return True
    if filename_lower.startswith("over_test") and ("_qr_" in filename_lower):
        return True
    return False


def list_input_pdfs(folder):
    """列出可作为输入的PDF（排除 over_test*.pdf）"""
    if not os.path.isdir(folder):
        return []
    out = []
    for fn in os.listdir(folder):
        l = fn.lower()
        if not l.endswith(".pdf"):
            continue
        if is_output_like_pdf(l):
            continue
        p = os.path.join(folder, fn)
        if os.path.isfile(p):
            out.append(p)
    out.sort()
    return out


def unique_dest_path(dst_dir, basename):
    dst = os.path.join(dst_dir, basename)
    if not os.path.exists(dst):
        return dst
    name, ext = os.path.splitext(basename)
    ts = time.strftime("%Y%m%d_%H%M%S")
    cand = os.path.join(dst_dir, "%s_%s%s" % (name, ts, ext))
    if not os.path.exists(cand):
        return cand
    idx = 1
    while True:
        cand2 = os.path.join(dst_dir, "%s_%s_%d%s" % (name, ts, idx, ext))
        if not os.path.exists(cand2):
            return cand2
        idx += 1


def pick_latest_pdf(folder):
    if not os.path.isdir(folder):
        return None
    pdfs = []
    for fn in os.listdir(folder):
        if fn.lower().endswith(".pdf"):
            p = os.path.join(folder, fn)
            try:
                pdfs.append((os.path.getmtime(p), p))
            except Exception:
                pass
    if not pdfs:
        return None
    pdfs.sort(key=lambda t: t[0], reverse=True)
    return pdfs[0][1]


def apply_paths_to_module(mod, dest_dir, archive_dir, out_dir1, out_dir2):
    """给 get_best5/get_best6 注入路径。"""
    if hasattr(mod, "set_runtime_paths"):
        try:
            mod.set_runtime_paths(dest_dir, archive_dir, out_dir1, out_dir2)
            return
        except Exception:
            pass

    if hasattr(mod, "DEST_DIR"):
        mod.DEST_DIR = dest_dir
    if hasattr(mod, "IN_PDF_ARCHIVE_DIR"):
        mod.IN_PDF_ARCHIVE_DIR = archive_dir
    if hasattr(mod, "DEST_DIR1"):
        mod.DEST_DIR1 = out_dir1
    if hasattr(mod, "DEST_DIR2"):
        mod.DEST_DIR2 = out_dir2

    if hasattr(mod, "OUT_PDF_P1"):
        try:
            mod.OUT_PDF_P1 = os.path.join(out_dir1, OUT_NAME_P1)
        except Exception:
            pass
    if hasattr(mod, "OUT_PDF_P2"):
        try:
            mod.OUT_PDF_P2 = os.path.join(out_dir2, OUT_NAME_P2)
        except Exception:
            pass
    if hasattr(mod, "OUT_PDF"):
        try:
            mod.OUT_PDF = os.path.join(out_dir1, "over_test.pdf")
        except Exception:
            pass


# -------------------------
# CLI 子进程模式：算法运行 / 贴二维码
# -------------------------
def _cli_run_algo(algo_name, work_dir, out1, out2):
    # algo_name: best1=整拼(get_best5), best2=全拼(get_best6)
    apply_paths_to_module(get_best5, work_dir, work_dir, out1, out2)
    apply_paths_to_module(get_best6, work_dir, work_dir, out1, out2)

    if algo_name == "best1":
        print("=== RUN get_best5.py (整拼) ===")
        get_best5.main()
        return 0
    else:
        print("=== RUN get_best6.py (全拼) ===")
        get_best6.main()
        return 0


def _cli_embed_qr(pdf_path, qr_pdf):
    """
    子进程贴二维码：矢量贴码 + 进度打印
    """
    if (not pdf_path) or (not os.path.isfile(pdf_path)):
        print("ERR: output pdf not found:", pdf_path)
        return 2
    if (not qr_pdf) or (not os.path.isfile(qr_pdf)):
        print("WARN: qr pdf not found, skip:", qr_pdf)
        return 0

    qr_doc = fitz.open(qr_pdf)
    if qr_doc.page_count < 1:
        qr_doc.close()
        print("WARN: qr pdf has no pages:", qr_pdf)
        return 0

    doc = fitz.open(pdf_path)
    total = doc.page_count

    w10 = mm_to_pt(10.0)
    h10 = mm_to_pt(10.0)

    print("=== EMBED QR START ===")
    print("PDF:", os.path.basename(pdf_path), "pages=", total)
    print("QR :", os.path.basename(qr_pdf))

    for i in range(total):
        page = doc.load_page(i)
        r = page.rect
        rect = fitz.Rect(r.x1 - w10, r.y0, r.x1, r.y0 + h10)
        page.show_pdf_page(rect, qr_doc, 0, overlay=True)

        if (i + 1) % 20 == 0 or (i + 1) == total:
            print("PROGRESS:", (i + 1), "/", total)

    qr_doc.close()

    # 保存（saveIncr 优先，失败再全量 save）
    print("SAVING...")
    try:
        doc.saveIncr()
        doc.close()
        print("SAVEINCR OK")
        return 0
    except Exception:
        base_dir = os.path.dirname(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        tmp_path = os.path.join(base_dir, base_name + "_tmp_qr.pdf")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        try:
            doc.save(tmp_path, garbage=0, deflate=False, incremental=False)
        finally:
            doc.close()

        try:
            os.replace(tmp_path, pdf_path)
            print("SAVE OK (replace)")
            return 0
        except PermissionError:
            ts = time.strftime("%Y%m%d_%H%M%S")
            alt = os.path.join(base_dir, base_name + "_qr_%s.pdf" % ts)
            try:
                os.replace(tmp_path, alt)
            except Exception:
                shutil.copyfile(tmp_path, alt)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            print("SAVE OK (new file):", alt)
            return 0


def _is_cli_mode():
    return ("--run-algo" in sys.argv) or ("--embed-qr" in sys.argv)


def _cli_entry():
    # 简单解析参数（避免引入 argparse）
    if "--run-algo" in sys.argv:
        i = sys.argv.index("--run-algo")
        algo = sys.argv[i + 1] if i + 1 < len(sys.argv) else "best2"

        def _get(flag, default=""):
            if flag in sys.argv:
                j = sys.argv.index(flag)
                return sys.argv[j + 1] if j + 1 < len(sys.argv) else default
            return default

        work_dir = _get("--work", "")
        out1 = _get("--out1", "")
        out2 = _get("--out2", "")

        if not work_dir or not out1 or not out2:
            print("ERR: missing args for --run-algo")
            return 2

        try:
            return _cli_run_algo(algo, work_dir, out1, out2)
        except Exception:
            print("❌ ALGO EXCEPTION:\n" + traceback.format_exc())
            return 1

    if "--embed-qr" in sys.argv:
        def _get(flag, default=""):
            if flag in sys.argv:
                j = sys.argv.index(flag)
                return sys.argv[j + 1] if j + 1 < len(sys.argv) else default
            return default

        pdf_path = _get("--pdf", "")
        qr_pdf = _get("--qr", "")
        try:
            return _cli_embed_qr(pdf_path, qr_pdf)
        except Exception:
            print("❌ EMBED EXCEPTION:\n" + traceback.format_exc())
            return 1

    return 0


# -------------------------
# Worker Thread
# -------------------------
class RunnerThread(QThread):
    sig_log = Signal(str)
    sig_status = Signal(str, str)   # status, phase
    sig_progress = Signal(float)    # 0..100
    sig_done = Signal(int)          # rc

    def __init__(self, cfg, parent=None):
        super(RunnerThread, self).__init__(parent)
        self.cfg = cfg
        self._stop = False
        self.current_proc = None

    def request_stop(self):
        self._stop = True
        self.sig_log.emit("\n⛔ 请求停止...\n")
        try:
            if self.current_proc and (self.current_proc.poll() is None):
                self.current_proc.terminate()
                self.sig_log.emit("⛔ 已发送 terminate 给子进程\n")
        except Exception:
            pass

    def _spawn_and_stream(self, cmd):
        self.sig_log.emit("CMD: %s\n" % " ".join(cmd))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        self.current_proc = p

        try:
            for line in p.stdout:
                self.sig_log.emit(line)

                # 解析进度：PROGRESS: a / b
                s = line.strip()
                m = re.search(r"PROGRESS:\s*(\d+)\s*/\s*(\d+)", s)
                if m:
                    cur = float(m.group(1))
                    tot = float(m.group(2)) if float(m.group(2)) > 0 else 1.0
                    pct = max(0.0, min(100.0, cur * 100.0 / tot))
                    self.sig_progress.emit(pct)

                if self._stop:
                    try:
                        if p.poll() is None:
                            p.terminate()
                    except Exception:
                        pass
                    break
        finally:
            try:
                p.stdout.close()
            except Exception:
                pass

        try:
            rc = p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
            rc = -1

        self.current_proc = None
        return rc

    def _transfer_input_pdfs(self, src_dir, dst_dir, mode="copy"):
        ensure_dir(dst_dir)
        files = list_input_pdfs(src_dir)
        moved = []
        for src_path in files:
            if self._stop:
                break
            base = os.path.basename(src_path)
            dst_path = unique_dest_path(dst_dir, base)
            if mode == "move":
                shutil.move(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
            moved.append(dst_path)
        return moved

    def run(self):
        try:
            cfg = self.cfg
            dest_dir = cfg["dest_dir"]
            qr_dir = cfg["qr_dir"]
            test_root = cfg["test_root"]
            out1 = cfg["out1"]
            out2 = cfg["out2"]
            mode = cfg["mode"]
            algo = cfg["algo"]

            self.sig_status.emit("Running", "Preparing")
            self.sig_progress.emit(0.0)

            ensure_dir(test_root)
            ensure_dir(out1)
            ensure_dir(out2)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            work_dir = os.path.join(test_root, "work_" + ts)
            ensure_dir(work_dir)

            self.sig_log.emit("=== CONFIG ===\n")
            self.sig_log.emit("输入PDF目录 DEST_DIR      : %s\n" % dest_dir)
            self.sig_log.emit("二维码目录 SRC_QR_DIR     : %s\n" % qr_dir)
            self.sig_log.emit("工作目录 TEST_DIR(work)   : %s\n" % work_dir)
            self.sig_log.emit("输出拼图 DEST_DIR1        : %s\n" % out1)
            self.sig_log.emit("输出刀线 DEST_DIR2        : %s\n" % out2)
            self.sig_log.emit("传输模式 TRANSFER_MODE    : %s\n" % mode)
            self.sig_log.emit("运行选择 ALGO             : %s\n" % algo)
            self.sig_log.emit("================\n\n")

            src_files = list_input_pdfs(dest_dir)
            if not src_files:
                self.sig_log.emit("⚠️ 输入目录没有可处理PDF（排除了 over_test*.pdf）：%s\n" % dest_dir)
                self.sig_done.emit(0)
                return

            # Transfer
            self.sig_status.emit("Running", "Transfer")
            self.sig_log.emit("=== TRANSFER INPUT PDFS ===\n")
            moved = self._transfer_input_pdfs(dest_dir, work_dir, mode=("move" if mode == "move" else "copy"))
            self.sig_log.emit("传输完成：%d 个PDF\n\n" % len(moved))
            if self._stop:
                self.sig_log.emit("⛔ 已停止：不再继续运行算法。\n")
                self.sig_done.emit(0)
                return

            qr_pdf = pick_latest_pdf(qr_dir)
            if qr_pdf:
                self.sig_log.emit("=== QR source === %s\n\n" % qr_pdf)
            else:
                self.sig_log.emit("⚠️ 二维码目录里没有pdf，将不贴码：%s\n\n" % qr_dir)

            # Algo subprocess
            self.sig_status.emit("Running", "Algorithm")
            self.sig_log.emit("=== RUN ALGO (SUBPROCESS) ===\n")
            cmd_algo = [
                sys.executable, "-u", os.path.abspath(__file__),
                "--run-algo", algo,
                "--work", work_dir,
                "--out1", out1,
                "--out2", out2
            ]
            rc = self._spawn_and_stream(cmd_algo)
            if self._stop:
                self.sig_log.emit("⛔ 已停止：算法阶段中断。\n")
                self.sig_done.emit(0)
                return
            if rc != 0:
                self.sig_log.emit("\n❌ 算法子进程失败 (rc=%s)\n" % rc)
                self.sig_done.emit(rc)
                return

            out_pdf1 = os.path.join(out1, OUT_NAME_P1)
            out_pdf2 = os.path.join(out2, OUT_NAME_P2)

            # Embed QR subprocess
            if qr_pdf:
                self.sig_status.emit("Running", "Embed QR")
                self.sig_progress.emit(0.0)

                if os.path.isfile(out_pdf1):
                    self.sig_log.emit("\n=== EMBED QR: P1 ===\n")
                    cmd_qr1 = [sys.executable, "-u", os.path.abspath(__file__),
                               "--embed-qr", "--pdf", out_pdf1, "--qr", qr_pdf]
                    rc1 = self._spawn_and_stream(cmd_qr1)
                    if self._stop:
                        self.sig_log.emit("⛔ 已停止：贴码阶段中断。\n")
                        self.sig_done.emit(0)
                        return
                    if rc1 != 0:
                        self.sig_log.emit("⚠️ P1贴码失败 (rc=%s)，已跳过。\n" % rc1)
                else:
                    self.sig_log.emit("⚠️ 未找到输出拼图PDF：%s\n" % out_pdf1)

                self.sig_progress.emit(0.0)
                if os.path.isfile(out_pdf2):
                    self.sig_log.emit("\n=== EMBED QR: P2 ===\n")
                    cmd_qr2 = [sys.executable, "-u", os.path.abspath(__file__),
                               "--embed-qr", "--pdf", out_pdf2, "--qr", qr_pdf]
                    rc2 = self._spawn_and_stream(cmd_qr2)
                    if self._stop:
                        self.sig_log.emit("⛔ 已停止：贴码阶段中断。\n")
                        self.sig_done.emit(0)
                        return
                    if rc2 != 0:
                        self.sig_log.emit("⚠️ P2贴码失败 (rc=%s)，已跳过。\n" % rc2)
                else:
                    self.sig_log.emit("⚠️ 未找到输出刀线PDF：%s\n" % out_pdf2)
            else:
                self.sig_log.emit("（无二维码PDF，跳过贴码）\n")

            self.sig_done.emit(0)

        except Exception:
            self.sig_log.emit("\n❌ RUNNER EXCEPTION:\n" + traceback.format_exc() + "\n")
            self.sig_done.emit(1)


# -------------------------
# Help Dialog
# -------------------------
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super(HelpDialog, self).__init__(parent)
        self.setWindowTitle("说明：全拼 vs 整拼")
        self.resize(820, 520)

        layout = QVBoxLayout(self)
        self.txt = QTextEdit(self)
        self.txt.setReadOnly(True)
        self.txt.setFont(QFont("Consolas", 11))
        layout.addWidget(self.txt)

        btn = QPushButton("返回", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

        help_text = (
            "【全拼 / 整拼 使用说明】\n\n"
            "1）全拼：适合类型少的时候，整体一起拼，效果更直观。\n"
            "   ✅ 建议：拼版类型（PDF种类）不超过 5 时使用。\n\n"
            "2）整拼：适合类型多的时候，分配更稳，整体更不容易爆页/爆内存。\n"
            "   ✅ 建议：拼版类型超过 5 时使用。\n\n"
            "【为什么类型多时用整拼更稳】\n"
            "- 类型多会导致总页数/写入量变大。\n"
            "- 贴二维码/保存 PDF 是重操作，页数越多越慢。\n\n"
            "【停止运行】\n"
            "- 点击“停止运行”会立即终止当前运行阶段（算法或贴二维码）。\n"
            "- 已生成的临时文件可能保留在输出目录，可手动删除。\n\n"
        )
        self.txt.setPlainText(help_text)


# -------------------------
# Main Window
# -------------------------
class RollWidget(QWidget):
    def __init__(self):
        super(RollWidget, self).__init__()

        self.setWindowTitle("印客链 - 拼版运行器")

        # Qt 标题栏图标：可以设置为你的 ico
        ico_path = r"C:\Users\wzqy\PycharmProjects\inklink\icon.ico"
        if os.path.isfile(ico_path):
            try:
                self.setWindowIcon(QIcon(ico_path))
            except Exception:
                pass

        self.resize(1100, 760)
        self.worker = None

        self._build_ui()
        self._apply_qss()

        # 默认值（保持你原来的）
        self.ed_dest.setText(r"D:\test_data\dest")
        self.ed_qr.setText(r"D:\test_data\src")
        self.ed_test.setText(r"D:\test_data\test")
        self.ed_out1.setText(r"D:\test_data\gest")
        self.ed_out2.setText(r"D:\test_data\pest")
        self.rb_copy.setChecked(True)
        self.rb_best2.setChecked(True)

        self._set_status("Idle", "Ready")
        self._set_progress_indeterminate(False)
        self.clear_log()

    def _apply_qss(self):
        qss = """
        QWidget { background: #0f172a; color: #e5e7eb; font-size: 12px; }
        QGroupBox {
            border: 1px solid #23304f;
            margin-top: 10px;
            border-radius: 8px;
            padding: 10px;
            background: #0b1224;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px 0 6px;
            color: #e5e7eb;
            font-weight: 600;
        }
        QLineEdit {
            background: #101b33;
            border: 1px solid #23304f;
            border-radius: 6px;
            padding: 8px;
        }
        QPushButton {
            background: #101b33;
            border: 1px solid #23304f;
            border-radius: 8px;
            padding: 10px 14px;
        }
        QPushButton:hover { background: #1f2a44; }
        QPushButton#btnStart {
            background: #3b82f6;
            border: none;
            font-weight: 700;
        }
        QPushButton#btnStart:hover { background: #2563eb; }
        QPushButton#btnStop {
            background: #ef4444;
            border: none;
            font-weight: 700;
        }
        QPushButton#btnStop:hover { background: #dc2626; }
        QTextEdit {
            background: #0b1224;
            border: 1px solid #23304f;
            border-radius: 8px;
            padding: 10px;
        }
        QProgressBar {
            background: #101b33;
            border: 1px solid #23304f;
            border-radius: 6px;
            text-align: center;
        }
        QProgressBar::chunk { background: #3b82f6; border-radius: 6px; }
        """
        self.setStyleSheet(qss)

    def _build_ui(self):
        root = QVBoxLayout()
        self.setLayout(root)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Header
        header = QFrame(self)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 12, 12, 12)
        hl.setSpacing(12)

        title_box = QVBoxLayout()
        lb_title = QLabel("印客链 - 拼版运行器")
        f = QFont("Microsoft YaHei UI", 18)
        f.setBold(True)
        lb_title.setFont(f)
        lb_sub = QLabel("子进程运行算法 + 矢量贴码（更稳）")
        lb_sub.setStyleSheet("color:#94a3b8;")
        title_box.addWidget(lb_title)
        title_box.addWidget(lb_sub)
        hl.addLayout(title_box, 1)

        st_box = QVBoxLayout()
        self.lb_status = QLabel("Idle")
        fs = QFont("Microsoft YaHei UI", 12)
        fs.setBold(True)
        self.lb_status.setFont(fs)
        self.lb_phase = QLabel("Ready")
        self.lb_phase.setStyleSheet("color:#94a3b8;")
        st_box.addWidget(self.lb_status, alignment=Qt.AlignRight)
        st_box.addWidget(self.lb_phase, alignment=Qt.AlignRight)
        hl.addLayout(st_box, 0)

        self.pb = QProgressBar()
        self.pb.setFixedWidth(280)
        self.pb.setRange(0, 100)
        self.pb.setValue(0)
        hl.addWidget(self.pb, 0, alignment=Qt.AlignVCenter)

        root.addWidget(header)

        # Splitter
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        # Left panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # Paths
        gp_paths = QGroupBox("路径配置")
        grid = QGridLayout(gp_paths)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        def add_path_row(r, label):
            lb = QLabel(label)
            ed = QLineEdit()
            btn = QPushButton("📁 选择")
            btn.clicked.connect(lambda: self._pick_dir(ed))
            grid.addWidget(lb, r, 0)
            grid.addWidget(ed, r, 1)
            grid.addWidget(btn, r, 2)
            return ed

        self.ed_dest = add_path_row(0, "输入PDF目录")
        self.ed_qr = add_path_row(1, "二维码PDF目录")
        self.ed_test = add_path_row(2, "工作根目录")
        self.ed_out1 = add_path_row(3, "输出拼图目录")
        self.ed_out2 = add_path_row(4, "输出刀线目录")
        grid.setColumnStretch(1, 1)
        left_layout.addWidget(gp_paths)

        # Options
        gp_opts = QGroupBox("运行选项")
        vopts = QVBoxLayout(gp_opts)

        row_algo = QHBoxLayout()
        row_algo.addWidget(QLabel("拼版模式："))
        self.rb_best2 = QRadioButton("全拼（<=5类型推荐）")
        self.rb_best1 = QRadioButton("整拼（>5类型更稳）")
        grp_algo = QButtonGroup(self)
        grp_algo.addButton(self.rb_best2, 2)
        grp_algo.addButton(self.rb_best1, 1)
        row_algo.addWidget(self.rb_best2)
        row_algo.addWidget(self.rb_best1)
        row_algo.addStretch(1)
        vopts.addLayout(row_algo)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("传输模式："))
        self.rb_copy = QRadioButton("复制 copy")
        self.rb_move = QRadioButton("移动 move")
        grp_mode = QButtonGroup(self)
        grp_mode.addButton(self.rb_copy, 0)
        grp_mode.addButton(self.rb_move, 1)
        row_mode.addWidget(self.rb_copy)
        row_mode.addWidget(self.rb_move)
        row_mode.addStretch(1)
        vopts.addLayout(row_mode)

        left_layout.addWidget(gp_opts)

        # Buttons
        gp_btn = QGroupBox("操作")
        hb = QHBoxLayout(gp_btn)

        self.btn_start = QPushButton("▶ 开始运行")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self.start)

        self.btn_stop = QPushButton("⛔ 停止运行")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)

        self.btn_help = QPushButton("ℹ 说明")
        self.btn_help.clicked.connect(self.show_help)

        self.btn_clear = QPushButton("🧹 清空日志")
        self.btn_clear.clicked.connect(self.clear_log)

        hb.addWidget(self.btn_start)
        hb.addWidget(self.btn_stop)
        hb.addWidget(self.btn_help)
        hb.addWidget(self.btn_clear)
        left_layout.addWidget(gp_btn)

        tip = QLabel("提示：日志自动高亮错误/警告；贴码阶段会显示真实进度。")
        tip.setStyleSheet("color:#94a3b8;")
        left_layout.addWidget(tip)
        left_layout.addStretch(1)

        splitter.addWidget(left)

        # Right panel (log)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        gp_log = QGroupBox("运行日志（子进程 stdout 实时回传）")
        vlog = QVBoxLayout(gp_log)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 11))
        vlog.addWidget(self.log)

        right_layout.addWidget(gp_log)
        splitter.addWidget(right)

        splitter.setSizes([420, 680])

    def _pick_dir(self, line_edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "选择文件夹", line_edit.text().strip() or os.getcwd())
        if d:
            line_edit.setText(d)

    def _set_status(self, status, phase):
        self.lb_status.setText(status)
        self.lb_phase.setText(phase)

    def _set_progress_indeterminate(self, on: bool):
        if on:
            self.pb.setRange(0, 0)   # busy
        else:
            self.pb.setRange(0, 100)

    @staticmethod
    def _html_escape(s):
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))

    def clear_log(self):
        self.log.clear()
        self.log.append('<span style="color:#94a3b8">Ready.</span>')

    def show_help(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def _get_algo_value(self):
        return "best1" if self.rb_best1.isChecked() else "best2"

    def _get_mode_value(self):
        return "move" if self.rb_move.isChecked() else "copy"

    def _append_log(self, s: str):
        # 高亮：CMD/✅/⚠️/❌/⛔/ERR/WARN
        line = s.rstrip("\n")
        if not line:
            self.log.append("")
            return

        color = "#e5e7eb"
        if line.startswith("CMD:"):
            color = "#60a5fa"
        elif ("❌" in line) or line.startswith("ERR:") or ("EXCEPTION" in line):
            color = "#fb7185"
        elif ("⚠️" in line) or line.startswith("WARN:"):
            color = "#fbbf24"
        elif ("✅" in line) or ("SAVEINCR OK" in line) or ("SAVE OK" in line):
            color = "#34d399"
        elif "⛔" in line:
            color = "#fbbf24"

        # 阶段推断（用于进度条 busy）
        if "=== TRANSFER INPUT PDFS" in line:
            self._set_status("Running", "Transfer")
            self._set_progress_indeterminate(True)
        elif "=== RUN ALGO" in line:
            self._set_status("Running", "Algorithm")
            self._set_progress_indeterminate(True)
        elif ("=== EMBED QR START" in line) or ("=== EMBED QR:" in line) or ("=== EMBED QR" in line):
            self._set_status("Running", "Embed QR")
            self._set_progress_indeterminate(True)
        elif "SAVING" in line:
            self._set_status("Running", "Saving")

        self.log.append(f'<span style="color:{color}">{self._html_escape(line)}</span>')

    def start(self):
        if self.worker is not None:
            return

        dest_dir = self.ed_dest.text().strip()
        qr_dir = self.ed_qr.text().strip()
        test_root = self.ed_test.text().strip()
        out1 = self.ed_out1.text().strip()
        out2 = self.ed_out2.text().strip()
        mode = self._get_mode_value()
        algo = self._get_algo_value()

        if not os.path.isdir(dest_dir):
            QMessageBox.critical(self, "错误", "输入PDF目录不存在：\n" + dest_dir)
            return
        if not test_root:
            QMessageBox.critical(self, "错误", "工作根目录不能为空")
            return
        if not os.path.isdir(qr_dir):
            QMessageBox.warning(self, "提示", "二维码目录不存在：\n%s\n将不贴二维码。" % qr_dir)

        ensure_dir(test_root)
        ensure_dir(out1)
        ensure_dir(out2)

        type_cnt = len(list_input_pdfs(dest_dir))
        if type_cnt > 5 and algo == "best2":
            QMessageBox.warning(self, "提示", "检测到类型数=%d (>5)\n建议使用【整拼】更稳。\n（已保留你的选择，不自动切换）" % type_cnt)
        if type_cnt <= 5 and algo == "best1":
            QMessageBox.information(self, "提示", "检测到类型数=%d (<=5)\n用【全拼】通常更合适。\n（已保留你的选择，不自动切换）" % type_cnt)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_status("Running", "Preparing")
        self._set_progress_indeterminate(True)
        self.pb.setValue(0)

        self.clear_log()

        cfg = {
            "dest_dir": dest_dir,
            "qr_dir": qr_dir,
            "test_root": test_root,
            "out1": out1,
            "out2": out2,
            "mode": mode,
            "algo": algo,
        }

        self.worker = RunnerThread(cfg)
        self.worker.sig_log.connect(self._append_log)
        self.worker.sig_status.connect(self._set_status)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_done.connect(self._on_done)
        self.worker.start()

    @Slot(float)
    def _on_progress(self, pct):
        # 收到 PROGRESS 时改为 determinate
        self._set_progress_indeterminate(False)
        self.pb.setValue(int(max(0.0, min(100.0, pct))))

    @Slot(int)
    def _on_done(self, rc):
        self._set_progress_indeterminate(False)
        self.pb.setValue(0)
        if rc == 0:
            self._set_status("Done", "Finished")
            self._append_log("\n✅ DONE\n")
        else:
            self._set_status("Failed", "Stopped/Error")
            self._append_log("\n❌ FAILED (rc=%s)\n" % rc)

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        try:
            self.worker.quit()
            self.worker.wait(3000)
        except Exception:
            pass
        self.worker = None

    def stop(self):
        if self.worker is None:
            return
        self._append_log("\n⛔ 请求停止...\n")
        self._set_status("Stopping", "Terminating")
        try:
            self.worker.request_stop()
        except Exception:
            pass

    def closeEvent(self, event):
        if self.worker is not None:
            ret = QMessageBox.question(
                self, "退出", "正在运行中，确定要退出吗？（会终止子进程）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            try:
                self.worker.request_stop()
            except Exception:
                pass
        event.accept()


# -------------------------
# main
# -------------------------
if __name__ == "__main__":
    # ✅ 子进程模式
    if _is_cli_mode():
        code = _cli_entry()
        raise SystemExit(int(code))

    # ✅ GUI 模式
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 11))

    w = RollWidget()
    w.show()

    sys.exit(app.exec())
