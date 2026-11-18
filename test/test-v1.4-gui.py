# -*- coding: utf-8 -*-
"""Test GUI v1.4 duoi Xvfb (khong can mang - giong duoc gia lap bang tone
4.0s moi cau, de co cau can tang toc moi kip slot).
Chay:
  xvfb-run -a ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.4-gui.py
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    "srt14gui", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PASSED = 0
FAILED = 0


def check(ten, dieu_kien, chi_tiet=""):
    global PASSED, FAILED
    if dieu_kien:
        PASSED += 1
        print("PASS: %s" % ten)
    else:
        FAILED += 1
        print("FAIL: %s %s" % (ten, chi_tiet))


def doi_den(app, dieu_kien, timeout=15.0, mo_ta=""):
    """Bom vong lap su kien Tk cho den khi dieu_kien() dung (hoac het gio)."""
    het = time.time() + timeout
    while time.time() < het:
        try:
            app.update()
        except tk.TclError:
            break
        if dieu_kien():
            return True
        time.sleep(0.05)
    return dieu_kien()


def tao_mp3_tone(path, tan_so=440, dai_giay=1.0):
    from pydub import AudioSegment
    from pydub.generators import Sine
    tone = Sine(tan_so).to_audio_segment(duration=int(dai_giay * 1000))
    tone = tone.set_frame_rate(24000).set_channels(1)
    tone.export(path, format="mp3")


def rms(am, a, b):
    doan = am[a:b]
    return doan.rms if len(doan) else 0


def toc_do_trong_trang_thai(app, chi_so):
    """Lay toc do (float) trong cot Trang thai cua 1 cau ('Xong (1.33x)'
    -> 1.33; 'Xong' -> None)."""
    iid = app._tree_ids.get(chi_so)
    if not iid or not app.tree_cau.exists(iid):
        return "KHONG-CO"
    tt = app.tree_cau.item(iid, "values")[4]
    mm = re.search(r"\((\d+\.\d+)x\)", tt)
    return float(mm.group(1)) if mm else None


# ---------- mock giong: moi cau doc thanh tone 4.0s (khong can mang) ----------
# Slot SRT mau: cau 1 = 3.5s, cau 2 = 3.0s, cau 3 = 4.5s, cau 4 = 3.0s,
# cau 5 = 4.0s. Voi tone 4.0s: cau 1 can ~1.14x, cau 2 ~1.33x, cau 3
# vua (1.00x), cau 4 ~1.33x, cau 5 vua (1.00x).
goi_giong = []
goi_giong_lock = threading.Lock()
TOC_DO_GIA_LAP = {"tre_giay": 0.0, "cau_loi": set()}


def mock_doc_cau(text, voice, toc_do, cao_do, duong_dan_ra, log_cb=None,
                 ffmpeg=None):
    with goi_giong_lock:
        goi_giong.append((text[:40], voice))
    for t_loi in TOC_DO_GIA_LAP["cau_loi"]:
        if text == t_loi or text.startswith(t_loi[:20]):
            return False, False, "No audio was received."
    if TOC_DO_GIA_LAP["tre_giay"]:
        time.sleep(TOC_DO_GIA_LAP["tre_giay"])
    tao_mp3_tone(duong_dan_ra, 440, 4.0)
    return True, False, ""


# Chan cac hop thoai messagebox (khong cho khoa test).
messagebox.showinfo = lambda *a, **k: None
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False

tmp = tempfile.mkdtemp(prefix="srt14-gui-")
cfg_dir = os.path.join(tmp, "cfg")
os.makedirs(cfg_dir, exist_ok=True)
luu_dir = os.path.join(tmp, "luu")
os.makedirs(luu_dir, exist_ok=True)
srt_path = os.path.join(HERE, "test-mau.srt")

# ---------- 1. Control moi ton tai + mac dinh ----------
app = m.App()
app.update()
check("checkbox tu dong ton tai",
      app.cb_tu_dong.cget("text") == "Tự động chỉnh tốc độ từng câu")
check("checkbox tu dong mac dinh BAT",
      bool(app.var_tu_dong_toc_do.get()) is True)
check("slider toc do toi da from=1.0",
      float(app.sl_toc_do_toi_da.cget("from")) == 1.0)
check("slider toc do toi da to=2.0",
      float(app.sl_toc_do_toi_da.cget("to")) == 2.0)
check("slider toc do toi da resolution=0.01",
      float(app.sl_toc_do_toi_da.cget("resolution")) == 0.01)
check("slider toc do toi da mac dinh 1.35",
      abs(float(app.sl_toc_do_toi_da.get()) - 1.35) < 0.01,
      "got %s" % app.sl_toc_do_toi_da.get())
check("nhan toc do toi da mac dinh 1.35x",
      app.lb_toc_do_toi_da.cget("text") == "1.35x",
      "got %s" % app.lb_toc_do_toi_da.cget("text"))
check("slider toc do toi da sang khi checkbox BAT",
      str(app.sl_toc_do_toi_da.cget("state")) == "normal")

# ---------- 2. Bat/tat checkbox ----------
app.var_tu_dong_toc_do.set(False)
app._doi_tu_dong_toc_do()
check("tat checkbox -> slider toi da mo",
      str(app.sl_toc_do_toi_da.cget("state")) == "disabled")
app.var_tu_dong_toc_do.set(True)
app._doi_tu_dong_toc_do()
check("bat checkbox -> slider toi da sang",
      str(app.sl_toc_do_toi_da.cget("state")) == "normal")
app.sl_toc_do_toi_da.set(1.60)
app._doi_toc_do_toi_da("1.60")
check("slider toi da 1.60 -> nhan 1.60x",
      app.lb_toc_do_toi_da.cget("text") == "1.60x")
app.sl_toc_do_toi_da.set(1.35)
app._doi_toc_do_toi_da("1.35")
check("slider toi da 1.35 -> nhan 1.35x",
      app.lb_toc_do_toi_da.cget("text") == "1.35x")

# ---------- 3. Chay day du, tu dong BAT, max 1.35x ----------
m.doc_cau_thanh_mp3 = mock_doc_cau
TOC_DO_GIA_LAP["tre_giay"] = 0.0
TOC_DO_GIA_LAP["cau_loi"] = set()
app.e_srt.delete(0, "end")
app.e_srt.insert(0, srt_path)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir)
app.sl_toc_do.set(1.0)
app._doi_toc_do("1.0")
app._nap_danh_sach_cau(srt_path)
app.update()
check("nap SRT 5 cau", len(app._tree_ids) == 5)
app.btn_bat_dau.invoke()
check("chay xong (tu dong BAT)",
      doi_den(app, lambda: not app.dang_chay, timeout=30))
check("cau 1 toc do ~1.14x",
      toc_do_trong_trang_thai(app, 1) is not None
      and abs(toc_do_trong_trang_thai(app, 1) - 1.14) < 0.05,
      "got %s" % toc_do_trong_trang_thai(app, 1))
check("cau 2 toc do ~1.33x",
      toc_do_trong_trang_thai(app, 2) is not None
      and abs(toc_do_trong_trang_thai(app, 2) - 1.33) < 0.05,
      "got %s" % toc_do_trong_trang_thai(app, 2))
check("cau 3 toc do 1.00x (vua slot)",
      toc_do_trong_trang_thai(app, 3) is not None
      and abs(toc_do_trong_trang_thai(app, 3) - 1.0) < 0.03,
      "got %s" % toc_do_trong_trang_thai(app, 3))
check("cau 4 toc do ~1.33x",
      toc_do_trong_trang_thai(app, 4) is not None
      and abs(toc_do_trong_trang_thai(app, 4) - 1.33) < 0.05,
      "got %s" % toc_do_trong_trang_thai(app, 4))
check("cau 5 toc do 1.00x (vua slot)",
      toc_do_trong_trang_thai(app, 5) is not None
      and abs(toc_do_trong_trang_thai(app, 5) - 1.0) < 0.03,
      "got %s" % toc_do_trong_trang_thai(app, 5))
log_text = app.txt_log.get("1.0", "end")
check("log bao tang toc cau 2 len 1.33x",
      "tăng tốc lên 1.33x" in log_text)
check("log KHONG canh bao tran slot khi vua max",
      "tràn sang câu sau" not in log_text)
mp3_gop = os.path.join(luu_dir, "test-mau", "test-mau_long-tieng.mp3")
check("co file gop", os.path.isfile(mp3_gop))
from pydub import AudioSegment
mp3_am = AudioSegment.from_file(mp3_gop, format="mp3")
check("file gop dai ~22s (dung timestamp SRT)",
      20000 <= len(mp3_am) <= 24000, "len=%d" % len(mp3_am))
check("file gop co audio cau 1 (1-4.5s)",
      rms(mp3_am, 1500, 2500) > 500)
check("file gop co audio cau 2 (5-8s)",
      rms(mp3_am, 5500, 7500) > 500)
check("file gop co audio cau 5 (18-22s)",
      rms(mp3_am, 18500, 21000) > 500)
check("file gop lang giua cau 1-2 (4.6-4.9s)",
      rms(mp3_am, 4600, 4900) < 100,
      "rms=%d" % rms(mp3_am, 4600, 4900))

# ---------- 4. Max 1.00x: cau dai bi cap, canh bao tran slot ----------
luu_dir2 = os.path.join(tmp, "luu2")
os.makedirs(luu_dir2, exist_ok=True)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir2)
app.sl_toc_do_toi_da.set(1.0)
app._doi_toc_do_toi_da("1.0")
app._nap_danh_sach_cau(srt_path)
app.update()
log_truoc = app.txt_log.get("1.0", "end")
app.btn_bat_dau.invoke()
check("chay xong (max 1.00x)",
      doi_den(app, lambda: not app.dang_chay, timeout=30))
check("max 1.00x: cau 1 toc do 1.00x",
      toc_do_trong_trang_thai(app, 1) == 1.0,
      "got %s" % toc_do_trong_trang_thai(app, 1))
check("max 1.00x: cau 2 toc do 1.00x",
      toc_do_trong_trang_thai(app, 2) == 1.0,
      "got %s" % toc_do_trong_trang_thai(app, 2))
log_moi = app.txt_log.get("1.0", "end")[len(log_truoc):]
check("max 1.00x: log canh bao 'tràn sang câu sau'",
      "tràn sang câu sau" in log_moi)
check("max 1.00x: log co 'Câu 2 đọc hết'",
      "Câu 2 đọc hết" in log_moi)
mp3_gop2 = os.path.join(luu_dir2, "test-mau", "test-mau_long-tieng.mp3")
check("max 1.00x: van co file gop", os.path.isfile(mp3_gop2))
app.sl_toc_do_toi_da.set(1.35)
app._doi_toc_do_toi_da("1.35")

# ---------- 5. Tat checkbox: moi cau doc dung toc do co ban ----------
luu_dir3 = os.path.join(tmp, "luu3")
os.makedirs(luu_dir3, exist_ok=True)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir3)
app.var_tu_dong_toc_do.set(False)
app._doi_tu_dong_toc_do()
app._nap_danh_sach_cau(srt_path)
app.update()
app.btn_bat_dau.invoke()
check("chay xong (tat tu dong)",
      doi_den(app, lambda: not app.dang_chay, timeout=30))
check("tat tu dong: cau 1 trang thai 'Xong' (khong toc do)",
      app.tree_cau.item(app._tree_ids[1], "values")[4] == "Xong",
      "got %s" % app.tree_cau.item(app._tree_ids[1], "values")[4])
check("tat tu dong: cau 2 trang thai 'Xong' (khong toc do)",
      app.tree_cau.item(app._tree_ids[2], "values")[4] == "Xong")
mp3_gop3 = os.path.join(luu_dir3, "test-mau", "test-mau_long-tieng.mp3")
check("tat tu dong: van co file gop", os.path.isfile(mp3_gop3))
app.var_tu_dong_toc_do.set(True)
app._doi_tu_dong_toc_do()

# ---------- 6. Huy giua chung + Tiep tuc noi dung toc do ----------
luu_dir4 = os.path.join(tmp, "luu4")
os.makedirs(luu_dir4, exist_ok=True)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir4)
TOC_DO_GIA_LAP["tre_giay"] = 0.5
app._nap_danh_sach_cau(srt_path)
app.update()
goi_giong.clear()
app.btn_bat_dau.invoke()
check("Huy: dang xuat",
      doi_den(app, lambda: app.dang_chay, timeout=5))
doi_den(app, lambda: len([f for f in os.listdir(
    os.path.join(luu_dir4, "test-mau", "tung-cau"))
    if f.endswith(".mp3")]) >= 2 if os.path.isdir(
    os.path.join(luu_dir4, "test-mau", "tung-cau")) else False, timeout=15)
app.btn_huy.invoke()
check("Huy: da huy xong",
      doi_den(app, lambda: not app.dang_chay, timeout=10))
thu_muc_kq = os.path.join(luu_dir4, "test-mau")
tien_trinh_path = os.path.join(thu_muc_kq, "tien-trinh.json")
check("Huy: tien-trinh.json ton tai", os.path.isfile(tien_trinh_path))
tt = json.load(open(tien_trinh_path, encoding="utf-8"))
check("Huy: tien trinh luu toc_do_toi_da=1.35",
      abs(float(tt.get("toc_do_toi_da", 0)) - 1.35) < 0.01,
      "toc_do_toi_da=%s" % tt.get("toc_do_toi_da"))
check("Huy: tien trinh luu tu_dong_toc_do=True",
      tt.get("tu_dong_toc_do") is True)
check("Huy: tien trinh luu toc_do_cau",
      isinstance(tt.get("toc_do_cau"), dict)
      and len(tt.get("toc_do_cau", {})) >= 2,
      str(tt.get("toc_do_cau")))
check("Huy: nut Tiep tuc sang sau khi huy",
      str(app.btn_tiep_tuc.cget("state")) == "normal")
# Tiep tuc: cau da xong hien lai dung toc do thuc, khong doc lai.
so_lan_goi_truoc = len(goi_giong)
TOC_DO_GIA_LAP["tre_giay"] = 0.0
app.btn_tiep_tuc.invoke()
check("Tiep tuc: chay lai",
      doi_den(app, lambda: app.dang_chay, timeout=5))
check("Tiep tuc: chay xong",
      doi_den(app, lambda: not app.dang_chay, timeout=30))
goi_moi = goi_giong[so_lan_goi_truoc:]
cac_cau = m.doc_srt(srt_path)
text_da_xong = {cac_cau[i - 1]["text"][:40] for i in tt["cau_da_xong"]}
goi_lai = [t for t, _ in goi_moi if t in text_da_xong]
check("Tiep tuc: khong doc lai cau da xong",
      len(goi_lai) == 0, "goi_lai=%s" % goi_lai)
check("Tiep tuc: cau 1 hien lai toc do ~1.14x",
      toc_do_trong_trang_thai(app, 1) is not None
      and abs(toc_do_trong_trang_thai(app, 1) - 1.14) < 0.05,
      "got %s" % toc_do_trong_trang_thai(app, 1))
mp3_day = AudioSegment.from_file(
    os.path.join(thu_muc_kq, "test-mau_long-tieng.mp3"), format="mp3")
check("Tiep tuc: file gop day du ~22s",
      20000 <= len(mp3_day) <= 24000, "len=%d" % len(mp3_day))
check("Tiep tuc: tien-trinh.json da xoa khi xong 100%",
      not os.path.isfile(tien_trinh_path))

# ---------- 7. Kiem tra cap nhat tim thay v1.4 (gia lap) ----------
ket_qua_gia = {"version_moi": "1.4", "tag": "v1.4",
               "tai_url": "https://example.com/SRT-Reader-HoaiMy.exe",
               "ten_file": "SRT-Reader-HoaiMy.exe",
               "kich_thuoc": 14000000}
m.kiem_tra_cap_nhat = lambda: ket_qua_gia
app.bam_kiem_tra_cap_nhat()
doi_den(app, lambda: "Có bản mới: v1.4" in app.txt_log.get("1.0", "end"),
        timeout=5)
check("Kiem tra cap nhat: tim thay v1.4",
      "Có bản mới: v1.4" in app.txt_log.get("1.0", "end"))

app.destroy()
print("\n=== KET QUA GUI: %d PASS, %d FAIL ===" % (PASSED, FAILED))
sys.exit(1 if FAILED else 0)
