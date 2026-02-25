# -*- coding: utf-8 -*-
"""
get_best1.py（单组拼版）
- 支持被 run.py 以 run(cfg=..., input_pdfs=..., progress_cb=..., log_cb=...) 调用
- 也支持自己单独运行（会按默认目录扫描）

✅ 更新点（按你的要求）：
- 识别整个 PDF 文档，不再只处理 1/2 页
- 按页对规则处理：2n 页是“图形轮廓”，2n-1 页是“图形本身”
- 对每一对 (2n-1, 2n)：
  - 用 2n 页识别 ref_bbox（轮廓 bbox）
  - 2n-1、2n 都按该 ref_bbox 进行裁剪/插图
  - 结果分别写入 out1 / out2（对应奇数页输出/偶数页输出）

依赖：
pip install pymupdf pillow numpy opencv-python pyside6
"""

import os
import re
import math
import time
import shutil

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

try:
    import cv2
    CV2_OK = True
except Exception:
    CV2_OK = False


# =========================
# 目录与输出（✅ 改为可由 run.py 动态注入）
# =========================
DEST_DIR = r"D:\test_data\dest"
IN_PDF_ARCHIVE_DIR = r"D:\test_data\test"
DEST_DIR1 = r"D:\test_data\gest"
DEST_DIR2 = r"D:\test_data\pest"

OUT_PDF_P1 = os.path.join(DEST_DIR1, "over_test_p1.pdf")
OUT_PDF_P2 = os.path.join(DEST_DIR2, "over_test_p2.pdf")


def set_runtime_paths(dest_dir, archive_dir, out_dir1, out_dir2):
    """
    ✅ 给 run.py 调用：动态设置路径（打包后不用改代码，只在窗口里选）
    """
    global DEST_DIR, IN_PDF_ARCHIVE_DIR, DEST_DIR1, DEST_DIR2, OUT_PDF_P1, OUT_PDF_P2

    DEST_DIR = str(dest_dir)
    IN_PDF_ARCHIVE_DIR = str(archive_dir)
    DEST_DIR1 = str(out_dir1)
    DEST_DIR2 = str(out_dir2)

    OUT_PDF_P1 = os.path.join(DEST_DIR1, "over_test_p1.pdf")
    OUT_PDF_P2 = os.path.join(DEST_DIR2, "over_test_p2.pdf")


# =========================
# 工艺/约束参数
# =========================
BLOCK_MAX_W = 320
BLOCK_MAX_H = 460

GAP = 6
MARGIN = 11.0

OUTER_EXT = 2.0
INNER_GAP = 3.0
INNER_MARGIN_MM = OUTER_EXT + INNER_GAP  # 固定 5mm

H_MIN, H_MAX = 570, 590
W_MAX = 1000

QR_BAND = 10
QR_W = 10
QR_H = 10

MARK_LEN = 10
LABEL_FONT_SIZE = 10

RENDER_DPI = 600
CROP_PAD_MM = 1.20  # 裁剪防抠边（固定毫米）


# =========================
# 基础工具
# =========================
def mm_to_pt(mm):
    return mm * 72.0 / 25.4

def mm_to_px(mm, dpi):
    return int(round(mm * dpi / 25.4))

def H_usable(H_sheet):
    return H_sheet - QR_BAND

def cap_block(dim_mm, block_max_mm):
    dim = float(dim_mm)
    if dim <= 0:
        return 0
    cap = int(block_max_mm // dim)
    return cap if cap >= 1 else 0

def ceil_div(a, b):
    return (a + b - 1) // b

def ensure_dir(p):
    if p and (not os.path.isdir(p)):
        os.makedirs(p)

def _log(log_cb, s):
    if log_cb:
        log_cb(s)
    else:
        print(s)


# =========================
# ✅ 把进入拼接的PDF复制到指定目录（可选：run.py已传就不需要）
# =========================
def archive_input_pdf_to_dir(src_pdf_path, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)

    base = os.path.basename(src_pdf_path)
    dst_path = os.path.join(dst_dir, base)

    try:
        if os.path.abspath(src_pdf_path).lower() == os.path.abspath(dst_path).lower():
            return dst_path
    except Exception:
        pass

    if os.path.exists(dst_path):
        try:
            if os.path.getsize(dst_path) == os.path.getsize(src_pdf_path):
                return dst_path
        except Exception:
            pass
        name, ext = os.path.splitext(base)
        ts = time.strftime("%Y%m%d_%H%M%S")
        dst_path = os.path.join(dst_dir, "%s_%s%s" % (name, ts, ext))

    shutil.copy2(src_pdf_path, dst_path)
    return dst_path


# =========================
# 文件名解析：第7个^后的 A*B^N
# =========================
def parse_A_B_N_from_filename(pdf_path):
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    parts = base.split("^")

    if len(parts) >= 9:
        size_part = parts[7]
        n_part = parts[8]
    else:
        size_part = None
        n_part = None
        for i in range(len(parts) - 1):
            if re.search(r"\d+(\.\d+)?\s*[\*xX]\s*\d+(\.\d+)?", parts[i]) and re.search(r"\d+", parts[i + 1]):
                size_part = parts[i]
                n_part = parts[i + 1]
                break
        if size_part is None or n_part is None:
            raise ValueError("无法从文件名解析 A*B^N：%s" % base)

    m = re.search(r"(\d+(\.\d+)?)\s*[\*xX]\s*(\d+(\.\d+)?)", size_part)
    if not m:
        raise ValueError("尺寸段不是 A*B 格式：%s" % size_part)

    A = float(m.group(1))
    B = float(m.group(3))

    m2 = re.search(r"(\d+)", n_part)
    if not m2:
        raise ValueError("数量段不是 N 格式：%s" % n_part)
    N = int(m2.group(1))

    if A <= 0 or B <= 0 or N <= 0:
        raise ValueError("解析到的 A/B/N 非法：A=%s B=%s N=%s" % (A, B, N))

    return A, B, N


def build_group_title_from_filename(pdf_path, pages_count):
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    parts = base.split("^")

    if len(parts) >= 2:
        left = "^".join(parts[:2])
    else:
        left = base

    right = "^".join(parts[9:]) if len(parts) >= 10 else ""
    title = left
    if right:
        title += "-" + right
    title += "-" + str(int(pages_count))
    return title


# =========================
# ✅ 渲染：支持复用已打开的 doc（避免重复 open/close）
# =========================
def render_page_to_pil(pdf_path, page_index=0, dpi=RENDER_DPI, doc=None):
    close_doc = False
    if doc is None:
        doc = fitz.open(pdf_path)
        close_doc = True

    try:
        if doc.page_count <= page_index:
            raise ValueError("PDF页数不足：%s 需要页=%d 实际=%d" % (pdf_path, page_index + 1, doc.page_count))
        page = doc.load_page(page_index)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        if close_doc:
            doc.close()


# =========================
# bbox 识别（多策略 + 兜底）
# =========================
def _bbox_from_mask(mask, W, H):
    ys, xs = np.where(mask > 0)
    if xs.size < 80 or ys.size < 80:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    if (x1 - x0) >= 0.99 * W and (y1 - y0) >= 0.99 * H:
        return None
    return (x0, y0, x1, y1)

def _reject_border_bbox(x, y, w, h, W, H):
    edge_pad = 8
    touches_edge = (x <= edge_pad or y <= edge_pad or (x + w) >= (W - edge_pad) or (y + h) >= (H - edge_pad))
    huge = (w >= 0.98 * W and h >= 0.98 * H)
    return touches_edge and huge

def _bbox_from_contours_union(mask, W, H):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    bboxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < max(10, int(W * 0.01)) or h < max(10, int(H * 0.01)):
            continue
        if _reject_border_bbox(x, y, w, h, W, H):
            continue
        bboxes.append((w * h, x, y, w, h))

    if not bboxes:
        return None

    bboxes.sort(key=lambda t: t[0], reverse=True)
    max_area = float(bboxes[0][0])

    keep = []
    for area, x, y, w, h in bboxes[:30]:
        if float(area) >= 0.10 * max_area:
            keep.append((x, y, x + w, y + h))

    if not keep:
        _, x, y, w, h = bboxes[0]
        return (x, y, x + w, y + h)

    x0 = min(k[0] for k in keep)
    y0 = min(k[1] for k in keep)
    x1 = max(k[2] for k in keep)
    y1 = max(k[3] for k in keep)
    return (int(x0), int(y0), int(x1), int(y1))

def find_outer_bbox(pil_img):
    arr = np.array(pil_img.convert("RGB"))
    H, W = arr.shape[0], arr.shape[1]

    if not CV2_OK:
        gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)
        for thr in [250, 245, 240, 235]:
            mask = (gray < thr).astype(np.uint8) * 255
            bbox = _bbox_from_mask(mask, W, H)
            if bbox:
                return bbox
        return (0, 0, W, H)

    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates = []

    # A: 自适应阈值
    try:
        thA = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35, 5
        )
        thA = cv2.morphologyEx(thA, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        thA = cv2.dilate(thA, np.ones((3, 3), np.uint8), iterations=1)
        bboxA = _bbox_from_contours_union(thA, W, H)
        if bboxA:
            candidates.append(bboxA)
    except Exception:
        pass

    # B: Otsu
    try:
        _, thB = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thB = cv2.morphologyEx(thB, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        thB = cv2.dilate(thB, np.ones((3, 3), np.uint8), iterations=1)
        bboxB = _bbox_from_contours_union(thB, W, H)
        if bboxB:
            candidates.append(bboxB)
    except Exception:
        pass

    # C: Canny
    try:
        edges = cv2.Canny(blur, 50, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)
        bboxC = _bbox_from_contours_union(edges, W, H)
        if bboxC:
            candidates.append(bboxC)
    except Exception:
        pass

    # D: 非白兜底
    try:
        for thr in [250, 245, 240, 235]:
            maskD = (gray < thr).astype(np.uint8) * 255
            maskD = cv2.morphologyEx(maskD, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
            bboxD = _bbox_from_mask(maskD, W, H)
            if bboxD:
                candidates.append(bboxD)
                break
    except Exception:
        pass

    if not candidates:
        return (0, 0, W, H)

    best = None
    best_area = None
    for (x0, y0, x1, y1) in candidates:
        bw, bh = (x1 - x0), (y1 - y0)
        if bw <= 0 or bh <= 0:
            continue
        if bw >= 0.99 * W and bh >= 0.99 * H:
            continue
        area = bw * bh
        if best_area is None or area > best_area:
            best_area = area
            best = (x0, y0, x1, y1)

    return best if best is not None else candidates[0]


def adjust_bbox_to_target_ratio(x0, y0, x1, y1, img_w, img_h, target_ratio):
    bw = x1 - x0
    bh = y1 - y0
    if bw <= 0 or bh <= 0:
        return x0, y0, x1, y1

    cur_ratio = bw / float(bh)

    if cur_ratio > target_ratio:
        new_bh = int(math.ceil(bw / target_ratio))
        delta = new_bh - bh
        top = delta // 2
        bottom = delta - top
        y0n = max(0, y0 - top)
        y1n = min(img_h, y1 + bottom)
        need = new_bh - (y1n - y0n)
        if need > 0:
            y0n = max(0, y0n - need)
        return x0, y0n, x1, y1n
    else:
        new_bw = int(math.ceil(bh * target_ratio))
        delta = new_bw - bw
        left = delta // 2
        right = delta - left
        x0n = max(0, x0 - left)
        x1n = min(img_w, x1 + right)
        need = new_bw - (x1n - x0n)
        if need > 0:
            x0n = max(0, x0n - need)
        return x0n, y0, x1n, y1

def clamp_bbox(x0, y0, x1, y1, img_w, img_h):
    x0 = max(0, min(img_w - 1, int(x0)))
    y0 = max(0, min(img_h - 1, int(y0)))
    x1 = max(x0 + 1, min(img_w, int(x1)))
    y1 = max(y0 + 1, min(img_h, int(y1)))
    return x0, y0, x1, y1

# =========================
# ✅ ref-guided bbox refine（避免用轮廓bbox裁实图时抠边）
# =========================
REFINE_SEARCH_PAD_MMS = [1.0, 2.0, 3.5, 5.0]   # 逐步扩大搜索窗口（mm）
EDGE_TOUCH_PX = 2                               # bbox 贴到窗口边缘就认为可能被截断
LOCAL_FAIL_MIN_PIX = 20                         # 太小的bbox视为失败


def _expand_bbox_px(bbox, pad_px, W, H):
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad_px)
    y0 = max(0, y0 - pad_px)
    x1 = min(W, x1 + pad_px)
    y1 = min(H, y1 + pad_px)
    return (int(x0), int(y0), int(x1), int(y1))


def _bbox_is_full(bbox, W, H):
    if bbox is None:
        return True
    x0, y0, x1, y1 = bbox
    return (x0 <= 0 and y0 <= 0 and x1 >= W and y1 >= H)


def _bbox_touches_window_edge(local_bbox, win_w, win_h, edge_px=EDGE_TOUCH_PX):
    if local_bbox is None:
        return True
    x0, y0, x1, y1 = local_bbox
    # 贴边（或非常接近边）=> 可能窗口不够大导致被截断
    if x0 <= edge_px or y0 <= edge_px:
        return True
    if (win_w - x1) <= edge_px or (win_h - y1) <= edge_px:
        return True
    return False


def _valid_local_bbox(local_bbox):
    if local_bbox is None:
        return False
    x0, y0, x1, y1 = local_bbox
    return (x1 - x0) >= LOCAL_FAIL_MIN_PIX and (y1 - y0) >= LOCAL_FAIL_MIN_PIX


def _refine_bbox_by_window(img_pil, init_bbox, dpi):
    """
    init_bbox：已经在目标页像素坐标系下的 bbox（来自 ref_bbox 缩放后的结果）
    做法：用 init_bbox 当“定位窗口”，窗口内对目标页再次 find_outer_bbox，
         若 bbox 贴边就扩大窗口重试，直到拿到不贴边的 bbox。
    返回：更贴合目标页的 bbox（全图坐标系）
    """
    W, H = img_pil.size
    if init_bbox is None:
        return None

    # 先 clamp 一次
    x0, y0, x1, y1 = clamp_bbox(init_bbox[0], init_bbox[1], init_bbox[2], init_bbox[3], W, H)
    init_bbox = (x0, y0, x1, y1)

    for pad_mm in REFINE_SEARCH_PAD_MMS:
        pad_px = mm_to_px(pad_mm, dpi)
        win = _expand_bbox_px(init_bbox, pad_px, W, H)
        wx0, wy0, wx1, wy1 = win
        win_img = img_pil.crop((wx0, wy0, wx1, wy1))

        local = find_outer_bbox(win_img)
        win_w, win_h = win_img.size

        # find_outer_bbox 可能返回整窗（失败兜底），这种直接视为失败
        if _bbox_is_full(local, win_w, win_h) or (not _valid_local_bbox(local)):
            continue

        # 如果 local bbox 贴边，说明窗口可能还不够大，继续扩大窗口重试
        if _bbox_touches_window_edge(local, win_w, win_h, edge_px=EDGE_TOUCH_PX):
            continue

        # 转回全图坐标
        lx0, ly0, lx1, ly1 = local
        return (wx0 + lx0, wy0 + ly0, wx0 + lx1, wy0 + ly1)

    # 全失败：回退用 init_bbox
    return init_bbox


def _union_bbox(b1, b2):
    if b1 is None:
        return b2
    if b2 is None:
        return b1
    x0 = min(b1[0], b2[0])
    y0 = min(b1[1], b2[1])
    x1 = max(b1[2], b2[2])
    y1 = max(b1[3], b2[3])
    return (x0, y0, x1, y1)

def _content_touches_edges(pil_rgba, thr=250, margin_px=2):
    """
    判断裁剪结果是否“贴边”（贴边通常意味着还在抠边）
    thr 越大越敏感；margin_px 是边缘检测厚度
    """
    arr = np.array(pil_rgba.convert("RGB"))
    gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)
    m = margin_px
    if m <= 0:
        m = 1
    mask = (gray < thr)  # 非白
    if mask[:m, :].any():
        return True
    if mask[-m:, :].any():
        return True
    if mask[:, :m].any():
        return True
    if mask[:, -m:].any():
        return True
    return False

def _expand_bbox_px(bbox, exp_px, img_w, img_h):
    x0, y0, x1, y1 = bbox
    x0 -= exp_px
    y0 -= exp_px
    x1 += exp_px
    y1 += exp_px
    return clamp_bbox(x0, y0, x1, y1, img_w, img_h)


def make_part_png_bytes_using_ref_bbox(pdf_path, page_index, inner_w_mm, inner_h_mm,
                                      ref_bbox, ref_size, dpi=RENDER_DPI, doc=None):
    """
    ✅ 修正版：
    - bbox = scaled(ref_bbox) 与 target页自身 bbox 的并集（更不容易削边）
    - CROP_PAD_MM 用更大的“安全padding”
    - 裁剪后做贴边自检：贴边就自动再扩一点（最多2次）
    """
    pad_px = mm_to_px(CROP_PAD_MM, dpi)

    img = render_page_to_pil(pdf_path, page_index=page_index, dpi=dpi, doc=doc)
    img_w, img_h = img.size

    # 1) 目标页自身 bbox（很关键：避免 ref_bbox 偏小导致削边）
    bbox_self = None
    try:
        bbox_self = find_outer_bbox(img)
    except Exception:
        bbox_self = None

    # 2) 参考页 bbox -> 缩放到目标页尺寸
    bbox_ref_scaled = None
    if (ref_bbox is not None) and (ref_size is not None):
        try:
            ref_w, ref_h = ref_size
            sx = img_w / float(ref_w)
            sy = img_h / float(ref_h)
            x0, y0, x1, y1 = ref_bbox
            x0 = int(round(x0 * sx)); x1 = int(round(x1 * sx))
            y0 = int(round(y0 * sy)); y1 = int(round(y1 * sy))
            bbox_ref_scaled = (x0, y0, x1, y1)
        except Exception:
            bbox_ref_scaled = None

    # 3) 取并集（更“宽松”，不抠边）
    bbox = _union_bbox(bbox_ref_scaled, bbox_self)
    if bbox is None:
        # 兜底：整页
        bbox = (0, 0, img_w, img_h)

    # 4) 先按安全 padding 扩一圈
    x0, y0, x1, y1 = bbox
    x0 -= pad_px; y0 -= pad_px; x1 += pad_px; y1 += pad_px
    x0, y0, x1, y1 = clamp_bbox(x0, y0, x1, y1, img_w, img_h)

    # 5) 自检：如果裁完“贴边”，说明还在削边 -> 再扩一点重裁（最多2次）
    for _ in range(2):
        crop = img.crop((x0, y0, x1, y1)).convert("RGBA")
        if not _content_touches_edges(crop, thr=250, margin_px=2):
            break
        # 贴边了：再扩 0.6mm（按像素）
        extra_px = mm_to_px(0.60, dpi)
        x0, y0, x1, y1 = _expand_bbox_px((x0, y0, x1, y1), extra_px, img_w, img_h)

    from io import BytesIO
    bio = BytesIO()
    crop.save(bio, format="PNG", optimize=True)
    return bio.getvalue()


# =========================
# 纵向排满
# =========================
def max_rows_fit(h_mm, capy, H_sheet):
    Huse = H_usable(H_sheet)
    avail = Huse - 2 * MARGIN
    h = float(h_mm)

    if avail < h:
        return 0, 0.0, float(Huse)

    best_rows = 0
    best_s = 0

    for s in range(1, 10000):
        avail_rows_height = avail - GAP * (s - 1)
        if avail_rows_height < h:
            break
        rows_fit = int(avail_rows_height // h)
        if rows_fit <= (s - 1) * capy:
            continue
        rows = min(rows_fit, s * capy)
        if rows > best_rows:
            best_rows = rows
            best_s = s

    used_content = best_rows * h + GAP * (best_s - 1)
    used_total = used_content + 2 * MARGIN
    blank = Huse - used_total
    return int(best_rows), float(used_total), float(blank)

def groups_for_k(capx, k):
    m = int(math.ceil(k / float(capx)))
    groups = [capx] * (m - 1)
    last = k - (m - 1) * capx
    if last <= 0 or last > capx:
        return None, None
    groups.append(last)
    return m, groups

def build_fullsheet_placements(type_name, z, h, capy, groups, rows_max):
    placements = []
    for r in range(rows_max):
        seg_idx = r // capy
        y = MARGIN + r * h + seg_idx * GAP

        x = MARGIN
        for gi, gsz in enumerate(groups):
            for _ in range(gsz):
                placements.append({"type": type_name, "x": x, "y": y, "w": z, "h": h})
                x += z
            if gi != len(groups) - 1:
                x += GAP
    return placements

def choose_first_row_leftmost_placement(placements):
    if not placements:
        return None
    max_top = None
    for p in placements:
        top = p["y"] + p["h"]
        if (max_top is None) or (top > max_top):
            max_top = top
    best = None
    for p in placements:
        if abs((p["y"] + p["h"]) - max_top) <= 1e-6:
            if best is None or p["x"] < best["x"]:
                best = p
    return best

def pick_cjk_fontfile():
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def trim_text_to_width(text, fontsize, max_width_pt):
    est = 0.55 * fontsize * len(text)
    if est <= max_width_pt:
        return text
    keep = max(0, int(max_width_pt / (0.55 * fontsize)) - 3)
    if keep <= 0:
        return "..."
    return text[:keep] + "..."

def draw_title_above_outer5mm(page, title, host_outer_rect, fontsize):
    band_h_mm = 5.0
    pad_x = mm_to_pt(1.0)
    x = host_outer_rect.x0 + pad_x
    baseline_in_band_mm = 3.8
    y = host_outer_rect.y0 - mm_to_pt(band_h_mm - baseline_in_band_mm)
    if y < mm_to_pt(2.0):
        y = mm_to_pt(2.0)

    max_w = (host_outer_rect.x1 - host_outer_rect.x0) - 2 * pad_x
    title2 = trim_text_to_width(title, fontsize, max_w)

    fontfile = pick_cjk_fontfile()
    if fontfile:
        page.insert_text(fitz.Point(x, y), title2, fontsize=fontsize, fontfile=fontfile, color=(0, 0, 0))
    else:
        page.insert_text(fitz.Point(x, y), title2, fontsize=fontsize, fontname="helv", color=(0, 0, 0))

def compute_x_edges_from_placements(placements):
    xs = set()
    for p in placements:
        xs.add(int(round(p["x"])))
        xs.add(int(round(p["x"] + p["w"])))
    return sorted(xs)

def compute_y_edges_from_placements(placements):
    ys = set()
    for p in placements:
        ys.add(int(round(p["y"])))
        ys.add(int(round(p["y"] + p["h"])))
    return sorted(ys)

def solve_single_type_template(part_size, need_count):
    w0, h0 = int(part_size[0]), int(part_size[1])
    best = None

    for ori in (0, 1):
        z = w0 if ori == 0 else h0
        h = h0 if ori == 0 else w0

        capx = cap_block(z, BLOCK_MAX_W)
        capy = cap_block(h, BLOCK_MAX_H)
        if capx <= 0 or capy <= 0:
            continue

        k_upper = int((W_MAX - 2 * MARGIN) // z) + 2
        if k_upper < 1:
            continue

        for k in range(1, k_upper + 1):
            m, groups = groups_for_k(capx, k)
            if groups is None:
                continue

            if any((g * z) > BLOCK_MAX_W for g in groups):
                continue

            R = k * z + GAP * (m - 1)
            W_sheet = R + 2 * MARGIN
            if W_sheet > W_MAX:
                break

            for H_sheet in range(H_MIN, H_MAX + 1):
                rows_max, usedH, blank = max_rows_fit(h, capy, H_sheet)
                if rows_max <= 0:
                    continue

                cap_sheet = rows_max * k
                pages = int(math.ceil(need_count / float(cap_sheet)))
                total_area = pages * (W_sheet * H_sheet)

                cand = {
                    "ori": ori,
                    "z": z, "h": h,
                    "capx": capx, "capy": capy,
                    "k": k,
                    "groups": groups,
                    "R": R,
                    "W_sheet": float(W_sheet),
                    "H_sheet": float(H_sheet),
                    "rows_max": int(rows_max),
                    "cap_sheet": int(cap_sheet),
                    "pages": int(pages),
                    "total_area": float(total_area),
                    "blank": float(blank),
                }

                if best is None:
                    best = cand
                else:
                    if cand["total_area"] < best["total_area"] - 1e-9:
                        best = cand
                    elif abs(cand["total_area"] - best["total_area"]) <= 1e-9:
                        if cand["H_sheet"] < best["H_sheet"] - 1e-9:
                            best = cand
                        elif abs(cand["H_sheet"] - best["H_sheet"]) <= 1e-9:
                            if cand["W_sheet"] < best["W_sheet"] - 1e-9:
                                best = cand
                            elif abs(cand["W_sheet"] - best["W_sheet"]) <= 1e-9:
                                if cand["blank"] < best["blank"] - 1e-9:
                                    best = cand

    return best

def append_group_pages(out_doc, best, placements, pages, title, img_bytes):
    W = best["W_sheet"]
    H = best["H_sheet"]
    Wpt = mm_to_pt(W)
    Hpt = mm_to_pt(H)

    inner_margin = float(INNER_MARGIN_MM)  # 固定 5mm
    rot = 90 if int(best.get("ori", 0)) == 1 else 0

    x_edges = compute_x_edges_from_placements(placements)
    y_edges = compute_y_edges_from_placements(placements)
    host = choose_first_row_leftmost_placement(placements)

    for _pi in range(pages):
        page = out_doc.new_page(width=Wpt, height=Hpt)

        page.draw_rect(fitz.Rect(0, 0, Wpt, Hpt), color=(0, 0, 0), width=1.2)
        page.draw_rect(fitz.Rect(Wpt - mm_to_pt(QR_W), 0, Wpt, mm_to_pt(QR_H)), color=(0, 0, 0), width=1.2)

        for p in placements:
            x = p["x"]; y = p["y"]; w = p["w"]; h = p["h"]
            y_top = H - (y + h)

            outer = fitz.Rect(mm_to_pt(x), mm_to_pt(y_top), mm_to_pt(x + w), mm_to_pt(y_top + h))
            page.draw_rect(outer, color=(0, 0, 0), width=0.6)

            if w <= 2 * inner_margin or h <= 2 * inner_margin:
                inner = outer
            else:
                inner = fitz.Rect(
                    mm_to_pt(x + inner_margin),
                    mm_to_pt(y_top + inner_margin),
                    mm_to_pt(x + w - inner_margin),
                    mm_to_pt(y_top + h - inner_margin),
                )

            if img_bytes:
                page.insert_image(inner, stream=img_bytes, keep_proportion=True, rotate=rot)

        if title and host:
            hx, hy, hw, hh = host["x"], host["y"], host["w"], host["h"]
            hy_top = H - (hy + hh)
            host_outer = fitz.Rect(mm_to_pt(hx), mm_to_pt(hy_top), mm_to_pt(hx + hw), mm_to_pt(hy_top + hh))
            draw_title_above_outer5mm(page, title, host_outer, fontsize=LABEL_FONT_SIZE)

        ml = mm_to_pt(MARK_LEN)
        for xx in x_edges:
            if xx >= (W - QR_W):
                continue
            xpt = mm_to_pt(xx)
            page.draw_line(fitz.Point(xpt, 0), fitz.Point(xpt, ml), color=(0, 0, 0), width=1.2)

        for yy in y_edges:
            y_line_top = H - yy
            ypt = mm_to_pt(y_line_top)
            page.draw_line(fitz.Point(0, ypt), fitz.Point(ml, ypt), color=(0, 0, 0), width=1.2)

def safe_save(doc, out_path):
    ensure_dir(os.path.dirname(out_path))
    tmp_pdf = os.path.join(os.path.dirname(out_path),
                           os.path.splitext(os.path.basename(out_path))[0] + "_tmp.pdf")

    try:
        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)
    except Exception:
        pass

    doc.save(tmp_pdf, garbage=4, deflate=True, incremental=False)
    doc.close()

    try:
        os.replace(tmp_pdf, out_path)
        return out_path
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S")
        alt_pdf = os.path.join(os.path.dirname(out_path),
                               os.path.splitext(os.path.basename(out_path))[0] + "_%s.pdf" % ts)
        try:
            shutil.move(tmp_pdf, alt_pdf)
        except Exception:
            shutil.copyfile(tmp_pdf, alt_pdf)
            try:
                os.remove(tmp_pdf)
            except Exception:
                pass
        return alt_pdf


# =========================
# ✅ 外部调用入口：run()
# =========================
def run(cfg=None, input_pdfs=None, progress_cb=None, log_cb=None):
    """
    cfg: dict，来自 run.py
      - DEST_DIR / TEST_DIR / DEST_DIR1 / DEST_DIR2 ...
    input_pdfs: run.py 已经传输到 TEST_DIR 的 pdf 路径列表（推荐传）
    progress_cb(n, N, text): 进度回调
    log_cb(msg): 日志回调
    """
    global DEST_DIR, IN_PDF_ARCHIVE_DIR, DEST_DIR1, DEST_DIR2, OUT_PDF_P1, OUT_PDF_P2

    if cfg:
        DEST_DIR = cfg.get("DEST_DIR", DEST_DIR)
        IN_PDF_ARCHIVE_DIR = cfg.get("TEST_DIR", IN_PDF_ARCHIVE_DIR)
        DEST_DIR1 = cfg.get("DEST_DIR1", DEST_DIR1)
        DEST_DIR2 = cfg.get("DEST_DIR2", DEST_DIR2)
        OUT_PDF_P1 = os.path.join(DEST_DIR1, "over_test_p1.pdf")
        OUT_PDF_P2 = os.path.join(DEST_DIR2, "over_test_p2.pdf")

    ensure_dir(IN_PDF_ARCHIVE_DIR)
    ensure_dir(DEST_DIR1)
    ensure_dir(DEST_DIR2)

    # 1) 输入列表（优先用 run.py 传进来的）
    if input_pdfs is not None:
        archived_paths = list(input_pdfs)
    else:
        # 单独运行时：从 DEST_DIR 扫描并复制到 test
        pdfs = []
        for fn in os.listdir(DEST_DIR):
            lfn = fn.lower()
            if not lfn.endswith(".pdf"):
                continue
            if lfn.startswith("over_test"):
                continue
            pdfs.append(os.path.join(DEST_DIR, fn))
        pdfs.sort()

        archived_paths = []
        for src in pdfs:
            try:
                dst = archive_input_pdf_to_dir(src, IN_PDF_ARCHIVE_DIR)
                archived_paths.append(dst)
            except Exception as e:
                _log(log_cb, "⚠️ 复制到test失败：%s err=%s" % (os.path.basename(src), repr(e)))

    if not archived_paths:
        raise RuntimeError("没有可处理PDF（archived_paths为空）")

    out1 = fitz.open()
    out2 = fitz.open()

    ok_list = []
    skip_list = []

    N_total = len(archived_paths)

    for idx, path in enumerate(archived_paths, start=1):
        type_name = os.path.splitext(os.path.basename(path))[0]

        if progress_cb:
            progress_cb(idx - 1, N_total, "处理中 %d/%d  %s" % (idx - 1, N_total, type_name))

        d = None
        try:
            d = fitz.open(path)
            pc = d.page_count
            if pc < 2:
                raise RuntimeError("PDF页数不足2页")

            # ✅ 按页对处理： (0,1), (2,3), (4,5)...
            pair_count = pc // 2
            if pair_count <= 0:
                raise RuntimeError("PDF无有效页对(页数=%d)" % pc)

            if (pc % 2) == 1:
                _log(log_cb, "⚠️ %s 页数为奇数(%d)，最后一页将忽略" % (type_name, pc))

            A, B, N = parse_A_B_N_from_filename(path)

            outer_A = A + 2.0 * OUTER_EXT
            outer_B = B + 2.0 * OUTER_EXT
            outer_size = (int(round(outer_A)), int(round(outer_B)))

            inner_w = A - 2.0 * INNER_GAP
            inner_h = B - 2.0 * INNER_GAP
            if inner_w <= 0 or inner_h <= 0:
                raise RuntimeError("A/B 太小，内缩3mm后无有效尺寸")

            best = solve_single_type_template(outer_size, N)
            if best is None:
                raise RuntimeError("单组无解（块限制/纸张限制下放不下）")

            pages_per_pair = best["pages"]
            title_base = build_group_title_from_filename(path, pages_per_pair)

            placements = build_fullsheet_placements(
                type_name=type_name,
                z=best["z"], h=best["h"],
                capy=best["capy"],
                groups=best["groups"],
                rows_max=best["rows_max"]
            )

            # ✅ 遍历每一对页：2n-1(本体) / 2n(轮廓)
            for pi in range(pair_count):
                page_body = 2 * pi      # 2n-1 -> 0-based: 0,2,4...
                page_cont = 2 * pi + 1  # 2n   -> 0-based: 1,3,5...

                # 以轮廓页作为 ref_bbox
                ref_img = render_page_to_pil(path, page_index=page_cont, dpi=RENDER_DPI, doc=d)
                ref_bbox = find_outer_bbox(ref_img)
                ref_size = ref_img.size

                img_bytes_body = make_part_png_bytes_using_ref_bbox(
                    pdf_path=path, page_index=page_body,
                    inner_w_mm=inner_w, inner_h_mm=inner_h,
                    ref_bbox=ref_bbox, ref_size=ref_size, dpi=RENDER_DPI, doc=d
                )
                img_bytes_cont = make_part_png_bytes_using_ref_bbox(
                    pdf_path=path, page_index=page_cont,
                    inner_w_mm=inner_w, inner_h_mm=inner_h,
                    ref_bbox=ref_bbox, ref_size=ref_size, dpi=RENDER_DPI, doc=d
                )

                # 标题区分不同页对（如果只有1对就不加）
                if pair_count > 1:
                    title = "%s-P%d/%d" % (title_base, pi + 1, pair_count)
                else:
                    title = title_base

                append_group_pages(out1, best, placements, pages_per_pair, title, img_bytes_body)
                append_group_pages(out2, best, placements, pages_per_pair, title, img_bytes_cont)

                _log(log_cb, "  ✅ pair %d/%d OK: %s" % (pi + 1, pair_count, type_name))

            total_pages_for_this_pdf = pages_per_pair * pair_count
            ok_list.append((type_name, total_pages_for_this_pdf))
            _log(log_cb, "✅ OK: %s pairs=%d pages_per_pair=%d total_pages=%d"
                 % (type_name, pair_count, pages_per_pair, total_pages_for_this_pdf))

        except Exception as e:
            skip_list.append((type_name, repr(e)))
            _log(log_cb, "⚠️ SKIP: %s reason=%s" % (type_name, repr(e)))
            continue
        finally:
            try:
                if d is not None:
                    d.close()
            except Exception:
                pass

    if not ok_list:
        try:
            out1.close()
        except Exception:
            pass
        try:
            out2.close()
        except Exception:
            pass
        raise RuntimeError("No feasible template found for any input (all skipped).")

    p1 = safe_save(out1, OUT_PDF_P1)
    p2 = safe_save(out2, OUT_PDF_P2)

    if progress_cb:
        progress_cb(N_total, N_total, "完成 %d/%d" % (N_total, N_total))

    _log(log_cb, "Saved: %s" % p1)
    _log(log_cb, "Saved: %s" % p2)

    return {"out_p1": p1, "out_p2": p2, "ok": ok_list, "skip": skip_list}


def main():
    # 单独运行（无界面）
    res = run(cfg=None, input_pdfs=None, progress_cb=None, log_cb=None)
    print("DONE:", res.get("out_p1"), res.get("out_p2"))


if __name__ == "__main__":
    main()
