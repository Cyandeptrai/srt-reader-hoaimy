# -*- coding: utf-8 -*-
"""Test logic v1.3 (khong can GUI, khong can mang - tru test live cuoi
cung, co the bo qua neu khong co mang). Chay:
  ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.3-logic.py
"""
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    "srt13", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
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


def tao_mp3_tone(path, tan_so=440, dai_giay=1.0):
    """Tao file MP3 tone sine (dung pydub, can ffmpeg de export)."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    tone = Sine(tan_so).to_audio_segment(duration=int(dai_giay * 1000))
    tone = tone.set_frame_rate(24000).set_channels(1)
    tone.export(path, format="mp3")
    return path


def rms_cua_doan(am, bat_dau_ms, ket_thuc_ms):
    """RMS cua 1 doan trong AudioSegment (0 neu im lang)."""
    doan = am[bat_dau_ms:ket_thuc_ms]
    if len(doan) == 0:
        return 0
    return doan.rms


# ---------------- 1. toc do he so nhan ----------------
check("dinh_dang 1.0x", m._dinh_dang_toc_do(1.0) == "1.00x")
check("dinh_dang 1.35x", m._dinh_dang_toc_do(1.35) == "1.35x")
check("dinh_dang 0.5x", m._dinh_dang_toc_do(0.5) == "0.50x")
check("dinh_dang 2.0x", m._dinh_dang_toc_do(2.0) == "2.00x")
check("sang phan tram 1.35->35", m._toc_do_sang_phan_tram(1.35) == 35)
check("sang phan tram 1.0->0", m._toc_do_sang_phan_tram(1.0) == 0)
check("sang phan tram 0.5->-50", m._toc_do_sang_phan_tram(0.5) == -50)
check("sang phan tram 2.0->100", m._toc_do_sang_phan_tram(2.0) == 100)
check("sang edge 1.35->+35%", m._toc_do_sang_edge(1.35) == "+35%")
check("sang edge 1.0->+0%", m._toc_do_sang_edge(1.0) == "+0%")
check("sang edge 0.5->-50%", m._toc_do_sang_edge(0.5) == "-50%")
check("chuyen cu 9 -> 1.09", m._chuyen_toc_do_cu(9) == 1.09)
check("chuyen cu 0 -> 1.0", m._chuyen_toc_do_cu(0) == 1.0)
check("chuyen cu -50 -> 0.5", m._chuyen_toc_do_cu(-50) == 0.5)
check("chuyen cu 50 -> 1.5", m._chuyen_toc_do_cu(50) == 1.5)
check("chuyen cu 1.35 giu nguyen", m._chuyen_toc_do_cu(1.35) == 1.35)
check("chuyen cu '1.35' -> 1.35", m._chuyen_toc_do_cu("1.35") == 1.35)
check("chuyen cu None -> 1.0", m._chuyen_toc_do_cu(None) == 1.0)
check("chuyen cu 999 -> 1.0", m._chuyen_toc_do_cu(999) == 1.0)
check("chuyen cu True -> 1.0", m._chuyen_toc_do_cu(True) == 1.0)

# ---------------- 2. tom tat loi ----------------
loi_dai = "Dong 1 loi o day\nDong 2\nDong 3 " + "x" * 300
tom = m._tom_tat_loi(loi_dai)
check("tom_tat_loi chi lay dong dau", "\n" not in tom and tom.startswith("Dong 1"))
check("tom_tat_loi cat <=160 ky tu", len(tom) <= 163, "len=%d" % len(tom))
check("tom_tat_loi chuoi rong -> ten kieu (khong tra ve rong)",
      m._tom_tat_loi("") == "str")
check("tom_tat_loi None -> 'None' (khong tra ve rong)",
      m._tom_tat_loi(None) == "None")

# ---------------- 3. so sanh version ----------------
check("so_sanh 1.3 > 1.2", m.so_sanh_version("1.3", "1.2") > 0)
check("so_sanh 1.10 > 1.2", m.so_sanh_version("1.10", "1.2") > 0)
check("so_sanh 1.2 < 1.3", m.so_sanh_version("1.2", "1.3") < 0)
check("so_sanh 1.3 == 1.3", m.so_sanh_version("1.3", "1.3") == 0)
check("so_sanh v1.3 > v1.2", m.so_sanh_version("v1.3", "v1.2") > 0)

# ---------------- 4. doc SRT mau ----------------
cac_cau = m.doc_srt(os.path.join(HERE, "test-mau.srt"))
check("doc_srt 5 cau", len(cac_cau) == 5, "len=%d" % len(cac_cau))
check("doc_srt cau 1 bat dau 1000ms",
      cac_cau[0]["bat_dau_ms"] == 1000 and cac_cau[0]["ket_thuc_ms"] == 4500)
check("doc_srt cau 5 ket thuc 22000ms", cac_cau[4]["ket_thuc_ms"] == 22000)

# ---------------- 5. GopDan (gop dan) ----------------
tmp = tempfile.mkdtemp(prefix="srt13-gopdan-")
ffmpeg = m.tim_ffmpeg()
check("tim_ffmpeg co san", bool(ffmpeg), "ffmpeg=%s" % ffmpeg)
thu_muc_rieng = os.path.join(tmp, "tung-cau")
os.makedirs(thu_muc_rieng, exist_ok=True)
# 3 cau tone khac tan so, dung slot SRT mau (cau 1,2,3).
for chi_so, tan_so, dai in ((1, 440, 3.5), (2, 660, 3.0), (3, 880, 4.5)):
    tao_mp3_tone(os.path.join(thu_muc_rieng, "%03d.mp3" % chi_so),
                 tan_so, dai)
wav_path = os.path.join(tmp, "test_long-tieng-tam.wav")
mp3_path = os.path.join(tmp, "test_long-tieng.mp3")
log_lines = []
gop = m.GopDan(wav_path, mp3_path, log_cb=log_lines.append)
# Them cau 1: file WAV tam xuat hien ngay, audio dung vi tri.
ok1 = gop.them_cau(cac_cau[0], os.path.join(thu_muc_rieng, "001.mp3"))
check("GopDan them cau 1 OK", ok1 and gop.so_cau == 1)
check("GopDan WAV tam ton tai ngay sau cau 1", os.path.isfile(wav_path))
from pydub import AudioSegment
wav1 = AudioSegment.from_file(wav_path, format="wav")
check("GopDan WAV cau 1 co audio dung vi tri",
      rms_cua_doan(wav1, 1500, 2500) > 1000,
      "rms=%d" % rms_cua_doan(wav1, 1500, 2500))
check("GopDan WAV khoang lang truoc cau 1",
      rms_cua_doan(wav1, 100, 900) < 100,
      "rms=%d" % rms_cua_doan(wav1, 100, 900))
# Them cau 2, 3.
check("GopDan them cau 2 OK",
      gop.them_cau(cac_cau[1], os.path.join(thu_muc_rieng, "002.mp3")))
check("GopDan them cau 3 OK",
      gop.them_cau(cac_cau[2], os.path.join(thu_muc_rieng, "003.mp3")))
wav2 = AudioSegment.from_file(wav_path, format="wav")
check("GopDan WAV cau 2 dung vi tri",
      rms_cua_doan(wav2, 5500, 6500) > 1000)
check("GopDan WAV khoang lang giua cau 1-2",
      rms_cua_doan(wav2, 4600, 4900) < 100,
      "rms=%d" % rms_cua_doan(wav2, 4600, 4900))
check("GopDan WAV cau 3 dung vi tri",
      rms_cua_doan(wav2, 9500, 12000) > 1000)
# Cau thieu file -> bo qua, khong lam hong file gop.
check("GopDan cau thieu file -> False",
      not gop.them_cau(cac_cau[3], os.path.join(thu_muc_rieng, "004.mp3")))
check("GopDan bo_qua=1 sau cau thieu", gop.bo_qua == 1)
check("GopDan log bo qua cau 4",
      any("Đã bỏ qua câu 4" in s for s in log_lines))
# Cau file hong (ghi rac) -> bo qua.
with open(os.path.join(thu_muc_rieng, "005.mp3"), "wb") as f:
    f.write(b"DAY KHONG PHAI MP3" * 100)
check("GopDan cau file hong -> False",
      not gop.them_cau(cac_cau[4], os.path.join(thu_muc_rieng, "005.mp3")))
check("GopDan bo_qua=2 sau cau hong", gop.bo_qua == 2)
# Cau file rong (0 byte) -> bo qua.
open(os.path.join(thu_muc_rieng, "006.mp3"), "wb").close()
cau_rong = {"chi_so": 6, "bat_dau_ms": 23000, "ket_thuc_ms": 25000,
            "text": "rong"}
check("GopDan cau file rong -> False",
      not gop.them_cau(cau_rong, os.path.join(thu_muc_rieng, "006.mp3")))
check("GopDan bo_qua=3 sau cau rong", gop.bo_qua == 3)
# Cau tran slot: audio 5s, slot 2s.
tao_mp3_tone(os.path.join(thu_muc_rieng, "007.mp3"), 550, 5.0)
cau_tran = {"chi_so": 7, "bat_dau_ms": 26000, "ket_thuc_ms": 28000,
            "text": "tran"}
log_truoc = len(log_lines)
check("GopDan cau tran slot van ghep duoc",
      gop.them_cau(cau_tran, os.path.join(thu_muc_rieng, "007.mp3")))
check("GopDan tran_slot=1", gop.tran_slot == 1)
check("GopDan log canh bao tran slot",
      any("tràn" in s or "tran" in s for s in log_lines[log_truoc:]))
# Hoan tat: WAV -> MP3, xoa WAV tam.
ok_gop, tong_ms = gop.hoan_tat(ffmpeg)
check("GopDan hoan_tat OK", ok_gop)
check("GopDan MP3 ton tai", os.path.isfile(mp3_path))
check("GopDan WAV tam da xoa", not os.path.isfile(wav_path))
mp3_gop = AudioSegment.from_file(mp3_path, format="mp3")
check("GopDan MP3 dai ~31s (cau tran ket thuc 31s)",
      29000 <= len(mp3_gop) <= 33000, "len=%d" % len(mp3_gop))
check("GopDan MP3 cau 1 dung vi tri",
      rms_cua_doan(mp3_gop, 1500, 2500) > 500)
check("GopDan MP3 slot cau 4 loi van lang",
      rms_cua_doan(mp3_gop, 14500, 16500) < 100,
      "rms=%d" % rms_cua_doan(mp3_gop, 14500, 16500))
# Hoan tat khi chua co cau nao.
gop2 = m.GopDan(os.path.join(tmp, "rong-tam.wav"),
                os.path.join(tmp, "rong.mp3"))
check("GopDan rong hoan_tat -> (False, 0)",
      gop2.hoan_tat(ffmpeg) == (False, 0))
# File WAV tam du dai tong_ms ngay tu cau dau (du cau cuoi ngan hon slot).
gop3 = m.GopDan(os.path.join(tmp, "du-tam.wav"),
                os.path.join(tmp, "du.mp3"), tong_ms=22000,
                log_cb=lambda s: None)
check("GopDan tong_ms: them cau 1 OK",
      gop3.them_cau(cac_cau[0], os.path.join(thu_muc_rieng, "001.mp3")))
check("GopDan tong_ms: WAV dai du 22000ms ngay sau cau 1",
      gop3.do_dai_ms() == 22000, "do_dai=%d" % gop3.do_dai_ms())
ok3, tong3 = gop3.hoan_tat(ffmpeg)
check("GopDan tong_ms: hoan_tat OK va dai 22000ms",
      ok3 and tong3 == 22000, "tong=%d" % tong3)

# ---------------- 6. kiem chung PyInstaller ----------------
# Exe Windows that (Chipchipdownload) - neu co tren may.
for ten_exe in ("Chipchipdownload.exe", "Gop-Video-Bilibili.exe"):
    p = os.path.join(os.path.expanduser("~"), "workspace", "muse-manager",
                     ten_exe)
    if os.path.isfile(p):
        ok_pi, ly_do = m.kiem_chung_pyinstaller(p)
        check("kiem_chung_pyinstaller %s" % ten_exe, ok_pi, ly_do)
# Exe Linux vua build (lib ten libpython3.12.so.1.0).
exe_linux = "/tmp/pyi-test/dist/app_test"
if os.path.isfile(exe_linux):
    ok_pi, ly_do = m.kiem_chung_pyinstaller(
        exe_linux, ten_dll="libpython3.12.so.1.0")
    check("kiem_chung_pyinstaller exe Linux", ok_pi, ly_do)
    ok_pi2, _ = m.kiem_chung_pyinstaller(exe_linux)
    check("kiem_chung_pyinstaller exe Linux sai ten dll -> False",
          not ok_pi2)
    # File cat 50% -> False.
    with open(exe_linux, "rb") as f:
        du_lieu = f.read()
    cat_path = os.path.join(tmp, "app_cat")
    with open(cat_path, "wb") as f:
        f.write(du_lieu[:len(du_lieu) // 2])
    ok_pi3, ly_do3 = m.kiem_chung_pyinstaller(
        cat_path, ten_dll="libpython3.12.so.1.0")
    check("kiem_chung_pyinstaller file cat 50% -> False",
          not ok_pi3, ly_do3)
# File ngau nhien / nho.
rand_path = os.path.join(tmp, "random.bin")
with open(rand_path, "wb") as f:
    f.write(os.urandom(5000000))
check("kiem_chung_pyinstaller file ngau nhien -> False",
      not m.kiem_chung_pyinstaller(rand_path)[0])
nho_path = os.path.join(tmp, "nho.bin")
with open(nho_path, "wb") as f:
    f.write(b"MZ" + b"\x00" * 50)
check("kiem_chung_pyinstaller file nho -> False",
      not m.kiem_chung_pyinstaller(nho_path)[0])

# ---------------- 7. kiem tra file cap nhat ----------------
# File hop le phai la exe Windows that (co python311.dll). Dung
# Chipchipdownload.exe (exe Windows PyInstaller that, co tren may).
exe_win = None
for ten_exe in ("Chipchipdownload.exe", "Gop-Video-Bilibili.exe"):
    p = os.path.join(os.path.expanduser("~"), "workspace", "muse-manager",
                     ten_exe)
    if os.path.isfile(p):
        exe_win = p
        break
if exe_win:
    size_win = os.path.getsize(exe_win)
    check("kiem_tra_file_cap_nhat hop le -> ''",
          m.kiem_tra_file_cap_nhat(exe_win, size_win) == "")
    check("kiem_tra_file_cap_nhat sai kich thuoc -> loi",
          "chỉ có" in m.kiem_tra_file_cap_nhat(exe_win, size_win + 100))
if os.path.isfile(exe_linux):
    size_linux = os.path.getsize(exe_linux)
    check("kiem_tra_file_cap_nhat file cat -> loi",
          m.kiem_tra_file_cap_nhat(cat_path, size_linux) != "")
check("kiem_tra_file_cap_nhat file khong co -> loi",
      m.kiem_tra_file_cap_nhat(os.path.join(tmp, "khong-co.exe"), 100) != "")

# ---------------- 8. luu/doc/xoa tien trinh ----------------
thu_muc_tt = os.path.join(tmp, "tien-trinh-test")
du_lieu_tt = {"srt": "/tmp/test.srt", "tong_cau": 5, "cau_da_xong": [1, 2],
              "toc_do": 1.35, "che_do": "gop", "thu_muc": thu_muc_tt}
check("luu tien trinh OK", m._luu_tien_trinh(thu_muc_tt, du_lieu_tt))
doc_tt = m._doc_tien_trinh(thu_muc_tt)
check("doc tien trinh khop",
      doc_tt and doc_tt["cau_da_xong"] == [1, 2]
      and doc_tt["toc_do"] == 1.35)
m._xoa_tien_trinh(thu_muc_tt)
check("xoa tien trinh OK", m._doc_tien_trinh(thu_muc_tt) is None)

# ---------------- 9. PowerShell giong may ----------------
ps = m._ps_giong_may("Xin chào, tôi là giọng máy.", 1.35, 0, None, False)
check("ps giong may co System.Speech", "System.Speech" in ps)
check("ps giong may Rate=7 cho 1.35x", "$synth.Rate = 7" in ps)
# Script luon chua khoi SSML (de phong truong hop can dung), nhung chi
# chay khi dung_ssml=True - kiem tra bang co bao ve if ($false).
check("ps giong may khong chay SSML khi cao_do=0", "if ($false)" in ps)
ps2 = m._ps_giong_may("Xin chào.", 1.35, 5, "/tmp/x.wav", True)
check("ps giong may co SSML khi cao_do!=0", "SpeakSsml" in ps2)
check("ps giong may SSML rate +35%", 'rate="+35%"' in ps2)
check("ps giong may SSML pitch +5Hz", 'pitch="+5Hz"' in ps2)
ps3 = m._ps_giong_may("Xin chào.", 0.5, 0, None, False)
check("ps giong may Rate=-10 cho 0.5x", "$synth.Rate = -10" in ps3)
ps4 = m._ps_giong_may("Xin chào.", 2.0, 0, None, False)
check("ps giong may Rate=10 cho 2.0x", "$synth.Rate = 10" in ps4)
ps5 = m._ps_giong_may("Tôi nói: 'xin chào' nhé.", 1.0, 0, None, False)
check("ps giong may thoat dau nhay don",
      "''xin chào''" in ps5 or "xin chào" in ps5)
check("ps giong may chon giong vi-*", "vi*" in ps)

# ---------------- 10. dispatcher giong ----------------
ok_may, _, loi_may = m.doc_cau_thanh_mp3(
    "Xin chào.", "may", 1.0, 0, os.path.join(tmp, "may.mp3"),
    log_cb=lambda s: None, ffmpeg=ffmpeg)
check("dispatcher giong may tren Linux -> loi Windows",
      not ok_may and "Windows" in loi_may, loi_may)
ok_nghe, loi_nghe = m.nghe_giong_may("Xin chào.", 1.0, 0)
check("nghe_giong_may tren Linux -> loi Windows",
      not ok_nghe and "Windows" in loi_nghe, loi_nghe)

# ---------------- 11. phat MP3 (Linux: ffplay) ----------------
tone_path = os.path.join(tmp, "phat.mp3")
tao_mp3_tone(tone_path, 440, 1.0)
ok_phat, loi_phat = m._phat_mp3(tone_path)
check("phat MP3 tren Linux (ffplay)", ok_phat, loi_phat)
dung = m.threading.Event()
dung.set()
ok_phat2, loi_phat2 = m._phat_mp3(tone_path, dung=dung)
check("phat MP3 bi dung ngay -> False + 'đã dừng'",
      not ok_phat2 and "đã dừng" in loi_phat2, loi_phat2)

# ---------------- 12. ghi log loi ffmpeg ----------------
m._ghi_log_loi_ffmpeg(tmp, "dong loi ffmpeg gia lap\n" * 3)
check("ffmpeg-loi.log duoc ghi",
      os.path.isfile(os.path.join(tmp, "ffmpeg-loi.log")))
check("tom tat loi ffmpeg ngan",
      len(m._tom_tat_loi("Decoding failed\n" + "x" * 500)) <= 163)

print("\n=== KET QUA: %d PASS, %d FAIL ===" % (PASSED, FAILED))
sys.exit(1 if FAILED else 0)
