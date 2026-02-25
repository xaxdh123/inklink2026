import json
import os
import pathlib
import re
import shutil
import subprocess
import traceback
import json
import win32com
from PySide6.QtWidgets import QDialog

from design_center.SingleSelectDialog import SingleSelectDialog
from trayapp import constant
from utils import GLOB_CONFIG
from PySide6.QtWidgets import QDialog

class DesignUtil:
    def openDesignFile(self, path, signal):
        print("openDesignFile", path)
        if not path:
            signal.emit({"msg": "文件路径为空"})
            return
        if not os.path.exists(path):
            signal.emit({"msg": "文件不存在"})
            return
        try:
            os.startfile(path)
        except Exception as e:
            traceback.print_exc()
            signal.emit({"msg": f"文件打开失败{str(e)}"})

    def jumpToDesignFile(self, path, signal):
        print("jumpToDesignFile", path)
        if not path:
            signal.emit({"msg": "文件路径为空"})
            return
        if not self._judge_netpath_exist():
            signal.emit({"msg": f"网络路径打开失败\n{path}"})
            return
        os.makedirs(path, exist_ok=True)
        self.openDesignFile(path, signal)

    def startDesign(self, data, signal):
        print("startDesign", data)
        startDesign_option = GLOB_CONFIG.value("auth/startDesign_option") or 0
        startDesign_option = int(startDesign_option)
        dlg = SingleSelectDialog(
            [".ai", ".cdr"],
            title="请选择文件类型",
            merge_wid_visiable=len(data) > 1,
        )
        dlg.radios[startDesign_option].setChecked(True)
        dlg.merge_wid.setVisible(len(data) > 1 and not startDesign_option)
        if dlg.exec() != QDialog.Accepted:
            return
        ext_result, need_marge = dlg.get_selected()
        GLOB_CONFIG.setValue("auth/startDesign_option", 0 if ext_result == ".ai" else 1)
        id_code_list = []
        for data_item in data:
            data_item_path = data_item["designOriginPath"]
            if not self._illegal_file_name(os.path.basename(data_item_path), signal):
                continue
            dest_path = self._copy_temp_file(
                data_item_path, signal, ext_result, need_marge
            )
            if not dest_path:
                continue
            if isinstance(dest_path, str):
                self.openDesignFile(dest_path, signal)
            id_code_list.append(
                [data_item["flowDesignId"], data_item["designFileName"]]
            )
        if not len(id_code_list):
            signal.emit({"msg": "没有有效文件"})
            return
        if ext_result == ".ai" and need_marge:
            src_ai = data[0]["designOriginPath"] + ".ai"
            shutil.copy(constant.TEMP_AI_PATH, src_ai)
            jsx_text = (
                constant.MERGE_DESIGN_SCRIPT.replace(
                    "%SRC%", src_ai.replace("\\", "\\\\")
                )
                .replace("%COLS%", str(len(id_code_list)))
                .replace("%ROWS%", "1")
                .replace("%MARGIN%", "30")
                .replace(
                    "%NAMES%",
                    json.dumps(
                        [id_code[1] for id_code in id_code_list], ensure_ascii=False
                    ),
                )
            )

            # 写文件
            pathlib.Path(constant.JS_MERGE_PATH).write_text(jsx_text, encoding="utf-8")
            self._run_jsx(constant.JS_MERGE_PATH)
            self.openDesignFile(src_ai, signal)
        if ext_result == ".cdr":
            ext_result = ".CDR"
        ids = [x[0] for x in id_code_list]
        runJS = f'window.startDesign({ids}, "{ext_result}");'
        signal.emit({"runJS": runJS})

    def confirmFirstDraft(self, data, signal):
        print("confirmFirstDraft", data)
        try:
            payload = self._normalize_event_data(data)
            ids = self._extract_flow_design_ids(payload)

            if not ids:
                signal.emit({"msg": "没有有效的 flowDesignId，无法确认初稿"})
                return

            runJS = self._build_confirm_first_draft_js(ids)
            signal.emit({"runJS": runJS})

        except Exception:
            traceback.print_exc()
            signal.emit({"msg": "confirmFirstDraft 执行异常"})

    def _judge_netpath_exist(self):
        folder = r"\\truenas\data"

        def can_access_folder():
            try:
                os.listdir(folder)
                return True
            except Exception:
                return False

        def try_with_credentials(username="Admin", password="admin3.14"):
            """Windows 下通过 net use 临时挂载网络路径"""
            if os.name != "nt" or not folder.startswith("\\\\"):
                return False
            parts = folder.split("\\")
            server = parts[2] if len(parts) > 2 else None
            if not server:
                return False
            try:
                subprocess.run(
                    ["net", "use", folder, password, f"/user:{username}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                subprocess.run(
                    [
                        "cmdkey",
                        f"/add:{server}",
                        f"/user:{username}",
                        f"/pass:{password}",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return can_access_folder(folder)
            except subprocess.CalledProcessError as e:
                print("net use failed:", e.stderr)
                return False

        if can_access_folder():
            return True
        return try_with_credentials()

    def _illegal_file_name(self, filename: str, signal):
        """
        校验 Windows 文件名
        返回: (是否有效: bool, 错误信息: str | None)
        """
        if not filename:
            signal.emit({"msg": "文件路径为空"})
            return False

        if [x for x in [".", ".."] if filename.startswith(x)]:
            signal.emit({"msg": "文件路径不能是相对路径"})
            return False

        INVALID_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|\x00-\x1F]')
        if INVALID_CHARS_PATTERN.search(filename):
            signal.emit({"msg": r'文件名包含非法字符: \ / : * ? " < > | 或控制字符'})
            return False

        if filename.endswith(" ") or filename.endswith("."):
            signal.emit({"msg": "文件名不能以空格或.结尾"})
            return False

        if len(filename.encode("utf-8")) > 255:
            return False, "文件名长度不能超过 255 个字符"
        return True

    def _copy_temp_file(self, path, signal, ext="", need_marge=0):
        try:
            folder = os.path.dirname(path)
            os.makedirs(folder, exist_ok=True)
            basename = os.path.splitext(os.path.basename(path))[0]
            for _ext in [".ai", ".cdr"]:
                temp = os.path.join(folder, basename + _ext)
                if os.path.exists(temp):
                    os.remove(temp)
            basename += ext
            d_path = os.path.join(folder, basename)
            if basename.endswith(".ai") and need_marge == 0:
                shutil.copy(constant.TEMP_AI_PATH, d_path)
            elif basename.endswith(".cdr"):
                shutil.copy(constant.TEMP_CDR_PATH, d_path)
            else:
                print("合并文件不复制模版")
                return True
            return d_path
        except Exception as e:
            traceback.print_exc()
            signal.emit({"msg": f"文件复制失败{str(e)}，{path}"})
            return False

    def _run_jsx(self, jsx_path):
        res = None
        try:
            ai = win32com.client.GetActiveObject("Illustrator.Application")
        except Exception:
            try:
                ai = win32com.client.Dispatch("Illustrator.Application")
            except AttributeError:
                traceback.print_exc()
                ai = win32com.client.dynamic.Dispatch("Illustrator.Application")
        try:
            print(jsx_path)
            if os.path.exists(jsx_path):
                res = ai.DoJavaScriptFile(jsx_path)
            else:
                res = ai.DoJavaScript(jsx_path)
            print("✅ Illustrator 已执行 JSX 脚本。", res)
        except Exception as e:
            # 退而求其次：读入脚本内容执行
            print("❌ 运行失败：", e)
        return res

    def _normalize_event_data(self, data):
        if data is None:
            return []

        # 1) 如果是字符串，尝试 JSON 解析
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
            # 不是 JSON，就当作无效
                return []

        # 2) 如果是 dict，尝试取内部 data
        if isinstance(data, dict):
            inner = data.get("data", None)
            if inner is None:
            # dict 但不是我们要的结构
                return []
            data = inner

        # 3) 最终要求 list
        if not isinstance(data, list):
            return []

        return data

    def _extract_flow_design_ids(self, data_list):
        if not data_list:
            return []

        seen = set()
        ids = []
        for item in data_list:
            if not isinstance(item, dict):
                continue

            if "flowDesignId" not in item:
                continue

            fid = item.get("flowDesignId", None)
            if fid is None:
                continue

            # 清理字符串空白
            if isinstance(fid, str):
                fid = fid.strip()
                if fid == "":
                    continue
            # 纯数字字符串 -> int（更规范）
                if fid.isdigit():
                    try:
                        fid = int(fid)
                    except Exception:
                        pass

            # 去重保序：用字符串 key，避免 int/str 混用造成重复
            key = str(fid)
            if key in seen:
                continue
            seen.add(key)
            ids.append(fid)

        return ids

    def _build_confirm_first_draft_js(self, ids):

        return (
            "(function(){"
            "try{"
            "if(window && typeof window.confirmFirstDraft==='function'){"
            "window.confirmFirstDraft(%s);"
            "}else{"
            "console.warn('window.confirmFirstDraft not found');"
            "}"
            "}catch(e){console.error(e);}"
            "})();"
        ) % (ids,)
    
    def confirmFinalDraft(self, data, signal):
        try:
            items = self._cf_normalize_event_data(data)
            if not items:
                self._cf_emit(signal, {"msg": "没有有效数据"})
                return

            choice = self._cf_choose_finalize_action(signal)
            if not choice:
                return

            generated_pdf_set = set()

            # 1) 执行脚本生成PDF（Illustrator COM 导出）
            if choice == "执行脚本生成PDF":
                jobs = self._cf_build_ai_to_pdf_jobs(items)
                if not jobs:
                    self._cf_emit(signal, {"msg": "未找到可导出的 AI 文件（无法脚本生成PDF）"})
                    return

                self._cf_spinner_show()
                state = {"done": False, "ok": True, "err": ""}

                def _bg_export():
                    try:
                        for ai_path, pdf_path in jobs:
                            # 改进：若已存在 pdf，不覆盖
                            if self._cf_file_exists(pdf_path):
                                continue
                            self._cf_export_ai_to_pdf(ai_path, pdf_path)
                            generated_pdf_set.add(pdf_path)
                    except Exception as e:
                        state["ok"] = False
                        state["err"] = str(e)
                    finally:
                        state["done"] = True

                self._cf_submit_bg(_bg_export)

                self._cf_wait_done(state)

                self._cf_spinner_close()

                if not state["ok"]:
                    self._cf_emit(signal, {"msg": "脚本生成PDF失败：%s" % state["err"]})
                    return

                if not self._cf_ask_continue_finalize():
                    return

                choice = "已有PDF"  # 继续则进入上传

            # 2) 上传已有文件
            ext = self._cf_map_choice_to_ext(choice)
            if not ext:
                self._cf_emit(signal, {"msg": "未选择有效定稿类型"})
                return

            remove_set = generated_pdf_set if ext == ".pdf" else set()

            for it in items:
                ok, err = self._cf_validate_finaldraft_item(it)
                if not ok:
                    self._cf_emit(signal, {"msg": err})
                    continue

                origin = it["designOriginPath"]
                dpath = it["finalDraftDath"]
                flow_id = it["flowDesignId"]
                third_no = it["thirdOrderNo"]

                folder, short_name = self._cf_split_origin(origin)

                cand = self._cf_find_candidates(folder, short_name, ext)
                if not cand:
                    self._cf_emit(signal, {"msg": "无%s定稿文件" % short_name})
                    continue

                selected_paths = self._cf_select_candidates(cand)
                if not selected_paths:
                    continue

                self._cf_submit_bg(
                    self._cf_upload_worker,
                    selected_paths, dpath, flow_id, third_no, remove_set, signal
                )

        except Exception as e:
            self._cf_fail(signal, "confirmFinalDraft 执行异常", e)
    
    def _cf_emit(self, signal, payload):
        try:
            if hasattr(signal, "emit"):
                signal.emit(payload)
            else:
                signal(payload)
        except Exception:
            print("signal emit failed:", payload)

    def _cf_fail(self, signal, title, e=None):
        import traceback
        tb = traceback.format_exc()
        msg = title if e is None else ("%s：%s" % (title, str(e)))
        print(tb)
        self._cf_emit(signal, {"msg": msg, "detail": tb})

    def _cf_normalize_event_data(self, data):
        import json
        if data is None:
            return []
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return []
        if isinstance(data, dict):
            data = data.get("data", None)
            if data is None:
                return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _cf_choose_finalize_action(self, signal):
        try:
            from PySide6.QtWidgets import QInputDialog
            options = ["执行脚本生成PDF", "已有PDF", "已有JPG", "已有AI", "已有CDR"]
            val, ok = QInputDialog.getItem(self, "定稿方式", "请选择：", options, 0, False)
            return val if ok else None
        except Exception as e:
            self._cf_fail(signal, "无法弹出定稿方式选择框", e)
            return None

    def _cf_get_executor(self):
        from concurrent.futures import ThreadPoolExecutor
        ex = getattr(self, "_cf_executor", None)
        if ex is None:
            self._cf_executor = ThreadPoolExecutor(max_workers=4)
            ex = self._cf_executor
        return ex

    def _cf_submit_bg(self, fn, *args, **kwargs):
        try:
            return self._cf_get_executor().submit(fn, *args, **kwargs)
        except Exception:
            import traceback
            traceback.print_exc()
            return fn(*args, **kwargs)  # 提交失败就同步执行兜底

    def _cf_spinner_show(self):
        try:
            if getattr(self, "finalize_finished_ProgressBar", None):
                self.finalize_finished_ProgressBar.show()
        except Exception:
            pass

    def _cf_spinner_close(self):
        try:
            if getattr(self, "finalize_finished_ProgressBar", None):
                self.finalize_finished_ProgressBar.close()
        except Exception:
            pass

    def _cf_wait_done(self, state_dict):
        from PySide6.QtWidgets import QApplication
        while not state_dict.get("done", False):
            QApplication.processEvents()

    def _cf_ask_continue_finalize(self):
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "继续定稿", "PDF 已生成，是否继续执行定稿上传？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            return reply != QMessageBox.StandardButton.No
        except Exception:
            return False

    def _cf_map_choice_to_ext(self, choice):
        if choice == "已有PDF":
            return ".pdf"
        if choice == "已有JPG":
            return ".jpg"
        if choice == "已有AI":
            return ".ai"
        if choice == "已有CDR":
            return ".cdr"
        return ""

    def _cf_validate_finaldraft_item(self, item):
        need = ["designOriginPath", "finalDraftDath", "flowDesignId", "thirdOrderNo"]
        for k in need:
            if k not in item or item.get(k) in (None, ""):
                return False, "缺少字段：%s" % k
        return True, ""

    def _cf_split_origin(self, origin_path):
        import os
        folder, filename = os.path.split(origin_path)
        short_name = os.path.splitext(filename)[0]
        return folder, short_name

    def _cf_file_exists(self, path):
        import os
        try:
            return os.path.exists(path)
        except Exception:
            return False

    def _cf_find_candidates(self, folder, short_name, ext):
        import os
        out = {}
        if not folder or not os.path.isdir(folder) or not short_name or not ext:
            return out
        short_low = short_name.lower()
        ext_low = ext.lower()
        try:
            names = os.listdir(folder)
        except Exception:
            return out

        for fn in sorted(names, key=lambda x: x.lower()):
            f = fn.lower()
            if not f.startswith(short_low):
                continue
            if not f.endswith(ext_low):
                continue
            full = os.path.join(folder, fn)
            if os.path.isfile(full):
                key = fn
                if key in out:
                    i = 2
                    while ("%s (%d)" % (fn, i)) in out:
                        i += 1
                    key = "%s (%d)" % (fn, i)
                out[key] = full
        return out

    def _cf_select_candidates(self, cand_dict):
        keys = list(cand_dict.keys())
        if len(keys) == 1:
            return [cand_dict[keys[0]]]

        try:
            from PySide6.QtWidgets import (
                QDialog, QVBoxLayout, QDialogButtonBox, QScrollArea, QWidget, QCheckBox
            )
            dlg = QDialog(self)
            dlg.setWindowTitle("含有多个定稿文件请选择")
            dlg.setModal(True)
            root = QVBoxLayout(dlg)

            scroll = QScrollArea(dlg)
            scroll.setWidgetResizable(True)
            inner = QWidget(scroll)
            v = QVBoxLayout(inner)

            checks = []
            for k in keys:
                cb = QCheckBox(str(k))
                v.addWidget(cb)
                checks.append((k, cb))

            inner.setLayout(v)
            scroll.setWidget(inner)
            root.addWidget(scroll)

            box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
            box.accepted.connect(dlg.accept)
            box.rejected.connect(dlg.reject)
            root.addWidget(box)

            if dlg.exec() != QDialog.Accepted:
                return []

            out = []
            for k, cb in checks:
                if cb.isChecked():
                    out.append(cand_dict[k])
            return out

        except Exception:
            return []

    def _cf_build_ai_to_pdf_jobs(self, items):
        import os
        jobs = []
        for it in items:
            origin = it.get("designOriginPath", "")
            if not origin:
                continue
            folder = os.path.dirname(origin)
            base = os.path.splitext(os.path.basename(origin))[0]

            ai_path = os.path.join(folder, base + ".ai")
            if not os.path.exists(ai_path) and origin.lower().endswith(".ai") and os.path.exists(origin):
                ai_path = origin

            if os.path.exists(ai_path):
                pdf_path = os.path.join(folder, base + ".pdf")
                jobs.append((ai_path, pdf_path))
        return jobs

    def _cf_export_ai_to_pdf(self, ai_path, pdf_path):
        """
        Windows + 安装 Illustrator 才能用。
        若缺 pywin32，会提示你安装。
        """
        import os
        try:
            import pythoncom
            import win32com.client
            from win32com.client import gencache
        except Exception as e:
            raise RuntimeError("缺少 pywin32/pythoncom，请先安装：pip install pywin32；%s" % e)

        pythoncom.CoInitialize()
        ai = None
        try:
            gencache.Rebuild()
            ai = win32com.client.Dispatch("Illustrator.Application")
            doc = ai.Open(os.path.abspath(ai_path))
            pdf_opt = win32com.client.Dispatch("Illustrator.PDFSaveOptions")
            doc.SaveAs(os.path.abspath(pdf_path), pdf_opt)
            doc.Close(2)  # 2 = 不保存更改
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _cf_build_update_fs_path_js(self, flow_id, dest_path):
        p = (dest_path or "").replace("\\", "\\\\")
        return (
            "(function(){try{"
            "if(window && typeof window.updateFsPath==='function'){"
            "window.updateFsPath(\"%s\",\"%s\");"
            "}else{console.warn('window.updateFsPath not found');}"
            "}catch(e){console.error(e);}})();"
        ) % (flow_id, p)

    def _cf_upload_worker(self, src_paths, dpath, flow_id, third_no, remove_set, signal):
        import os, shutil
        try:
            try:
                os.makedirs(dpath, exist_ok=True)
            except Exception:
                pass

            try:
                is_voucher = self.voucher_judgment() if hasattr(self, "voucher_judgment") else False
            except Exception:
                is_voucher = False

            last_dest = ""
            for src in src_paths:
                dest = os.path.join(dpath, os.path.basename(src))
                need_remove = (src in remove_set)

                if hasattr(self, "copy_final_file") and callable(getattr(self, "copy_final_file")):
                    self.copy_final_file(src, dest, flow_id, third_no, is_voucher, need_remove)
                else:
                    shutil.copy(src, dest)
                    if need_remove:
                        try:
                            os.remove(src)
                        except Exception:
                            pass

                last_dest = dest

            if last_dest:
                runJS = self._cf_build_update_fs_path_js(flow_id, last_dest)
                self._cf_emit(signal, {"runJS": runJS})

        except Exception as e:
            self._cf_fail(signal, "上传定稿文件失败", e)
