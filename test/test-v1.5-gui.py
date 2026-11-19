# -*- coding: utf-8 -*-
"""Test GUI v1.5 duoi Xvfb (khong can mang - giong duoc gia lap bang tone
4.0s moi cau, 24kHz mono nhu MP3 goc cua edge-tts). Kiem tra file MP3
gop that xuat qua giao dien co dung dinh dang chuan v1.5 (44.1kHz
stereo 192k) va chuyen sang M4A duoc (mo phong Concat).
Chay:
  xvfb-run -a ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.5-gui.py
"""
import importlib.util
import os
import subprocess
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
    "srt15gui", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
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


def doi_den(app, dieu_kien, timeout=30.0, mo_ta=""):
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


def thong_so_mp3(path):
    ffprobe = m.tim_ffprobe(m.tim_ffmpeg())
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                        "stream=sample_rate,channels,bit_rate",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        path], capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    dong = [d.strip() for d in r.stdout.strip().split("\n") if d.strip()]
    try:
        return int(dong[0]), int(dong[1]), int(dong[2])
    except (IndexError, ValueError):
        return None


def la_mp3_chuan(path):
    ts = thong_so_mp3(path)
    if ts is None:
        return False, "khong doc duoc ffprobe"
    sr, ch, br = ts
    return (sr == 44100 and ch == 2 and 180000 <= br <= 210000,
            "sr=%s ch=%s br=%s" % (sr, ch, br))


def mp3_sang_m4a(duong_dan, ten):
    ffmpeg = m.tim_ffmpeg()
    out = os.path.join(tmp, ten + ".m4a")
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", duong_dan,
                        "-vn", "-af",
                        "aresample=48000:async=1,pan=stereo|c0=c0|c1=c0",
                        "-c:a", "aac", "-b:a", "128k", out],
                       capture_output=True, text=True, timeout=120)
    return (r.returncode == 0 and os.path.isfile(out)
            and os.path.getsize(out) > 0), (r.stderr or "").strip()[:200]


def rms(am, a, b):
    doan = am[a:b]
    return doan.rms if len(doan) else 0


# ---------- mock giong: moi cau doc thanh tone 4.0s (khong can mang) ----------
goi_giong_lock = threading.Lock()


def mock_doc_cau(text, voice, toc_do, cao_do, duong_dan_ra, log_cb=None,
                 ffmpeg=None):
    tao_mp3_tone(duong_dan_ra, 440, 4.0)
    return True, False, ""


messagebox.showinfo = lambda *a, **k: None
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False

tmp = tempfile.mkdtemp(prefix="srt15-gui-")
luu_dir = os.path.join(tmp, "luu")
os.makedirs(luu_dir, exist_ok=True)
srt_path = os.path.join(HERE, "test-mau.srt")

app = m.App()
app.update()
check("title v1.5", "1.5" in app.title(), app.title())

# ---------- 1. Xuat day du, tu dong BAT, max 1.35x ----------
m.doc_cau_thanh_mp3 = mock_doc_cau
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
mp3_gop = os.path.join(luu_dir, "test-mau", "test-mau_long-tieng.mp3")
check("co file gop", os.path.isfile(mp3_gop))
ok_chuan, ct = la_mp3_chuan(mp3_gop)
check("GUI: file gop chuan 44100/stereo/192k", ok_chuan, ct)
from pydub import AudioSegment
mp3_am = AudioSegment.from_file(mp3_gop, format="mp3")
check("GUI: file gop dai ~22s (dung timestamp SRT)",
      20000 <= len(mp3_am) <= 24000, "len=%d" % len(mp3_am))
check("GUI: file gop co audio cau 1 (1-4.5s)",
      rms(mp3_am, 1500, 2500) > 500)
check("GUI: file gop co audio cau 2 (5-8s)",
      rms(mp3_am, 5500, 7500) > 500)
check("GUI: file gop co audio cau 5 (18-22s)",
      rms(mp3_am, 18500, 21000) > 500)
ok_m4a, err_m4a = mp3_sang_m4a(mp3_gop, "gui-gop-m4a")
check("GUI: file gop -> M4A (mo phong Concat) OK", ok_m4a, err_m4a)

# ---------- 2. Tat tu dong: file gop van chuan ----------
luu_dir2 = os.path.join(tmp, "luu2")
os.makedirs(luu_dir2, exist_ok=True)
app.e_luu.delete(0, "end")
app.e_luu.insert(0, luu_dir2)
app.var_tu_dong_toc_do.set(False)
app._doi_tu_dong_toc_do()
app._nap_danh_sach_cau(srt_path)
app.update()
app.btn_bat_dau.invoke()
check("chay xong (tat tu dong)",
      doi_den(app, lambda: not app.dang_chay, timeout=30))
mp3_gop2 = os.path.join(luu_dir2, "test-mau", "test-mau_long-tieng.mp3")
check("tat tu dong: van co file gop", os.path.isfile(mp3_gop2))
ok_chuan2, ct2 = la_mp3_chuan(mp3_gop2)
check("GUI: file gop (tat tu dong) chuan 44100/stereo/192k",
      ok_chuan2, ct2)
ok_m4a2, err_m4a2 = mp3_sang_m4a(mp3_gop2, "gui-gop2-m4a")
check("GUI: file gop (tat tu dong) -> M4A OK", ok_m4a2, err_m4a2)
app.var_tu_dong_toc_do.set(True)
app._doi_tu_dong_toc_do()

print("\n=== KET QUA: %d PASS, %d FAIL ===" % (PASSED, FAILED))
try:
    app.destroy()
except Exception:
    pass
sys.exit(1 if FAILED else 0)
