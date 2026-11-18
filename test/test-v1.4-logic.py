# -*- coding: utf-8 -*-
"""Test logic v1.4 (khong can GUI, khong can mang). Chay:
  ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.4-logic.py
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    "srt14", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
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


def gan_bang(a, b, sai_so=0.01):
    return abs(float(a) - float(b)) <= sai_so


def tao_mp3_tone(path, tan_so=440, dai_giay=1.0):
    """Tao file MP3 tone sine (dung pydub, can ffmpeg de export)."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    tone = Sine(tan_so).to_audio_segment(duration=int(dai_giay * 1000))
    tone = tone.set_frame_rate(24000).set_channels(1)
    tone.export(path, format="mp3")
    return path


def rms_cua_doan(am, bat_dau_ms, ket_thuc_ms):
    doan = am[bat_dau_ms:ket_thuc_ms]
    if len(doan) == 0:
        return 0
    return doan.rms


check("VERSION = 1.4", m.VERSION == "1.4")
ffmpeg = m.tim_ffmpeg()
check("tim_ffmpeg co san", bool(ffmpeg), "ffmpeg=%s" % ffmpeg)
tmp = tempfile.mkdtemp(prefix="srt14-logic-")

# ---------------- 1. tinh toc do can ----------------
# (slot_ms, do_dai_ms, co_ban, toi_da) -> (thuc, he_so, vuot_max)
check("vua slot -> co ban",
      m._tinh_toc_do_can(5000, 3000, 1.0, 1.35) == (1.0, 1.0, False))
check("vua slot (bang) -> co ban",
      m._tinh_toc_do_can(3000, 3000, 1.0, 1.35) == (1.0, 1.0, False))
check("can 1.60x trong gioi han",
      m._tinh_toc_do_can(3000, 4800, 1.0, 2.0) == (1.6, 1.6, False),
      str(m._tinh_toc_do_can(3000, 4800, 1.0, 2.0)))
check("can 1.19x trong gioi han",
      gan_bang(m._tinh_toc_do_can(3500, 4165, 1.0, 1.35)[0], 1.19)
      and not m._tinh_toc_do_can(3500, 4165, 1.0, 1.35)[2])
check("vuot toc do toi da -> cap 1.35x",
      m._tinh_toc_do_can(3000, 6000, 1.0, 1.35) == (1.35, 1.35, True),
      str(m._tinh_toc_do_can(3000, 6000, 1.0, 1.35)))
check("co ban 1.35, can them -> cap 1.35x, khong atempo",
      m._tinh_toc_do_can(2000, 3000, 1.35, 1.35) == (1.35, 1.0, True),
      str(m._tinh_toc_do_can(2000, 3000, 1.35, 1.35)))
check("co ban 1.35, can 1.60x trong max 2.0",
      gan_bang(m._tinh_toc_do_can(2000, 2370, 1.35, 2.0)[0], 1.60)
      and gan_bang(m._tinh_toc_do_can(2000, 2370, 1.35, 2.0)[1], 1.185),
      str(m._tinh_toc_do_can(2000, 2370, 1.35, 2.0)))
check("co ban > toi da: toi da hieu dung = co ban",
      m._tinh_toc_do_can(2000, 3000, 1.5, 1.35) == (1.5, 1.0, True),
      str(m._tinh_toc_do_can(2000, 3000, 1.5, 1.35)))
check("slot <= 0 -> co ban",
      m._tinh_toc_do_can(0, 3000, 1.0, 1.35) == (1.0, 1.0, False))
check("do_dai None -> co ban",
      m._tinh_toc_do_can(3000, None, 1.0, 1.35) == (1.0, 1.0, False))
check("do_dai 0 -> co ban",
      m._tinh_toc_do_can(3000, 0, 1.0, 1.35) == (1.0, 1.0, False))
check("toi_da khong hop le -> mac dinh 1.35",
      m._tinh_toc_do_can(3000, 6000, 1.0, "x") == (1.35, 1.35, True))

# ---------------- 2. chuoi atempo ----------------
check("atempo 1.6", m._chuoi_atempo(1.6) == "atempo=1.6000",
      m._chuoi_atempo(1.6))
check("atempo 2.0", m._chuoi_atempo(2.0) == "atempo=2.0000",
      m._chuoi_atempo(2.0))
check("atempo 3.2 chuoi 2 filter",
      m._chuoi_atempo(3.2) == "atempo=2.0000,atempo=1.6000",
      m._chuoi_atempo(3.2))
check("atempo 4.0 chuoi 2 filter",
      m._chuoi_atempo(4.0) == "atempo=2.0000,atempo=2.0000",
      m._chuoi_atempo(4.0))
check("atempo 8.0 chuoi 3 filter",
      m._chuoi_atempo(8.0) == "atempo=2.0000,atempo=2.0000,atempo=2.0000",
      m._chuoi_atempo(8.0))

# ---------------- 3. uoc luong thoi luong ----------------
check("uoc luong 135 ky tu o 1.0x = 10000ms",
      m._uoc_luong_thoi_luong_ms("x" * 135, 1.0) == 10000,
      str(m._uoc_luong_thoi_luong_ms("x" * 135, 1.0)))
check("uoc luong 135 ky tu o 1.35x ~7407ms",
      7000 <= m._uoc_luong_thoi_luong_ms("x" * 135, 1.35) <= 7800,
      str(m._uoc_luong_thoi_luong_ms("x" * 135, 1.35)))
check("uoc luong chuoi rong = 0",
      m._uoc_luong_thoi_luong_ms("", 1.0) == 0)
check("uoc luong None = 0", m._uoc_luong_thoi_luong_ms(None, 1.0) == 0)

# ---------------- 4. do thoi luong that ----------------
tone2 = os.path.join(tmp, "tone2.mp3")
tao_mp3_tone(tone2, 440, 2.0)
do_dai2 = m._do_dai_mp3_ms(tone2, ffmpeg)
check("do dai MP3 2.0s ~2000ms",
      do_dai2 is not None and 1850 <= do_dai2 <= 2200,
      "do_dai=%s" % do_dai2)
check("do dai file khong co -> None",
      m._do_dai_mp3_ms(os.path.join(tmp, "khong-co.mp3"), ffmpeg) is None)
rong_path = os.path.join(tmp, "rong.mp3")
open(rong_path, "wb").close()
check("do dai file rong -> None",
      m._do_dai_mp3_ms(rong_path, ffmpeg) is None)

# ---------------- 5. tang toc MP3 bang atempo ----------------
tone3 = os.path.join(tmp, "tone3.mp3")
tao_mp3_tone(tone3, 440, 3.0)
check("tang toc 1.5x OK", m._tang_toc_mp3(tone3, 1.5, ffmpeg))
sau15 = m._do_dai_mp3_ms(tone3, ffmpeg)
check("tang toc 1.5x: 3.0s -> ~2.0s",
      sau15 is not None and 1800 <= sau15 <= 2200, "sau=%s" % sau15)
tone4 = os.path.join(tmp, "tone4.mp3")
tao_mp3_tone(tone4, 440, 4.0)
check("tang toc 3.0x (chuoi atempo) OK", m._tang_toc_mp3(tone4, 3.0, ffmpeg))
sau30 = m._do_dai_mp3_ms(tone4, ffmpeg)
check("tang toc 3.0x: 4.0s -> ~1.33s",
      sau30 is not None and 1150 <= sau30 <= 1550, "sau=%s" % sau30)
check("tang toc he_so <= 1.0 -> False",
      not m._tang_toc_mp3(tone4, 1.0, ffmpeg))
check("tang toc khong ffmpeg -> False",
      not m._tang_toc_mp3(tone4, 1.5, None))

# ---------------- 6. ap dung toc do tu dong (end-to-end) ----------------
cau_slot_2s = {"chi_so": 2, "bat_dau_ms": 5000, "ket_thuc_ms": 7000,
               "text": "x" * 40}
# 6a. Tat tu dong -> tra ve co ban, file khong doi.
f_off = os.path.join(tmp, "off.mp3")
tao_mp3_tone(f_off, 440, 3.0)
log_off = []
toc = m._ap_dung_toc_do_tu_dong(f_off, cau_slot_2s, 1.0, 1.35, False,
                                ffmpeg, log_cb=log_off.append)
check("tat tu dong -> tra co ban 1.0", toc == 1.0, "toc=%s" % toc)
check("tat tu dong -> file khong doi (~3.0s)",
      2800 <= m._do_dai_mp3_ms(f_off, ffmpeg) <= 3200)
check("tat tu dong -> khong log gi", log_off == [])
# 6b. Vua slot -> co ban, khong atempo.
f_vua = os.path.join(tmp, "vua.mp3")
tao_mp3_tone(f_vua, 440, 1.5)
toc = m._ap_dung_toc_do_tu_dong(f_vua, cau_slot_2s, 1.0, 1.35, True,
                                ffmpeg, log_cb=lambda s: None)
check("vua slot -> co ban 1.0", toc == 1.0, "toc=%s" % toc)
# 6c. Can 1.60x trong max 2.0: tone 3.2s, slot 2.0s -> ~1.6x, vua slot.
f_160 = os.path.join(tmp, "c160.mp3")
tao_mp3_tone(f_160, 440, 3.2)
log_160 = []
toc = m._ap_dung_toc_do_tu_dong(f_160, cau_slot_2s, 1.0, 2.0, True,
                                ffmpeg, log_cb=log_160.append)
check("can 1.60x -> toc do thuc ~1.6x",
      gan_bang(toc, 1.6, 0.08), "toc=%s" % toc)
sau_160 = m._do_dai_mp3_ms(f_160, ffmpeg)
check("can 1.60x -> file vua slot ~2.0s",
      sau_160 is not None and 1800 <= sau_160 <= 2200, "sau=%s" % sau_160)
check("can 1.60x -> log bao tang toc 1.6x",
      any("tăng tốc lên 1.6" in s for s in log_160), str(log_160))
check("can 1.60x -> khong canh bao tran slot",
      not any("tràn sang câu sau" in s for s in log_160))
# 6d. Vuot max: tone 3.0s, slot 2.0s, max 1.35 -> cap 1.35x, van tran.
f_max = os.path.join(tmp, "vmax.mp3")
tao_mp3_tone(f_max, 440, 3.0)
log_max = []
toc = m._ap_dung_toc_do_tu_dong(f_max, cau_slot_2s, 1.0, 1.35, True,
                                ffmpeg, log_cb=log_max.append)
check("vuot max -> cap dung 1.35x", toc == 1.35, "toc=%s" % toc)
sau_max = m._do_dai_mp3_ms(f_max, ffmpeg)
check("vuot max -> file van dai hon slot (~2.2s)",
      sau_max is not None and sau_max > 2000, "sau=%s" % sau_max)
check("vuot max -> log canh bao 'tràn sang câu sau'",
      any("tràn sang câu sau" in s for s in log_max), str(log_max))
check("vuot max -> log co dung so 'Câu 2 đọc hết'",
      any("Câu 2 đọc hết" in s for s in log_max), str(log_max))
# 6e. Khong co ffmpeg -> tra co ban (khong do duoc thi uoc luong, nhung
# khong tang toc duoc).
f_nof = os.path.join(tmp, "nof.mp3")
tao_mp3_tone(f_nof, 440, 3.0)
log_nof = []
toc = m._ap_dung_toc_do_tu_dong(f_nof, cau_slot_2s, 1.0, 1.35, True,
                                None, log_cb=log_nof.append)
check("khong ffmpeg -> tra co ban 1.0", toc == 1.0, "toc=%s" % toc)
check("khong ffmpeg -> log bao thieu ffmpeg",
      any("thiếu ffmpeg" in s for s in log_nof), str(log_nof))
# 6f. Slot 0 -> co ban.
f_s0 = os.path.join(tmp, "s0.mp3")
tao_mp3_tone(f_s0, 440, 1.0)
cau_s0 = {"chi_so": 9, "bat_dau_ms": 5000, "ket_thuc_ms": 5000, "text": "x"}
check("slot 0 -> co ban",
      m._ap_dung_toc_do_tu_dong(f_s0, cau_s0, 1.0, 1.35, True, ffmpeg)
      == 1.0)

# ---------------- 7. gop dan voi file da tang toc ----------------
from pydub import AudioSegment
cac_cau = m.doc_srt(os.path.join(HERE, "test-mau.srt"))
# Cau 2 SRT mau: slot 5000->8000 (3.0s). Tone 4.5s -> 1.5x -> 3.0s vua slot.
thu_muc_rieng = os.path.join(tmp, "tung-cau")
os.makedirs(thu_muc_rieng, exist_ok=True)
f_c2 = os.path.join(thu_muc_rieng, "002.mp3")
tao_mp3_tone(f_c2, 660, 4.5)
toc2 = m._ap_dung_toc_do_tu_dong(f_c2, cac_cau[1], 1.0, 2.0, True,
                                 ffmpeg, log_cb=lambda s: None)
check("gop dan: cau 2 tang toc ~1.5x", gan_bang(toc2, 1.5, 0.08),
      "toc=%s" % toc2)
wav_path = os.path.join(tmp, "gop-tam.wav")
mp3_path = os.path.join(tmp, "gop.mp3")
gop = m.GopDan(wav_path, mp3_path, tong_ms=22000,
               log_cb=lambda s: None)
check("gop dan: them cau 2 da tang toc OK",
      gop.them_cau(cac_cau[1], f_c2))
check("gop dan: khong dem tran slot (vua slot sau khi tang toc)",
      gop.tran_slot == 0, "tran_slot=%d" % gop.tran_slot)
wav = AudioSegment.from_file(wav_path, format="wav")
check("gop dan: audio cau 2 dung vi tri (5-8s)",
      rms_cua_doan(wav, 5500, 7500) > 1000)
check("gop dan: lang ngay sau slot cau 2 (8-9s)",
      rms_cua_doan(wav, 8100, 8900) < 100,
      "rms=%d" % rms_cua_doan(wav, 8100, 8900))
ok_gop, tong_ms = gop.hoan_tat(ffmpeg)
check("gop dan: hoan tat OK", ok_gop)
mp3_gop = AudioSegment.from_file(mp3_path, format="mp3")
check("gop dan: MP3 dai ~22s", 20000 <= len(mp3_gop) <= 24000,
      "len=%d" % len(mp3_gop))
check("gop dan: MP3 co audio cau 2 dung vi tri",
      rms_cua_doan(mp3_gop, 5500, 7500) > 500)

# ---------------- 8. config mac dinh moi ----------------
cfg = m.doc_config()
check("config mac dinh toc_do_toi_da=1.35",
      cfg.get("toc_do_toi_da") == 1.35, str(cfg.get("toc_do_toi_da")))
check("config mac dinh tu_dong_toc_do=True",
      cfg.get("tu_dong_toc_do") is True)

# ---------------- 9. luu tien trinh co toc_do_cau ----------------
thu_muc_tt = os.path.join(tmp, "tien-trinh-test")
du_lieu_tt = {"srt": "/tmp/test.srt", "tong_cau": 5, "cau_da_xong": [1, 2],
              "toc_do": 1.0, "toc_do_toi_da": 1.35, "tu_dong_toc_do": True,
              "toc_do_cau": {"1": 1.0, "2": 1.6}, "che_do": "gop"}
check("luu tien trinh v1.4 OK",
      m._luu_tien_trinh(thu_muc_tt, du_lieu_tt))
doc_tt = m._doc_tien_trinh(thu_muc_tt)
check("doc tien trinh co toc_do_cau",
      doc_tt and doc_tt.get("toc_do_cau") == {"1": 1.0, "2": 1.6},
      str(doc_tt and doc_tt.get("toc_do_cau")))

print("\n=== KET QUA: %d PASS, %d FAIL ===" % (PASSED, FAILED))
sys.exit(1 if FAILED else 0)
