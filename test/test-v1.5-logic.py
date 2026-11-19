# -*- coding: utf-8 -*-
"""Test logic v1.5 (khong can GUI, khong can mang). Chuan hoa dinh dang MP3
dau ra ve 44.1kHz stereo 192k (sua loi file v1.4 24kHz mono import vao
Concat bi ffmpeg bao 'filter output failed: Invalid argument').
Chay:
  ~/workspace/muse-manager/srt-reader-hoaimy-venv/bin/python test/test-v1.5-logic.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    "srt15", os.path.join(ROOT, "SRT-Reader-HoaiMy.py"))
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
    """Tao file MP3 tone sine gia lap MP3 goc cua edge-tts: 24kHz mono."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    tone = Sine(tan_so).to_audio_segment(duration=int(dai_giay * 1000))
    tone = tone.set_frame_rate(24000).set_channels(1)
    tone.export(path, format="mp3")
    return path


def thong_so_mp3(path):
    """Tra ve (sample_rate, channels, bit_rate) cua file MP3 qua ffprobe."""
    ffprobe = m.tim_ffprobe(ffmpeg)
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
    """File MP3 co dung dinh dang chuan v1.5 khong: 44100Hz, stereo,
    bitrate ~192k (cho sai so do VBR/lam tron header)."""
    ts = thong_so_mp3(path)
    if ts is None:
        return False, "khong doc duoc ffprobe"
    sr, ch, br = ts
    return (sr == 44100 and ch == 2 and 180000 <= br <= 210000,
            "sr=%s ch=%s br=%s" % (sr, ch, br))


def rms_cua_doan(am, bat_dau_ms, ket_thuc_ms):
    doan = am[bat_dau_ms:ket_thuc_ms]
    if len(doan) == 0:
        return 0
    return doan.rms


check("VERSION = 1.5", m.VERSION == "1.5")
check("hang so MP3 chuan: tan so 44100",
      m.MP3_CHUAN_TAN_SO == 44100)
check("hang so MP3 chuan: 2 kenh (stereo)",
      m.MP3_CHUAN_KENH == 2)
check("hang so MP3 chuan: bitrate 192k",
      m.MP3_CHUAN_BITRATE == "192k")
ffmpeg = m.tim_ffmpeg()
check("tim_ffmpeg co san", bool(ffmpeg), "ffmpeg=%s" % ffmpeg)
tmp = tempfile.mkdtemp(prefix="srt15-logic-")

# ---------------- 1. MP3 goc gia lap edge-tts la 24kHz mono ----------------
goc = os.path.join(tmp, "goc.mp3")
tao_mp3_tone(goc, 440, 4.0)
ts_goc = thong_so_mp3(goc)
check("MP3 goc (gia lap edge-tts) la 24kHz mono",
      ts_goc is not None and ts_goc[0] == 24000 and ts_goc[1] == 1,
      "ts=%s" % (ts_goc,))

# ---------------- 2. atempo ra MP3 chuan ----------------
f_at = os.path.join(tmp, "atempo.mp3")
tao_mp3_tone(f_at, 440, 4.0)
check("tang toc 1.6x OK", m._tang_toc_mp3(f_at, 1.6, ffmpeg))
ok_chuan, ct = la_mp3_chuan(f_at)
check("atempo 1.6x -> MP3 chuan 44100/stereo/192k", ok_chuan, ct)
sau = m._do_dai_mp3_ms(f_at, ffmpeg)
check("atempo 1.6x: 4.0s -> ~2.5s",
      sau is not None and 2300 <= sau <= 2700, "sau=%s" % sau)
f_at3 = os.path.join(tmp, "atempo3.mp3")
tao_mp3_tone(f_at3, 440, 4.0)
check("tang toc 3.0x (chuoi atempo) OK",
      m._tang_toc_mp3(f_at3, 3.0, ffmpeg))
ok_chuan3, ct3 = la_mp3_chuan(f_at3)
check("atempo 3.0x -> MP3 chuan 44100/stereo/192k", ok_chuan3, ct3)
sau3 = m._do_dai_mp3_ms(f_at3, ffmpeg)
check("atempo 3.0x: 4.0s -> ~1.33s",
      sau3 is not None and 1150 <= sau3 <= 1550, "sau=%s" % sau3)
check("tang toc he_so <= 1.0 -> False (hoi quy v1.4)",
      not m._tang_toc_mp3(f_at3, 1.0, ffmpeg))

# ---------------- 3. GopDan: cau 24kHz mono -> MP3 gop chuan ----------------
from pydub import AudioSegment
wav_path = os.path.join(tmp, "gop-tam.wav")
mp3_path = os.path.join(tmp, "gop.mp3")
gop = m.GopDan(wav_path, mp3_path, tong_ms=12000, log_cb=lambda s: None)
for i in range(1, 4):
    f_cau = os.path.join(tmp, "cau%d.mp3" % i)
    tao_mp3_tone(f_cau, 440 + i * 100, 4.0)
    cau = {"chi_so": i, "bat_dau_ms": (i - 1) * 4000,
           "ket_thuc_ms": i * 4000, "text": "x"}
    check("gop dan: them cau %d (24kHz mono) OK" % i,
          gop.them_cau(cau, f_cau))
ok_gop, tong_ms = gop.hoan_tat(ffmpeg)
check("gop dan: hoan tat OK", ok_gop)
ok_chuan_g, ct_g = la_mp3_chuan(mp3_path)
check("gop dan: MP3 gop cuoi chuan 44100/stereo/192k", ok_chuan_g, ct_g)
mp3_gop = AudioSegment.from_file(mp3_path, format="mp3")
check("gop dan: MP3 dai ~12s", 11000 <= len(mp3_gop) <= 13000,
      "len=%d" % len(mp3_gop))
check("gop dan: audio cau 1 dung vi tri (0.5-3.5s)",
      rms_cua_doan(mp3_gop, 500, 3500) > 500)
check("gop dan: audio cau 3 dung vi tri (8.5-11.5s)",
      rms_cua_doan(mp3_gop, 8500, 11500) > 500)

# ---------------- 4. GopDan: cau dau da atempo (44.1kHz stereo) ----------------
wav2 = os.path.join(tmp, "gop2-tam.wav")
mp3_2 = os.path.join(tmp, "gop2.mp3")
gop2 = m.GopDan(wav2, mp3_2, tong_ms=9000, log_cb=lambda s: None)
f_dau = os.path.join(tmp, "dau-atempo.mp3")
tao_mp3_tone(f_dau, 660, 4.5)
check("cau dau atempo 1.5x OK", m._tang_toc_mp3(f_dau, 1.5, ffmpeg))
ok_dau, ct_dau = la_mp3_chuan(f_dau)
check("cau dau sau atempo da la MP3 chuan", ok_dau, ct_dau)
cau1 = {"chi_so": 1, "bat_dau_ms": 0, "ket_thuc_ms": 3000, "text": "x"}
check("gop dan 2: them cau dau da atempo OK", gop2.them_cau(cau1, f_dau))
f_sau = os.path.join(tmp, "sau-thuong.mp3")
tao_mp3_tone(f_sau, 440, 3.0)
cau2 = {"chi_so": 2, "bat_dau_ms": 3000, "ket_thuc_ms": 6000, "text": "x"}
check("gop dan 2: them cau sau (24kHz mono) OK",
      gop2.them_cau(cau2, f_sau))
ok_gop2, _ = gop2.hoan_tat(ffmpeg)
check("gop dan 2: hoan tat OK", ok_gop2)
ok_chuan2, ct2 = la_mp3_chuan(mp3_2)
check("gop dan 2: MP3 gop cuoi chuan 44100/stereo/192k", ok_chuan2, ct2)

# ---------------- 5. Chuyen MP3 v1.5 sang M4A (mo phong Concat) ----------------
def mp3_sang_m4a(duong_dan, ten, them_filter=None):
    out = os.path.join(tmp, ten + ".m4a")
    af = "aresample=48000:async=1,pan=stereo|c0=c0|c1=c0"
    if them_filter:
        af = af + "," + them_filter
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", duong_dan,
                        "-vn", "-af", af, "-c:a", "aac", "-b:a", "128k",
                        out], capture_output=True, text=True, timeout=120)
    return (r.returncode == 0 and os.path.isfile(out)
            and os.path.getsize(out) > 0), (r.stderr or "").strip()[:200]


ok_m4a, err_m4a = mp3_sang_m4a(mp3_path, "gop-m4a")
check("MP3 v1.5 -> M4A (resample 48k stereo, mo phong Concat) OK",
      ok_m4a, err_m4a)
ok_m4a2, err_m4a2 = mp3_sang_m4a(mp3_2, "gop2-m4a",
                                "loudnorm=I=-16:TP=-1.5:LRA=11")
check("MP3 v1.5 (tron cau atempo/thuong) -> M4A + loudnorm OK",
      ok_m4a2, err_m4a2)
ok_m4a3, err_m4a3 = mp3_sang_m4a(f_at, "atempo-m4a")
check("MP3 cau atempo v1.5 -> M4A OK", ok_m4a3, err_m4a3)
# Doi chieu: file 24kHz mono cu (v1.4) cung chuyen duoc bang ffmpeg 8.1
# tren VM (loi Concat chi tai hien tren may CYAN / ffmpeg cua Concat).
f_cu = os.path.join(tmp, "cu-24k.mp3")
tao_mp3_tone(f_cu, 440, 2.0)
ok_cu, _ = mp3_sang_m4a(f_cu, "cu-m4a")
check("doi chieu: MP3 24kHz mono cu van chuyen M4A duoc tren VM",
      ok_cu, "chi de doi chieu, khong phai loi")

# ---------------- 6. Export pydub chuan hoa (mau duong cau dai) ----------------
# Cung cac lenh nhu doc_thanh_mp3 / doc_giong_may khi noi cac doan dai:
# set_frame_rate(44100).set_channels(2).export(bitrate="192k").
am_noi = AudioSegment.empty()
for tan_so in (440, 550):
    from pydub.generators import Sine
    am_noi += Sine(tan_so).to_audio_segment(duration=1500)
am_noi = am_noi.set_frame_rate(24000).set_channels(1)  # gia lap noi goc
f_noi = os.path.join(tmp, "noi.mp3")
(am_noi.set_frame_rate(m.MP3_CHUAN_TAN_SO)
        .set_channels(m.MP3_CHUAN_KENH)
        .export(f_noi, format="mp3", bitrate=m.MP3_CHUAN_BITRATE))
ok_noi, ct_noi = la_mp3_chuan(f_noi)
check("export pydub chuan hoa -> MP3 chuan 44100/stereo/192k",
      ok_noi, ct_noi)
am_noi_doc = AudioSegment.from_file(f_noi, format="mp3")
check("export pydub chuan hoa -> dai ~3.0s",
      2800 <= len(am_noi_doc) <= 3200, "len=%d" % len(am_noi_doc))

# ---------------- 7. hoi quy v1.4: tinh toc do can ----------------
check("hoi quy: vua slot -> co ban",
      m._tinh_toc_do_can(5000, 3000, 1.0, 1.35) == (1.0, 1.0, False))
check("hoi quy: can 1.60x trong gioi han",
      m._tinh_toc_do_can(3000, 4800, 1.0, 2.0) == (1.6, 1.6, False))
check("hoi quy: vuot max -> cap 1.35x",
      m._tinh_toc_do_can(3000, 6000, 1.0, 1.35) == (1.35, 1.35, True))
check("hoi quy: chuoi atempo 3.2",
      m._chuoi_atempo(3.2) == "atempo=2.0000,atempo=1.6000")

print("\n=== KET QUA: %d PASS, %d FAIL ===" % (PASSED, FAILED))
sys.exit(1 if FAILED else 0)
