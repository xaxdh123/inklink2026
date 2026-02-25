# -*- coding: utf-8 -*-
"""
双输出版（每个源PDF多对页 -> 输出两个拼版PDF）：

【页面语义（最终规则）】
- 2n-1 页（奇数页，0-based 偶数 index）：图形页（圆形/实图）
- 2n   页（偶数页，0-based 奇数 index）：外围轮廓页（只画外轮廓线）
- 裁剪规则：
    - 图形页(2n-1)：用对应轮廓页(2n) 的 bbox 来裁剪
    - 轮廓页(2n)：用自身 bbox 来裁剪
  （0-based：target_index 为偶数 -> ref = target_index+1；target_index 为奇数 -> ref = target_index）

✅ 本次更新（按“同样方式”）
- bbox 裁剪更稳：scaled(ref_bbox) 与 target 自身 bbox 取并集（避免削边）
- padding 改大（毫米->像素）
- 裁剪后做“贴边检测”：如果内容贴边，自动再扩一圈重裁（最多2次）

【重要变更】
- 只用 bbox 裁剪，不再用 fillPoly 做透明mask
- bbox 识别多策略 + 自动兜底
- bbox padding 使用“固定毫米 -> 像素”
- 排版旋转时，insert_image 同步 rotate

依赖：
pip install pymupdf pillow numpy opencv-python
"""

import os
import re
import math
import json
from copy import deepcopy
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

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# =========================
# 0) 目录与输出
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
    global DEST_DIR, IN_PDF_ARCHIVE_DIR, DEST_DIR1, DEST_DIR2
    global OUT_PDF_P1, OUT_PDF_P2, JSON_NAME_P1, JSON_NAME_P2

    DEST_DIR = str(dest_dir)
    IN_PDF_ARCHIVE_DIR = str(archive_dir)
    DEST_DIR1 = str(out_dir1)
    DEST_DIR2 = str(out_dir2)

    try:
        if DEST_DIR:
            os.makedirs(DEST_DIR, exist_ok=True)
        if IN_PDF_ARCHIVE_DIR:
            os.makedirs(IN_PDF_ARCHIVE_DIR, exist_ok=True)
        if DEST_DIR1:
            os.makedirs(DEST_DIR1, exist_ok=True)
        if DEST_DIR2:
            os.makedirs(DEST_DIR2, exist_ok=True)
    except Exception:
        pass

    OUT_PDF_P1 = os.path.join(DEST_DIR1, "over_test_p1.pdf")
    OUT_PDF_P2 = os.path.join(DEST_DIR2, "over_test_p2.pdf")

    JSON_NAME_P1 = os.path.join(DEST_DIR1, "sheet_template_p1.json")
    JSON_NAME_P2 = os.path.join(DEST_DIR2, "sheet_template_p2.json")


SAVE_JSON = False
JSON_NAME_P1 = os.path.join(DEST_DIR1, "sheet_template_p1.json")
JSON_NAME_P2 = os.path.join(DEST_DIR2, "sheet_template_p2.json")


# =========================
# 1) PAPER / PROCESS PARAMS
# =========================
SEG_MAX_W = 320
SEG_MAX_H = 460

GAP = 6
MARGIN = 11

H_MIN, H_MAX = 570, 590
W_MAX = 1000

QR_BAND = 10
QR_W = 10
QR_H = 10

MARK_LEN = 10
LABEL_BAND_H = GAP
LABEL_FONT_SIZE = 10

RENDER_DPI = 600

# ✅ 原来 0.3mm 太容易削边（600dpi只有 ~7px），这里先给 1.2mm
CROP_PAD_MM = 1.20

INNER_MARGIN_MM = 5.0


def H_usable(H_sheet: int) -> int:
    return H_sheet - QR_BAND


R_MIN = 200
R_MAX = W_MAX - 2 * MARGIN
R_STEP = 1

N_MAX_BASE = 60
N_MAX_HARD = 4000

ALLOW_EXTRA_REQUIRED_FOR_FILL = True
FILLER_TYPES = []

BEAM_WIDTH = 30
BEAM_STEPS = 200
MAX_ADD_ROWS_PER_TYPE = 30


# =========================
# 2) 动态输入（每次run会重置）
# =========================
PARTS = {}
NEED = {}
PART_IMG_BYTES = {}


# =========================
# 工具函数
# =========================
def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b

def mm_to_pt(mm):
    return mm * 72.0 / 25.4

def mm_to_px(mm, dpi):
    return int(round(mm * dpi / 25.4))

def enum_orientations(names):
    n = len(names)
    for mask in range(1 << n):
        ori = {}
        for i, nm in enumerate(names):
            ori[nm] = 1 if ((mask >> i) & 1) else 0
        yield ori

def get_z_hrow(names, ori):
    z = {}
    hrow = {}
    for nm in names:
        x, y = PARTS[nm]
        if ori[nm] == 0:
            z[nm] = x
            hrow[nm] = y
        else:
            z[nm] = y
            hrow[nm] = x
    return z, hrow

def dynamic_nmax():
    max_need = max(NEED.values()) if NEED else 0
    guess = int(max(N_MAX_BASE, math.ceil(math.sqrt(max_need)) * 10))
    return min(N_MAX_HARD, max(N_MAX_BASE, guess))

def compress_same_type_blocks(blocks):
    out = []
    for nm, nrows in blocks:
        if nrows <= 0:
            continue
        if out and out[-1][0] == nm:
            out[-1] = (nm, out[-1][1] + nrows)
        else:
            out.append((nm, nrows))
    return out

def seg_height_with_inner_gaps(seg, hrow):
    if not seg:
        return 0
    hsum = 0
    for nm, nrows in seg:
        hsum += nrows * hrow[nm]
    if len(seg) >= 2:
        hsum += GAP * (len(seg) - 1)
    return hsum

def safe_save_pdf(doc, out_path):
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(out_path))[0]
    tmp_path = os.path.join(out_dir, base + "_tmp.pdf")

    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass

    doc.save(tmp_path, garbage=4, deflate=True, incremental=False)
    doc.close()

    try:
        os.replace(tmp_path, out_path)
        print("Saved:", out_path)
        return out_path
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S")
        alt = os.path.join(out_dir, base + "_" + ts + ".pdf")
        try:
            os.replace(tmp_path, alt)
        except Exception:
            shutil.copyfile(tmp_path, alt)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        print("⚠️ 被占用，已输出：", alt)
        return alt


# =========================
# ✅ 轮廓参考页规则
# =========================
def ref_page_index_for_bbox(target_page_index: int, page_count: int) -> int:
    if target_page_index % 2 == 0:
        ref = target_page_index + 1
        if ref < page_count:
            return ref
        return target_page_index
    return target_page_index


# =========================
# 标记文本：开头到第二个^ + 第九个^之后所有 + 连续块数量
# =========================
def build_mark_text_from_type(type_name: str, block_count: int) -> str:
    base = type_name
    parts = base.split("^")

    if len(parts) >= 2:
        prefix = parts[0] + "^" + parts[1] + "^"
    elif len(parts) == 1:
        prefix = parts[0] + "^"
    else:
        prefix = ""

    suffix = ""
    if len(parts) >= 10:
        suffix = "^".join(parts[9:])
        if suffix and (not suffix.endswith("^")):
            suffix += "^"

    return prefix + suffix + str(int(block_count))


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
            if re.search(r"\d+(\.\d+)?\s*[\*xX]\s*\d+(\.\d+)?", parts[i]) and re.search(r"\d+", parts[i+1]):
                size_part = parts[i]
                n_part = parts[i+1]
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


# =========================
# ✅ PDF渲染任意页（支持复用 doc）
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
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    finally:
        if close_doc:
            doc.close()


# =========================
# bbox 识别：多策略 + 自动兜底
# =========================
def _reject_border_bbox(x, y, w, h, W, H):
    edge_pad = 8
    touches_edge = (x <= edge_pad or y <= edge_pad or (x + w) >= (W - edge_pad) or (y + h) >= (H - edge_pad))
    huge_rect = (w >= 0.98 * W and h >= 0.98 * H)
    return bool(touches_edge and huge_rect)

def _bbox_from_mask(mask, W, H):
    if mask is None:
        return None
    ys, xs = np.where(mask > 0)
    if xs.size < 50 or ys.size < 50:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    return (x0, y0, x1, y1)

def _bbox_from_contours(mask, W, H):
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
        bboxes.append((float(w * h), x, y, w, h))

    if not bboxes:
        return None

    bboxes.sort(key=lambda t: t[0], reverse=True)
    max_area = bboxes[0][0]

    keep = []
    for area, x, y, w, h in bboxes[:20]:
        if area >= 0.10 * max_area:
            keep.append((x, y, x + w, y + h))
    if not keep:
        x, y, w, h = bboxes[0][1], bboxes[0][2], bboxes[0][3], bboxes[0][4]
        return (x, y, x + w, y + h)

    x0 = min(k[0] for k in keep)
    y0 = min(k[1] for k in keep)
    x1 = max(k[2] for k in keep)
    y1 = max(k[3] for k in keep)
    return (int(x0), int(y0), int(x1), int(y1))

def find_outer_bbox(pil_img):
    if not CV2_OK:
        arr = np.array(pil_img.convert("RGB"))
        gray = (0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]).astype(np.uint8)
        mask = (gray < 250).astype(np.uint8) * 255
        H, W = mask.shape
        return _bbox_from_mask(mask, W, H)

    arr = np.array(pil_img.convert("RGB"))
    H, W = arr.shape[0], arr.shape[1]
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates = []

    try:
        thA = cv2.adaptiveThreshold(
            gray_blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35, 5
        )
        thA = cv2.morphologyEx(thA, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        thA = cv2.dilate(thA, np.ones((3, 3), np.uint8), iterations=1)
        bboxA = _bbox_from_contours(thA, W, H)
        if bboxA:
            candidates.append(bboxA)
    except Exception:
        pass

    try:
        _, thB = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thB = cv2.morphologyEx(thB, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        thB = cv2.dilate(thB, np.ones((3, 3), np.uint8), iterations=1)
        bboxB = _bbox_from_contours(thB, W, H)
        if bboxB:
            candidates.append(bboxB)
    except Exception:
        pass

    try:
        edges = cv2.Canny(gray_blur, 50, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)
        bboxC = _bbox_from_contours(edges, W, H)
        if bboxC:
            candidates.append(bboxC)
    except Exception:
        pass

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
        return None

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


def scale_bbox(bbox, src_size, dst_size):
    if bbox is None or src_size is None or dst_size is None:
        return None
    sx = float(dst_size[0]) / float(src_size[0])
    sy = float(dst_size[1]) / float(src_size[1])
    x0, y0, x1, y1 = bbox
    x0 = int(round(x0 * sx))
    x1 = int(round(x1 * sx))
    y0 = int(round(y0 * sy))
    y1 = int(round(y1 * sy))
    return (x0, y0, x1, y1)

def _union_bbox(b1, b2):
    if b1 is None:
        return b2
    if b2 is None:
        return b1
    return (min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3]))

def _clamp_bbox(bbox, W, H):
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    x0 = max(0, min(W - 2, int(x0)))
    y0 = max(0, min(H - 2, int(y0)))
    x1 = max(x0 + 2, min(W, int(x1)))
    y1 = max(y0 + 2, min(H, int(y1)))
    return (x0, y0, x1, y1)

def _expand_bbox_px(bbox, exp_px, W, H):
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    x0 -= exp_px; y0 -= exp_px; x1 += exp_px; y1 += exp_px
    return _clamp_bbox((x0, y0, x1, y1), W, H)

def _content_touches_edges(pil_rgb, thr=250, margin_px=2):
    arr = np.array(pil_rgb.convert("RGB"))
    gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)

    m = int(margin_px)
    if m <= 0:
        m = 1
    mask = (gray < thr)

    if mask[:m, :].any():
        return True
    if mask[-m:, :].any():
        return True
    if mask[:, :m].any():
        return True
    if mask[:, -m:].any():
        return True
    return False

def _apply_bbox_crop_rgb(img_rgb, bbox, pad_px):
    W, H = img_rgb.size
    if bbox is None:
        return img_rgb

    x0, y0, x1, y1 = bbox
    x0 -= pad_px; y0 -= pad_px; x1 += pad_px; y1 += pad_px
    bbox2 = _clamp_bbox((x0, y0, x1, y1), W, H)
    if bbox2 is None:
        return img_rgb
    x0, y0, x1, y1 = bbox2
    return img_rgb.crop((x0, y0, x1, y1))


# =========================
# ✅ 用“参考页 bbox”裁剪目标页（支持 doc 复用）——稳版
# =========================
def make_part_png_bytes_using_ref_bbox(pdf_path, target_page_index, ref_bbox, ref_size, dpi=RENDER_DPI, doc=None):
    """
    ✅ 稳版裁剪：
    - bbox_ref_scaled 与 bbox_self 取并集
    - 先按 CROP_PAD_MM 扩一圈
    - 裁完如果“贴边”，再自动扩 0.6mm 重裁（最多2次）
    """
    img = render_page_to_pil(pdf_path, page_index=target_page_index, dpi=dpi, doc=doc).convert("RGB")
    pad_px = mm_to_px(CROP_PAD_MM, dpi)
    W, H = img.size

    bbox_self = None
    try:
        bbox_self = find_outer_bbox(img)
    except Exception:
        bbox_self = None

    bbox_ref_scaled = None
    if (ref_bbox is not None) and (ref_size is not None):
        try:
            bbox_ref_scaled = scale_bbox(ref_bbox, ref_size, img.size)
        except Exception:
            bbox_ref_scaled = None

    bbox = _union_bbox(bbox_ref_scaled, bbox_self)
    if bbox is None:
        bbox = (0, 0, W, H)

    bbox = _clamp_bbox(bbox, W, H)
    if bbox is None:
        bbox = (0, 0, W, H)

    # 先裁一次
    crop = _apply_bbox_crop_rgb(img, bbox, pad_px)

    # 贴边自检：贴边则再扩 0.6mm 重裁（最多2次）
    for _ in range(2):
        if not _content_touches_edges(crop, thr=250, margin_px=2):
            break
        extra_px = mm_to_px(0.60, dpi)
        bbox = _expand_bbox_px(bbox, extra_px, W, H)
        crop = _apply_bbox_crop_rgb(img, bbox, pad_px)

    from io import BytesIO
    bio = BytesIO()
    crop.save(bio, format="PNG", optimize=True)
    return bio.getvalue()


# =========================
# Row pattern：横向每块 <= SEG_MAX_W
# =========================
def find_row_pattern(z: int, R: int):
    cap = SEG_MAX_W // z
    if cap <= 0:
        return None

    m_max = (R // z) + 1
    for m in range(1, m_max + 1):
        t = m - 1
        usable = R - GAP * t
        if usable <= 0:
            continue
        if usable % z != 0:
            continue
        k = usable // z
        if k <= 0:
            continue
        if not ((m - 1) * cap < k <= m * cap):
            continue

        groups = [cap] * (m - 1)
        last = k - (m - 1) * cap
        if not (1 <= last <= cap):
            continue
        groups.append(last)

        if any((g * z) > SEG_MAX_W for g in groups):
            continue

        return {"k": k, "t": t, "groups": groups, "cap": cap}

    return None


# =========================
# build_segments：纵向每段高度 <= SEG_MAX_H
# =========================
def build_segments(rows: dict, hrow: dict):
    names = list(hrow.keys())
    full_segments = []
    rema = []

    for nm in names:
        hh = hrow[nm]
        capy = SEG_MAX_H // hh
        if capy <= 0:
            return None

        r = rows.get(nm, 0)
        full = r // capy
        rem = r % capy

        for _ in range(full):
            full_segments.append([(nm, capy)])

        if rem > 0:
            rema.append((rem * hh, nm, rem))

    rema.sort(key=lambda x: x[0], reverse=True)
    bins = []
    for h, nm, nrows in rema:
        placed = False
        for b in bins:
            extra_gap = GAP if b["blocks"] else 0
            if b["used"] + extra_gap + h <= SEG_MAX_H:
                if extra_gap:
                    b["used"] += GAP
                b["blocks"].append((nm, nrows))
                b["used"] += h
                placed = True
                break
        if not placed:
            if h > SEG_MAX_H:
                return None
            bins.append({"used": h, "blocks": [(nm, nrows)]})

    mixed_segments = [compress_same_type_blocks(b["blocks"]) for b in bins]
    all_segments = full_segments + mixed_segments
    all_segments.sort(key=lambda seg: seg_height_with_inner_gaps(seg, hrow), reverse=True)
    return all_segments


def required_height(segments, hrow):
    if segments is None:
        return None
    if len(segments) == 0:
        return 2 * MARGIN

    content = 0
    for seg in segments:
        content += seg_height_with_inner_gaps(seg, hrow)

    content += GAP * (len(segments) - 1)
    return content + 2 * MARGIN


def used_area_from_rows(rows: dict, k_per_row: dict, names_all: list):
    used = 0
    for nm in names_all:
        r = rows.get(nm, 0)
        k = k_per_row.get(nm, 0)
        px, py = PARTS[nm]
        used += (r * k) * px * py
    return used


def beam_fill(rows_base: dict, names_all: list, fill_names: list, hrow: dict, k_per_row: dict, H_sheet: int):
    Huse = H_usable(H_sheet)
    seg0 = build_segments(rows_base, hrow)
    H0 = required_height(seg0, hrow)
    if H0 is None or H0 > Huse:
        return None

    best_rows = deepcopy(rows_base)
    best_used = used_area_from_rows(best_rows, k_per_row, names_all)
    best_blank = Huse - H0

    start_adds = tuple([0] * len(fill_names))
    beam = [(deepcopy(rows_base), best_used, H0, start_adds)]

    for _ in range(BEAM_STEPS):
        new_states = []
        for rows, used, Hn, adds in beam:
            for i, nm in enumerate(fill_names):
                if adds[i] >= MAX_ADD_ROWS_PER_TYPE:
                    continue
                cand = dict(rows)
                cand[nm] = cand.get(nm, 0) + 1

                segs = build_segments(cand, hrow)
                H2 = required_height(segs, hrow)
                if H2 is None or H2 > Huse:
                    continue

                used2 = used_area_from_rows(cand, k_per_row, names_all)
                blank2 = Huse - H2

                if (blank2 < best_blank - 1e-9) or (abs(blank2 - best_blank) <= 1e-9 and used2 > best_used + 1e-9):
                    best_blank = blank2
                    best_used = used2
                    best_rows = cand

                adds2 = list(adds)
                adds2[i] += 1
                new_states.append((cand, used2, H2, tuple(adds2)))

        if not new_states:
            break

        new_states.sort(key=lambda t: (Huse - t[2], -t[1], -t[2]))
        beam = new_states[:BEAM_WIDTH]

    return best_rows


def best_template_for_N(N: int, required_names: list):
    req_per_sheet = {nm: int(math.ceil(NEED[nm] / float(N))) for nm in required_names}

    fill_names = [nm for nm in FILLER_TYPES if nm in PARTS and nm not in required_names]
    if ALLOW_EXTRA_REQUIRED_FOR_FILL:
        for nm in required_names:
            if nm not in fill_names:
                fill_names.append(nm)

    names_all = []
    for nm in required_names + fill_names:
        if nm not in names_all:
            names_all.append(nm)

    if not names_all:
        return None

    best = None

    for ori in enum_orientations(names_all):
        z, hrow = get_z_hrow(names_all, ori)

        if any((SEG_MAX_H // hrow[nm]) <= 0 for nm in names_all):
            continue

        for R in range(R_MIN, R_MAX + 1, R_STEP):
            W_sheet = R + 2 * MARGIN
            if W_sheet > W_MAX:
                break

            patterns = {}
            k_per_row = {}
            ok = True
            for nm in names_all:
                pat = find_row_pattern(z[nm], R)
                if pat is None:
                    ok = False
                    break
                patterns[nm] = pat
                k_per_row[nm] = pat["k"]
            if not ok:
                continue

            rows_required = {}
            for nm in required_names:
                need = req_per_sheet[nm]
                rows_required[nm] = 0 if need <= 0 else ceil_div(need, k_per_row[nm])

            seg_min = build_segments(rows_required, hrow)
            Hneed_min = required_height(seg_min, hrow)
            if Hneed_min is None or Hneed_min > H_MAX:
                continue

            H_sheet = max(H_MIN, int(math.ceil(Hneed_min)))
            if H_sheet > H_MAX:
                continue

            Huse = H_usable(H_sheet)
            if Hneed_min > Huse:
                continue

            rows_base = dict(rows_required)
            for nm in fill_names:
                rows_base.setdefault(nm, 0)

            seg0 = build_segments(rows_base, hrow)
            H0 = required_height(seg0, hrow)
            if H0 is None:
                continue

            blank0 = Huse - H0
            rows_filled = rows_base

            if blank0 >= 1 and fill_names:
                tmp = beam_fill(rows_base, names_all, fill_names, hrow, k_per_row, H_sheet)
                if tmp is not None:
                    rows_filled = tmp

            seg_final = build_segments(rows_filled, hrow)
            Hneed = required_height(seg_final, hrow)
            if Hneed is None or Hneed > Huse:
                continue

            area_sheet = W_sheet * H_sheet
            total_area = N * area_sheet
            used_area = used_area_from_rows(rows_filled, k_per_row, names_all)
            util = used_area / float(area_sheet)
            blank_top = Huse - Hneed

            cand = {
                "N": N,
                "R": R,
                "W_sheet": W_sheet,
                "H_sheet": H_sheet,
                "ori": ori,
                "z": z,
                "hrow": hrow,
                "patterns": patterns,
                "k_per_row": k_per_row,
                "rows": rows_filled,
                "rows_required_only": rows_required,
                "segments": seg_final,
                "area_sheet": area_sheet,
                "total_area": total_area,
                "util": util,
                "blankTop": blank_top,
                "names_all": names_all,
                "required_names": required_names,
                "fill_names": fill_names
            }

            if best is None or cand["total_area"] < best["total_area"]:
                best = cand
            elif cand["total_area"] == best["total_area"]:
                if cand["blankTop"] < best["blankTop"] - 1e-9:
                    best = cand
                elif abs(cand["blankTop"] - best["blankTop"]) <= 1e-9 and cand["util"] > best["util"] + 1e-12:
                    best = cand

    return best


def compute_N_required(best, required_names):
    prod_req = {}
    for nm in required_names:
        prod_req[nm] = best["rows_required_only"][nm] * best["k_per_row"][nm]
    N = 1
    for nm in required_names:
        need = NEED[nm]
        p = prod_req.get(nm, 0)
        if p <= 0:
            return None
        N = max(N, int(math.ceil(need / float(p))))
    return N


def build_placements(best):
    placements = []
    labels = []
    y = MARGIN

    segs = [compress_same_type_blocks(seg) for seg in best["segments"]]
    nsegs = len(segs)

    def place_rows_of_type(nm, nrows):
        nonlocal y
        groups = best["patterns"][nm]["groups"]
        rh = best["hrow"][nm]
        w = best["z"][nm]
        for _ in range(int(nrows)):
            x = MARGIN
            for gi, gsz in enumerate(groups):
                for _p in range(gsz):
                    placements.append({"type": nm, "x": x, "y": y, "w": w, "h": rh})
                    x += w
                if gi != len(groups) - 1:
                    x += GAP
            y += rh

    run_nm = None
    run_blocks = 0

    for si, seg in enumerate(segs):
        if len(seg) == 1:
            nm, nrows = seg[0]

            if run_nm is None:
                run_nm = nm
                run_blocks = 0
            if nm != run_nm:
                run_nm = nm
                run_blocks = 0

            run_blocks += 1
            place_rows_of_type(nm, nrows)

            is_last = (si == nsegs - 1)
            if not is_last:
                labels.append({"type": run_nm, "count": int(run_blocks), "y0": y, "y1": y + LABEL_BAND_H})
                y += GAP

                next_seg = segs[si + 1]
                next_nm = next_seg[0][0] if len(next_seg) == 1 else None
                if next_nm != run_nm:
                    run_nm = None
                    run_blocks = 0
            else:
                Huse = H_usable(best["H_sheet"])
                avail = max(0.0, Huse - y)
                band = min(float(LABEL_BAND_H), float(avail))
                if band > 0.5 and run_nm is not None:
                    labels.append({"type": run_nm, "count": int(run_blocks), "y0": y, "y1": y + band})
                run_nm = None
                run_blocks = 0

        else:
            for bi, (nm, nrows) in enumerate(seg):
                place_rows_of_type(nm, nrows)

                has_next = (bi != len(seg) - 1) or (si != nsegs - 1)
                if has_next:
                    labels.append({"type": nm, "count": 1, "y0": y, "y1": y + LABEL_BAND_H})
                    y += GAP
                else:
                    Huse = H_usable(best["H_sheet"])
                    avail = max(0.0, Huse - y)
                    band = min(float(LABEL_BAND_H), float(avail))
                    if band > 0.5:
                        labels.append({"type": nm, "count": 1, "y0": y, "y1": y + band})

    return placements, labels


def compute_x_edges_from_placements(placements, W_sheet):
    xs = set([0, int(W_sheet)])
    for p in placements:
        xs.add(int(round(p["x"])))
        xs.add(int(round(p["x"] + p["w"])))
    return sorted(xs)

def compute_y_edges_from_placements(placements, H_sheet):
    ys = set([0, int(H_sheet)])
    for p in placements:
        ys.add(int(round(p["y"])))
        ys.add(int(round(p["y"] + p["h"])))
    return sorted(ys)


def write_over_test_pdf(out_pdf_path, best, placements, y_edges, x_edges, labels):
    doc = fitz.open()

    W = float(best["W_sheet"])
    H = float(best["H_sheet"])
    Wpt = mm_to_pt(W)
    Hpt = mm_to_pt(H)

    n_pages = int(best["N"])

    fontfile = None
    for p in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if os.path.exists(p):
            fontfile = p
            break

    for _pi in range(n_pages):
        page = doc.new_page(width=Wpt, height=Hpt)

        page.draw_rect(fitz.Rect(0, 0, Wpt, Hpt), color=(0, 0, 0), width=1.2)
        page.draw_rect(fitz.Rect(Wpt - mm_to_pt(QR_W), 0, Wpt, mm_to_pt(QR_H)), color=(0, 0, 0), width=1.2)

        for p in placements:
            nm = p["type"]
            x = float(p["x"]); y = float(p["y"]); w = float(p["w"]); h = float(p["h"])
            y_top = H - (y + h)

            outer = fitz.Rect(mm_to_pt(x), mm_to_pt(y_top), mm_to_pt(x + w), mm_to_pt(y_top + h))
            page.draw_rect(outer, color=(0, 0, 0), width=0.6)

            inner_margin = float(INNER_MARGIN_MM)
            if w <= 2 * inner_margin or h <= 2 * inner_margin:
                inner = outer
            else:
                inner = fitz.Rect(
                    mm_to_pt(x + inner_margin),
                    mm_to_pt(y_top + inner_margin),
                    mm_to_pt(x + w - inner_margin),
                    mm_to_pt(y_top + h - inner_margin),
                )

            img_bytes = PART_IMG_BYTES.get(nm, None)
            if img_bytes is not None:
                rot = 90 if int(best["ori"].get(nm, 0)) == 1 else 0
                page.insert_image(inner, stream=img_bytes, keep_proportion=True, rotate=rot)

        x_text_pt = mm_to_pt(MARGIN + 1.0)
        for lb in labels:
            nm = lb["type"]
            cnt = int(lb.get("count", 1))
            y0 = float(lb["y0"])
            text = build_mark_text_from_type(nm, cnt)
            baseline_mm = (H - y0) - 1.2
            if baseline_mm < 1.0:
                baseline_mm = 1.0
            y_text_pt = mm_to_pt(baseline_mm)

            if fontfile:
                page.insert_text(fitz.Point(x_text_pt, y_text_pt), text, fontsize=LABEL_FONT_SIZE, fontfile=fontfile, color=(0, 0, 0))
            else:
                page.insert_text(fitz.Point(x_text_pt, y_text_pt), text, fontsize=LABEL_FONT_SIZE, fontname="helv", color=(0, 0, 0))

        ml = mm_to_pt(MARK_LEN)
        for xx in x_edges:
            xx = float(xx)
            if xx >= (W - QR_W):
                continue
            xpt = mm_to_pt(xx)
            page.draw_line(fitz.Point(xpt, 0), fitz.Point(xpt, ml), color=(0, 0, 0), width=1.2)

        for yy in y_edges:
            yy = float(yy)
            y_line_top = H - yy
            ypt = mm_to_pt(y_line_top)
            page.draw_line(fitz.Point(0, ypt), fitz.Point(ml, ypt), color=(0, 0, 0), width=1.2)

    safe_save_pdf(doc, out_pdf_path)


# =========================
# ✅ 选择要剔除的“最难拼”类型（用于整体无解时，不硬拼）
# =========================
def is_type_impossible_basic(nm):
    x, y = PARTS[nm]
    if min(x, y) > SEG_MAX_W:
        return True
    if min(x, y) > SEG_MAX_H:
        return True
    return False

def pick_hardest_type(names):
    for nm in names:
        if is_type_impossible_basic(nm):
            return nm

    best_nm = None
    best_score = None
    for nm in names:
        x, y = PARTS[nm]
        need = NEED.get(nm, 0)
        score = (max(x, y) * max(1, need)) + (x * y) * 0.001
        if best_score is None or score > best_score:
            best_score = score
            best_nm = nm
    return best_nm


def find_best_with_optional_skips(required_names):
    dropped = []
    cur = list(required_names)

    def try_find(cur_names):
        if not cur_names:
            return None
        best1 = best_template_for_N(1, cur_names)
        if best1 is not None:
            return best1

        best = None
        nmax_dyn = dynamic_nmax()
        for Ntry in range(2, nmax_dyn + 1):
            cand = best_template_for_N(Ntry, cur_names)
            if cand is None:
                continue
            if best is None or cand["total_area"] < best["total_area"]:
                best = cand
        return best

    while cur:
        best = try_find(cur)
        if best is not None:
            return best, cur, dropped

        bad = pick_hardest_type(cur)
        if bad is None:
            break
        dropped.append(bad)
        cur = [nm for nm in cur if nm != bad]
        print("⚠️ 整体无解：已跳过类型 =>", bad)

    return None, [], dropped


# =========================
# ✅ 单次运行：mode='body' or 'outline'，输出到指定pdf
# =========================
def run_one(mode, out_pdf_path, json_path=None):
    """
    mode:
      - 'body'    => 拼版所有图形页(2n-1)，每对用对应轮廓页 bbox
      - 'outline' => 拼版所有轮廓页(2n)，轮廓页用自身 bbox
    """
    global PARTS, NEED, PART_IMG_BYTES
    PARTS = {}
    NEED = {}
    PART_IMG_BYTES = {}

    pdfs = []
    for fn in os.listdir(DEST_DIR):
        if not fn.lower().endswith(".pdf"):
            continue
        if fn.lower().startswith("over_test"):
            continue
        pdfs.append(os.path.join(DEST_DIR, fn))

    if not pdfs:
        raise RuntimeError("目录里没有可处理的 PDF：%s" % DEST_DIR)

    skipped_files = []  # (path, reason)

    for path in sorted(pdfs):
        doc = None
        added_names = []
        try:
            doc = fitz.open(path)
            pc = doc.page_count
            if pc < 2:
                raise RuntimeError("页数不足2页")

            pair_count = pc // 2
            if pair_count <= 0:
                raise RuntimeError("无有效页对(页数=%d)" % pc)

            if (pc % 2) == 1:
                print("⚠️", os.path.basename(path), "页数为奇数(%d)，最后一页将忽略" % pc)

            A, B, N = parse_A_B_N_from_filename(path)
            base_name = os.path.splitext(os.path.basename(path))[0]

            # 逐对页生成“虚拟类型”
            for pi in range(pair_count):
                if pair_count == 1:
                    name = base_name
                else:
                    name = "%s__P%02d" % (base_name, pi + 1)

                PARTS[name] = (int(round(A)), int(round(B)))
                NEED[name] = int(N)

                if mode == "body":
                    target_page = 2 * pi       # 0,2,4...
                else:
                    target_page = 2 * pi + 1   # 1,3,5...

                ref_page = ref_page_index_for_bbox(target_page, pc)

                ref_img = render_page_to_pil(path, page_index=ref_page, dpi=RENDER_DPI, doc=doc)
                ref_bbox = find_outer_bbox(ref_img)
                ref_size = ref_img.size

                PART_IMG_BYTES[name] = make_part_png_bytes_using_ref_bbox(
                    pdf_path=path,
                    target_page_index=target_page,
                    ref_bbox=ref_bbox,
                    ref_size=ref_size,
                    dpi=RENDER_DPI,
                    doc=doc
                )

                added_names.append(name)

        except Exception as e:
            skipped_files.append((path, repr(e)))
            print("⚠️ 跳过PDF（处理失败）:", os.path.basename(path), "reason:", repr(e))
            for nm in added_names:
                PARTS.pop(nm, None)
                NEED.pop(nm, None)
                PART_IMG_BYTES.pop(nm, None)
        finally:
            try:
                if doc is not None:
                    doc.close()
            except Exception:
                pass

    required_names = [nm for nm, v in NEED.items() if v > 0]
    if not required_names:
        raise RuntimeError("没有任何可用PDF能进入拼版（全部被跳过）。")

    best, final_required_names, dropped_names = find_best_with_optional_skips(required_names)
    if best is None or not final_required_names:
        raise RuntimeError("No feasible template found. 已自动跳过若干类型后仍无解。")

    keep = set(final_required_names)
    for nm in list(PARTS.keys()):
        if nm not in keep:
            PARTS.pop(nm, None)
            NEED.pop(nm, None)
            PART_IMG_BYTES.pop(nm, None)

    N_real = compute_N_required(best, final_required_names)
    if N_real is None:
        raise RuntimeError("Template capacity missing required type.")
    best["N"] = N_real
    best["total_area"] = N_real * best["area_sheet"]

    placements, labels = build_placements(best)
    x_edges = compute_x_edges_from_placements(placements, best["W_sheet"])
    y_edges = compute_y_edges_from_placements(placements, best["H_sheet"])

    write_over_test_pdf(out_pdf_path, best, placements, y_edges, x_edges, labels)
    print("Saved:", out_pdf_path)

    if skipped_files:
        print("=== SKIPPED FILES (PROCESS FAIL) ===")
        for p, r in skipped_files:
            print(" -", os.path.basename(p), "=>", r)
    if dropped_names:
        print("=== SKIPPED TYPES (NO FEASIBLE TEMPLATE) ===")
        for nm in dropped_names:
            print(" -", nm)
    print("=== INCLUDED TYPES ===", len(final_required_names))

    if SAVE_JSON and json_path:
        data = {
            "N_identical": best["N"],
            "W_sheet": best["W_sheet"],
            "H_sheet": best["H_sheet"],
            "need": NEED,
            "util": best["util"],
            "segments": best["segments"],
            "x_edges": x_edges,
            "y_edges": y_edges,
            "labels": labels,
            "placements": placements,
            "block_limit": {"max_w": SEG_MAX_W, "max_h": SEG_MAX_H, "gap": GAP},
            "mode": mode
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved JSON:", json_path)


def main():
    print("=== BUILD PDF 1: pack BODY pages (2n-1), bbox from outline page (2n) ===")
    run_one(mode="body", out_pdf_path=OUT_PDF_P1, json_path=JSON_NAME_P1)

    print("\n=== BUILD PDF 2: pack OUTLINE pages (2n), bbox from itself ===")
    run_one(mode="outline", out_pdf_path=OUT_PDF_P2, json_path=JSON_NAME_P2)

    print("\nDONE:")
    print(" -", OUT_PDF_P1)
    print(" -", OUT_PDF_P2)


if __name__ == "__main__":
    main()
