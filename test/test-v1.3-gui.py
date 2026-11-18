# -*- coding: utf-8 -*-
"""Test GUI v1.3 duoi Xvfb (khong can mang - giong duoc gia lap bang tone).
Chay:
  xvfb-run -a ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.3-gui.py
"""
import importlib.util
import json
import os
import shutil
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
    "srt13gui", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
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


# ---------- mock giong (khong can mang) ----------
goi_giong = []  # (text, voice) cac lan goi doc_cau_thanh_mp3
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
    tao_mp3_tone(duong_dan_ra, 440, 1.0)
    return True, False, ""


def mock_doc_thanh_mp3(text, voice, toc_do, cao_do, duong_dan_ra,
                       log_cb=None):
    # Dung cho nut Nghe thu: tao tone theo do dai van ban (de test nut Dung).
    dai = TOC_DO_GIA_LAP.get("nghe_thu_giay", 1.0)
    tao_mp3_tone(duong_dan_ra, 440, dai)
    return True, False, ""


# Chan cac hop thoai messagebox (khong cho khoa test).
messagebox.showinfo = lambda *a, **k: None
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False

tmp = tempfile.mkdtemp(prefix="srt13-gui-")
cfg_dir = os.path.join(tmp, "cfg")
os.makedirs(cfg_dir, exist_ok=True)
luu_dir = os.path.join(tmp, "luu")
os.makedirs(luu_dir, exist_ok=True)
srt_path = os.path.join(HERE, "test-mau.srt")

# ---------- 1. Config cu (toc_do phan tram) tu doi sang he so nhan ----------
with open(os.path.join(cfg_dir, "config.json"), "w",
          encoding="utf-8") as f:
    json.dump({"giong": "HoaiMy (nữ)", "toc_do": 9, "cao_do": 0,
               "thu_muc_luu": luu_dir, "che_do": "gop"}, f)
m.config_path = lambda: os.path.join(cfg_dir, "config.json")
app = m.App()
app.update()
check("slider toc do from=0.5", float(app.sl_toc_do.cget("from")) == 0.5)
check("slider toc do to=2.0", float(app.sl_toc_do.cget("to")) == 2.0)
check("slider toc do resolution=0.01",
      float(app.sl_toc_do.cget("resolution")) == 0.01)
check("config cu toc_do=9 -> slider 1.09x",
      abs(float(app.sl_toc_do.get()) - 1.09) < 0.01,
      "got %s" % app.sl_toc_do.get())
check("config cu toc_do=9 -> nhan 1.09x",
      app.lb_toc_do.cget("text") == "1.09x",
      "got %s" % app.lb_toc_do.cget("text"))
app.sl_toc_do.set(1.35)
app._doi_toc_do("1.35")
check("slider 1.35 -> nhan 1.35x", app.lb_toc_do.cget("text") == "1.35x")
app.sl_toc_do.set(1.0)
app._doi_toc_do("1.0")
check("slider 1.0 -> nhan 1.00x", app.lb_toc_do.cget("text") == "1.00x")

# ---------- 2. Nut Nghe thu / Tiep tuc / Sub lai ton tai ----------
check("nut Nghe thu ton tai", app.btn_nghe_thu.cget("text") == "▶ Nghe thử")
check("nut Dung ton tai, mo luc dau",
      app.btn_dung_nghe.cget("text") == "Dừng"
      and str(app.btn_dung_nghe.cget("state")) == "disabled")
check("nut Tiep tuc mo khi chua nap SRT",
      str(app.btn_tiep_tuc.cget("state")) == "disabled")
check("nut Sub lai mo khi chua nap SRT",
      str(app.btn_sub_lai.cget("state")) == "disabled")
check("giong may co trong danh sach",
      "Giọng máy (cũ)" in list(app.cb_giong.cget("values")))

# ---------- 3. Nap SRT ----------
app.e_srt.delete(0, "end")
app.e_srt.insert(0, srt_path)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir)
app._nap_danh_sach_cau(srt_path)
app.update()
check("nap SRT 5 cau", len(app._tree_ids) == 5)
check("nut Sub lai sang sau khi nap SRT",
      str(app.btn_sub_lai.cget("state")) == "normal")
check("nut Tiep tuc mo khi chua co tien trinh",
      str(app.btn_tiep_tuc.cget("state")) == "disabled")

# ---------- 4. Chan nut + Huy van luu (giong cham 0.5s/cau) ----------
m.doc_cau_thanh_mp3 = mock_doc_cau
m.doc_thanh_mp3 = mock_doc_thanh_mp3
TOC_DO_GIA_LAP["tre_giay"] = 0.5
TOC_DO_GIA_LAP["cau_loi"] = set()
goi_giong.clear()
app.btn_bat_dau.invoke()
# Doi cho chay that (nut Huy sang).
check("dang xuat sau khi bam XUAT",
      doi_den(app, lambda: app.dang_chay, timeout=5))
# Kiem tra nut bi chan trong luc xuat.
for ten_btn, btn in (("Kiem tra giong", app.btn_kiem_tra),
                     ("Kiem tra cap nhat", app.btn_cap_nhat),
                     ("Chon SRT", app.btn_chon_srt),
                     ("Chon thu muc", app.btn_chon_luu),
                     ("Tiep tuc", app.btn_tiep_tuc),
                     ("Sub lai", app.btn_sub_lai),
                     ("XUAT", app.btn_bat_dau),
                     ("Nghe thu", app.btn_nghe_thu)):
    check("nut %s mo trong luc xuat" % ten_btn,
          str(btn.cget("state")) == "disabled")
check("nut Huy sang trong luc xuat",
      str(app.btn_huy.cget("state")) == "normal")
# Doi 2 cau xong roi bam Huy.
doi_den(app, lambda: len([f for f in os.listdir(
    os.path.join(luu_dir, "test-mau", "tung-cau"))
    if f.endswith(".mp3")]) >= 2 if os.path.isdir(
    os.path.join(luu_dir, "test-mau", "tung-cau")) else False, timeout=10)
app.btn_huy.invoke()
check("da huy xong (dang_chay=False)",
      doi_den(app, lambda: not app.dang_chay, timeout=10))
thu_muc_kq = os.path.join(luu_dir, "test-mau")
thu_muc_rieng = os.path.join(thu_muc_kq, "tung-cau")
mp3_gop = os.path.join(thu_muc_kq, "test-mau_long-tieng.mp3")
tien_trinh_path = os.path.join(thu_muc_kq, "tien-trinh.json")
so_file_cau = len([f for f in os.listdir(thu_muc_rieng)
                   if f.endswith(".mp3")]) if os.path.isdir(thu_muc_rieng) else 0
check("Huy: file cac cau da xong van con (>=2)",
      so_file_cau >= 2, "so_file=%d" % so_file_cau)
check("Huy: file gop do ton tai", os.path.isfile(mp3_gop))
check("Huy: tien-trinh.json ton tai", os.path.isfile(tien_trinh_path))
tt = json.load(open(tien_trinh_path, encoding="utf-8"))
check("Huy: tien trinh co cau_da_xong",
      len(tt.get("cau_da_xong", [])) >= 2, str(tt.get("cau_da_xong")))
check("Huy: tien trinh luu toc_do he so nhan",
      abs(float(tt.get("toc_do", 0)) - 1.0) < 0.01,
      "toc_do=%s" % tt.get("toc_do"))
check("Huy: log bao 'Đã hủy ở câu'",
      "Đã hủy ở câu" in app.txt_log.get("1.0", "end"))
check("Huy: nut Tiep tuc sang sau khi huy",
      str(app.btn_tiep_tuc.cget("state")) == "normal")
check("Huy: nut Kiem tra giong sang lai sau khi huy",
      str(app.btn_kiem_tra.cget("state")) == "normal")
# File gop do co dung cac cau da xong (do dai > 0, doc duoc).
from pydub import AudioSegment
mp3_do = AudioSegment.from_file(mp3_gop, format="mp3")
check("Huy: file gop do doc duoc, dai > 5s",
      len(mp3_do) > 5000, "len=%d" % len(mp3_do))

# ---------- 5. Tiep tuc: khong doc lai cau da xong, noi vao file cu ----------
so_lan_goi_truoc = len(goi_giong)
TOC_DO_GIA_LAP["tre_giay"] = 0.0
app.btn_tiep_tuc.invoke()
check("Tiep tuc: chay lai sau khi bam Tiep tuc",
      doi_den(app, lambda: app.dang_chay, timeout=5))
check("Tiep tuc: chay xong",
      doi_den(app, lambda: not app.dang_chay, timeout=15))
goi_moi = goi_giong[so_lan_goi_truoc:]
# Cac cau da xong o lan truoc (chi_so trong tt) khong duoc goi lai.
# Text cac cau da xong: lay tu SRT.
cac_cau = m.doc_srt(srt_path)
text_da_xong = {cac_cau[i - 1]["text"][:40] for i in tt["cau_da_xong"]}
goi_lai = [t for t, _ in goi_moi if t in text_da_xong]
check("Tiep tuc: khong doc lai cau da xong",
      len(goi_lai) == 0, "goi_lai=%s" % goi_lai)
check("Tiep tuc: doc not cac cau con lai",
      len(goi_moi) == 5 - len(tt["cau_da_xong"]),
      "goi_moi=%d, can=%d" % (len(goi_moi), 5 - len(tt["cau_da_xong"])))
mp3_day = AudioSegment.from_file(mp3_gop, format="mp3")
check("Tiep tuc: file gop day du ~22s",
      20000 <= len(mp3_day) <= 24000, "len=%d" % len(mp3_day))
check("Tiep tuc: tien-trinh.json da xoa khi xong 100%",
      not os.path.isfile(tien_trinh_path))
check("Tiep tuc: nut Tiep tuc mo lai sau khi xong 100%",
      str(app.btn_tiep_tuc.cget("state")) == "disabled")
# File gop day du co ca 5 cau (kiem tra audio o vi tri moi cau).
def rms(am, a, b):
    doan = am[a:b]
    return doan.rms if len(doan) else 0
check("Tiep tuc: file gop co audio cau 1 (1-4.5s)",
      rms(mp3_day, 1500, 2500) > 500)
check("Tiep tuc: file gop co audio cau 5 (18-22s)",
      rms(mp3_day, 18500, 21000) > 500)

# ---------- 6. Sub lai tu dau: tao thu muc moi, khong ghi de ----------
mtime_cu = os.path.getmtime(mp3_gop)
size_cu = os.path.getsize(mp3_gop)
app.btn_sub_lai.invoke()
check("Sub lai: chay lai sau khi bam",
      doi_den(app, lambda: app.dang_chay, timeout=5))
check("Sub lai: chay xong",
      doi_den(app, lambda: not app.dang_chay, timeout=15))
thu_muc_moi = os.path.join(luu_dir, "test-mau (1)")
check("Sub lai: tao thu muc moi 'test-mau (1)'",
      os.path.isdir(thu_muc_moi))
check("Sub lai: file gop cu khong bi ghi de",
      os.path.getmtime(mp3_gop) == mtime_cu
      and os.path.getsize(mp3_gop) == size_cu)
check("Sub lai: thu muc moi co file gop day du",
      os.path.isfile(os.path.join(thu_muc_moi,
                                  "test-mau_long-tieng.mp3")))

# ---------- 7. Cau loi khong lam hong file gop ----------
# Dung thu muc luu moi de chay sach (tranh tien trinh cu).
luu_dir2 = os.path.join(tmp, "luu2")
os.makedirs(luu_dir2, exist_ok=True)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir2)
app._nap_danh_sach_cau(srt_path)
app.update()
TOC_DO_GIA_LAP["cau_loi"] = {"Và từ giây phút đó, vận mệnh của hắn bắt đầu thay đổi."}
TOC_DO_GIA_LAP["tre_giay"] = 0.0
goi_giong.clear()
app.btn_bat_dau.invoke()
check("Cau loi: chay xong",
      doi_den(app, lambda: not app.dang_chay, timeout=15))
mp3_loi = os.path.join(luu_dir2, "test-mau", "test-mau_long-tieng.mp3")
check("Cau loi: van co file gop", os.path.isfile(mp3_loi))
mp3_loi_am = AudioSegment.from_file(mp3_loi, format="mp3")
check("Cau loi: file gop doc duoc, dai ~22s",
      20000 <= len(mp3_loi_am) <= 24000, "len=%d" % len(mp3_loi_am))
log_text = app.txt_log.get("1.0", "end")
check("Cau loi: log bao 'Đã bỏ qua câu 3 (không có audio)'",
      "Đã bỏ qua câu 3 (không có audio)" in log_text)
check("Cau loi: log KHONG chua output tho ffmpeg",
      "Decoding failed" not in log_text
      and "MPEG audio frames" not in log_text
      and "Failed to find two consecutive" not in log_text)
check("Cau loi: slot cau 3 van lang (khong co audio)",
      rms(mp3_loi_am, 9500, 12000) < 100,
      "rms=%d" % rms(mp3_loi_am, 9500, 12000))
check("Cau loi: cau 4 van co audio",
      rms(mp3_loi_am, 14500, 16500) > 500)
TOC_DO_GIA_LAP["cau_loi"] = set()

# ---------- 8. Nghe thu: PLAY ra loa + Dung ----------
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir)
TOC_DO_GIA_LAP["nghe_thu_giay"] = 1.0
app.e_nghe_thu.delete(0, "end")
app.e_nghe_thu.insert(0, "Xin chào, đây là câu nghe thử.")
app.btn_nghe_thu.invoke()
check("Nghe thu: dang_nghe=True sau khi bam",
      doi_den(app, lambda: app.dang_nghe, timeout=5))
check("Nghe thu: nut Nghe thu mo trong luc nghe",
      str(app.btn_nghe_thu.cget("state")) == "disabled")
check("Nghe thu: nut Dung sang trong luc nghe",
      str(app.btn_dung_nghe.cget("state")) == "normal")
check("Nghe thu: xong, nut Nghe thu sang lai",
      doi_den(app, lambda: (not app.dang_nghe
                            and str(app.btn_nghe_thu.cget("state"))
                            == "normal"), timeout=10))
check("Nghe thu: nut Dung mo lai sau khi xong",
      str(app.btn_dung_nghe.cget("state")) == "disabled")
# Nghe thu cau dang chon trong danh sach (o trong).
app.e_nghe_thu.delete(0, "end")
iid = app._tree_ids[2]
app.tree_cau.selection_set(iid)
app.btn_nghe_thu.invoke()
check("Nghe thu cau chon: chay",
      doi_den(app, lambda: app.dang_nghe, timeout=5))
check("Nghe thu cau chon: xong",
      doi_den(app, lambda: not app.dang_nghe, timeout=10))
# Nut Dung: nghe 1 doan dai 5s roi dung giua chung.
TOC_DO_GIA_LAP["nghe_thu_giay"] = 5.0
app.e_nghe_thu.delete(0, "end")
app.e_nghe_thu.insert(0, "Đoạn nghe thử dài để bấm dừng.")
app.btn_nghe_thu.invoke()
doi_den(app, lambda: app.dang_nghe, timeout=5)
time.sleep(0.5)
app.btn_dung_nghe.invoke()
check("Dung nghe thu: dung trong 2s",
      doi_den(app, lambda: not app.dang_nghe, timeout=3))
TOC_DO_GIA_LAP["nghe_thu_giay"] = 1.0

# ---------- 9. Kiem tra cap nhat tim thay v1.3 (gia lap) ----------
ket_qua_gia = {"version_moi": "1.3", "tag": "v1.3",
               "tai_url": "https://example.com/SRT-Reader-HoaiMy.exe",
               "ten_file": "SRT-Reader-HoaiMy.exe",
               "kich_thuoc": 14000000}
m.kiem_tra_cap_nhat = lambda: ket_qua_gia
log_truoc = app.txt_log.get("1.0", "end")
app.bam_kiem_tra_cap_nhat()
doi_den(app, lambda: "Có bản mới: v1.3" in app.txt_log.get("1.0", "end"),
        timeout=5)
check("Kiem tra cap nhat: tim thay v1.3",
      "Có bản mới: v1.3" in app.txt_log.get("1.0", "end"))

app.destroy()
print("\n=== KET QUA GUI: %d PASS, %d FAIL ===" % (PASSED, FAILED))
sys.exit(1 if FAILED else 0)
