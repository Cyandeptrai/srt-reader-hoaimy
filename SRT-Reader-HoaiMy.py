# -*- coding: utf-8 -*-
"""
SRT Reader HoaiMy - Doc file phu de SRT bang giong Microsoft Edge TTS.
Giong: HoaiMy (nu, vi-VN-HoaiMyNeural) mac dinh, NamMinh (nam, vi-VN-NamMinhNeural),
va Giong may (cu) - giong tieng Viet co san tren may Windows (SAPI, vd Microsoft An).
Khong can API key: dung dich vu Edge TTS mien phi (speech.platform.bing.com).
Dau ra: tung cau rieng (MP3) va/hoac 1 file gop dat dung moc thoi gian SRT (dub track).
Toc do: he so nhan 0.5x-2.0x (mac dinh 1.00x), giong trang web test.
Phien ban: 1.4 (toc do tu dong theo tung cau: cau dai doc nhanh hon
toi da toc-do-toi-da mac dinh 1.35x, dung ffmpeg atempo tang toc file da
tao, khong goi lai API TTS; cau nao cung khong kip du o toc do toi da
thi log canh bao tran slot; trang thai hien toc do thuc tung cau)
"""
import asyncio
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import traceback
import queue
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "SRT Reader HoaiMy"
VERSION = "1.4"
# Ten file exe that su (khac APP_TITLE: exe dung gach noi, khong dung khoang trang).
EXE_TEN = "SRT-Reader-HoaiMy.exe"
GITHUB_REPO = "Cyandeptrai/srt-reader-hoaimy"
GITHUB_API_LATEST_RELEASE = ("https://api.github.com/repos/"
                             + GITHUB_REPO + "/releases/latest")
GITHUB_RAW_VERSION_JSON = ("https://raw.githubusercontent.com/"
                           + GITHUB_REPO + "/main/version.json")
GITHUB_RELEASES_URL = "https://github.com/" + GITHUB_REPO + "/releases"
UA_TRINH_DUYET = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36")

GIONG_MAY = "Giọng máy (cũ)"  # giong SAPI tieng Viet co san tren may Windows
GIONG = {
    "HoaiMy (nữ)": "vi-VN-HoaiMyNeural",
    "NamMinh (nam)": "vi-VN-NamMinhNeural",
    GIONG_MAY: "may",
}
GIONG_MAC_DINH = "HoaiMy (nữ)"
MAU_DOC_THU = "Xin chào, đây là giọng đọc thử."
DO_DAI_TOI_DA_MOT_LAN = 500  # ky tu; cau dai hon se tach nho


# ---------------- thu muc / config ----------------

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.path.join(app_dir(), "config.json")


def mac_dinh_thu_muc_luu():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.expanduser("~")
    return os.path.join(desktop, "SRT-HoaiMy")


def doc_config():
    mac_dinh = {
        "giong": GIONG_MAC_DINH,
        # v1.3: toc do luu dang HE SO NHAN (1.0x mac dinh, 0.5x-2.0x)
        # giong trang web test - khong con dang phan tram nhu v1.2.
        "toc_do": 1.0,
        "cao_do": 0,
        "thu_muc_luu": mac_dinh_thu_muc_luu(),
        # v1.4 - toc do tu dong theo tung cau (giong iContent): cau dai
        # doc nhanh hon, toi da toc_do_toi_da (mac dinh 1.35x, 1.00x-
        # 2.00x). Tat tu_dong_toc_do thi moi cau doc dung toc do co ban
        # (hanh vi cu v1.3).
        "toc_do_toi_da": 1.35,
        "tu_dong_toc_do": True,
        # Mac dinh: gop 1 file MP3 long tieng (track long tieng dung timestamp
        # SRT). Muon tung cau rieng thi chon o muc Dau ra.
        "che_do": "gop",
    }
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in mac_dinh.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return mac_dinh


def luu_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------- ffmpeg ----------------

def tim_ffmpeg():
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    for cand in [
        os.path.join(app_dir(), "ffmpeg.exe"),
        os.path.join(app_dir(), "ffmpeg"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\iContent\ffmpeg\bin\ffmpeg.exe",
        r"C:\iContent\.venv\Scripts\ffmpeg.exe",
    ]:
        if os.path.isfile(cand):
            return cand
    return None


def tim_ffprobe(ffmpeg):
    if not ffmpeg:
        return None
    import shutil
    p = shutil.which("ffprobe")
    if p:
        return p
    d = os.path.dirname(ffmpeg)
    for cand in [os.path.join(d, "ffprobe.exe"), os.path.join(d, "ffprobe")]:
        if os.path.isfile(cand):
            return cand
    return None


# ---------------- SRT ----------------

_TS_RE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)
_TAG_RE = re.compile(r"<[^>]+>")


def _ts_sang_ms(h, m, s, ms):
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def _dinh_dang_ms(ms):
    """ms -> chuoi 'HH:MM:SS,mmm' de hien trong danh sach cau."""
    ms = int(ms)
    s, mmm = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d,%03d" % (h, m, s, mmm)


def doc_srt(duong_dan):
    """Tra ve list dict: {chi_so, bat_dau_ms, ket_thuc_ms, text}."""
    with open(duong_dan, "r", encoding="utf-8-sig", errors="replace") as f:
        noi_dung = f.read()
    noi_dung = noi_dung.replace("\r\n", "\n").replace("\r", "\n")
    khoi = [k.strip("\n") for k in re.split(r"\n\s*\n", noi_dung) if k.strip()]
    ket_qua = []
    chi_so_tu_dong = 0
    for k in khoi:
        dong = [d for d in k.split("\n") if d.strip() != ""]
        if not dong:
            continue
        i_ts = None
        chi_so = None
        for i, d in enumerate(dong):
            if _TS_RE.search(d):
                i_ts = i
                break
        if i_ts is None:
            continue
        m = _TS_RE.search(dong[i_ts])
        bat_dau = _ts_sang_ms(m.group(1), m.group(2), m.group(3), m.group(4))
        ket_thuc = _ts_sang_ms(m.group(5), m.group(6), m.group(7), m.group(8))
        if i_ts == 1:
            try:
                chi_so = int(dong[0].strip())
            except ValueError:
                chi_so = None
        if chi_so is None:
            chi_so_tu_dong += 1
            chi_so = chi_so_tu_dong
        else:
            chi_so_tu_dong = max(chi_so_tu_dong, chi_so)
        text = " ".join(dong[i_ts + 1:])
        text = _TAG_RE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        ket_qua.append({
            "chi_so": chi_so,
            "bat_dau_ms": bat_dau,
            "ket_thuc_ms": ket_thuc,
            "text": text,
        })
    ket_qua.sort(key=lambda x: x["bat_dau_ms"])
    return ket_qua


def tach_cau_dai(text, gioi_han=DO_DAI_TOI_DA_MOT_LAN):
    """Tach cau dai thanh nhieu doan ngan de Edge TTS doc on dinh."""
    if len(text) <= gioi_han:
        return [text]
    doan = []
    tam = ""
    for cau in re.split(r"(?<=[.!?;:,])\s+", text):
        if len(tam) + len(cau) + 1 <= gioi_han:
            tam = (tam + " " + cau).strip()
        else:
            if tam:
                doan.append(tam)
            if len(cau) > gioi_han:
                # cat cung theo khoang trang
                while len(cau) > gioi_han:
                    cat = cau.rfind(" ", 0, gioi_han)
                    cat = cat if cat > 0 else gioi_han
                    doan.append(cau[:cat].strip())
                    cau = cau[cat:].strip()
                if cau:
                    tam = cau
                else:
                    tam = ""
            else:
                tam = cau
    if tam:
        doan.append(tam)
    return [d for d in doan if d]


# ---------------- Edge TTS ----------------

def la_loi_chung_chi_ssl(e):
    s = str(e).lower()
    return ("certificate" in s or "ssl" in s or "wrong_version_number" in s
            or "self-signed" in s or "cert" in s)


# ---------------- tu cap nhat (v1.1, theo mau Chipchipdownload v6.2/v6.3) ----------------
# Repo PUBLIC nen KHONG can token GitHub: doc Releases qua API khong xac thuc,
# fallback doc version.json raw tren main. Tai exe qua browser_download_url
# (link truc tiep, khong can auth).

def so_sanh_version(a, b):
    """So sanh 2 chuoi version dang '1.2' / 'v1.10': tra 1 neu a>b, -1 neu
    a<b, 0 neu bang. So theo tung cum so (1.10 > 1.2), khong so chuoi."""
    def tach(s):
        s = (s or "").strip().lstrip("vV")
        parts = []
        for p in s.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return parts
    pa, pb = tach(a), tach(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    if pa > pb:
        return 1
    if pa < pb:
        return -1
    return 0


def mo_url_co_fallback_ssl(req, timeout, log_cb=None):
    """Mo URL bang urllib: thu TRUOC bang SSL context mac dinh (xac minh
    chung chi). Chi khi loi la do xac minh chung chi that bai moi thu lai
    bang context khong xac minh, va ghi ro vao log (mau Chipchipdownload
    v6.3 - sua loi SSL CERTIFICATE_VERIFY_FAILED)."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        if not la_loi_chung_chi_ssl(e):
            raise
        if log_cb:
            log_cb("Loi chung chi SSL, thu lai khong xac minh chung chi "
                   "(kho chung chi tren may co the thieu/bi chan)...")
        try:
            return urllib.request.urlopen(
                req, timeout=timeout,
                context=ssl._create_unverified_context())
        except Exception as e2:
            raise RuntimeError(
                "Loi chung chi SSL ca khi da thu bo xac minh (%s). "
                "Nguyen nhan co the: phan mem diet virus hoac proxy tren "
                "may chan chung chi SSL." % e2)


def tai_file_qua_url(url, dest, timeout, log_cb, ten, headers=None):
    """Tai 1 file qua HTTP(S) ve dest, dung mo_url_co_fallback_ssl.
    Raise RuntimeError neu tai that bai."""
    head = {"User-Agent": UA_TRINH_DUYET}
    if headers:
        head.update(headers)
    req = urllib.request.Request(url, headers=head)
    with mo_url_co_fallback_ssl(req, timeout, log_cb) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _xoa_file_quiet(path):
    """Xoa file, bo qua moi loi (dung khi file tai ve bi hong)."""
    try:
        os.remove(path)
    except OSError:
        pass


def _tom_tat_loi(e, gioi_han=160):
    """Lay dong dau tien cua loi, cat ngan de hien len giao dien (v1.3:
    KHONG hien toan bo log tho ffmpeg dai, nhay lien tuc - log ffmpeg
    day du chi ghi vao file, xem _ghi_log_loi_ffmpeg)."""
    s = str(e).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > gioi_han:
        s = s[:gioi_han].rstrip() + "..."
    return s or type(e).__name__


def _ghi_log_loi_ffmpeg(thu_muc, noi_dung):
    """Ghi log loi ffmpeg DAY DU vao file ffmpeg-loi.log trong thu muc ket
    qua (de chan doan sau), thay vi hien toan bo len man hinh (v1.3)."""
    try:
        os.makedirs(thu_muc, exist_ok=True)
        with open(os.path.join(thu_muc, "ffmpeg-loi.log"), "a",
                  encoding="utf-8") as f:
            f.write("\n--- %s ---\n%s\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), noi_dung))
    except Exception:
        pass


def kiem_chung_pe(path):
    """Kiem tra nhanh file vua tai co phai exe Windows that khong
    (header MZ + chu ky PE), de khong va phai trang loi HTML doi lot file.
    Tra ve True neu dung dinh dang PE."""
    try:
        with open(path, "rb") as f:
            dau = f.read(64)
        if len(dau) < 64 or dau[:2] != b"MZ":
            return False
        e_lfanew = int.from_bytes(dau[60:64], "little")
        with open(path, "rb") as f:
            f.seek(e_lfanew)
            return f.read(4) == b"PE\x00\x00"
    except Exception:
        return False


def goi_github_api(url):
    """GET JSON tu GitHub API (repo public nen khong can token).
    Dung mo_url_co_fallback_ssl nhu Chipchipdownload v6.3."""
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": UA_TRINH_DUYET})
    with mo_url_co_fallback_ssl(req, 60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tim_cookie_pyinstaller(f, kich_thuoc):
    """Tim vi tri bat dau cua cookie PyInstaller bang cach quet nguoc
    tu cuoi file theo tung khoi 8KB (giong cach PyInstaller tu doc).
    Tra ve offset hoac -1 neu khong thay. Cookie o cuoi file doi voi
    exe Windows; doi voi exe Linux thi con co section header ELF nam
    sau cookie nen khong duoc gia dinh cookie o dung 88 byte cuoi."""
    MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"
    CHUNK = 8192
    end_pos = kich_thuoc
    dau_sau = b""  # 7 byte dau cua khoi ke sau (de bat mau cat doi khoi)
    while end_pos > 0:
        start_pos = max(end_pos - CHUNK, 0)
        f.seek(start_pos)
        chunk = f.read(end_pos - start_pos)
        noi = chunk + dau_sau
        idx = noi.rfind(MAGIC)
        if idx >= 0:
            return start_pos + idx
        dau_sau = chunk[:len(MAGIC) - 1]
        end_pos = start_pos
    return -1


def kiem_chung_pyinstaller(path, ten_dll="python311.dll"):
    """Kiem tra file exe co phai PyInstaller onefile hop le khong: co
    cookie PyInstaller o cuoi file, bang TOC doc duoc, va co nhung
    ten_dll (vd python311.dll). Chi DOC header/TOC, khong chay thu
    file. Tra ve (True, '') hoac (False, ly_do).
    (v1.3: sua loi cap nhat v1.1 -> v1.2 tren may CYAN - exe moi tai ve
    bi thieu/hong nen chay len bao 'Failed to load Python DLL
    python311.dll'. Kiem tra MZ/PE thong thuong khong du vi file bi
    cat van co header hop le; phai doi chieu ca kich thuoc + TOC.)"""
    import struct
    MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"
    try:
        size = os.path.getsize(path)
        if size < 100:
            return False, "file quá nhỏ (%d byte)" % size
        with open(path, "rb") as f:
            cookie_pos = _tim_cookie_pyinstaller(f, size)
            if cookie_pos < 0:
                return False, ("không tìm thấy dấu hiệu PyInstaller "
                               "(file có thể bị cắt/xén)")
            f.seek(cookie_pos)
            cookie = f.read(88)
        if len(cookie) < 88 or cookie[:8] != MAGIC:
            return False, ("không tìm thấy dấu hiệu PyInstaller ở cuối "
                           "file (file có thể bị cắt/xén)")
        (_magic, lengthofPackage, toc_offset, toc_length,
         _pyver) = struct.unpack("!8sIIII", cookie[:24])
        # Goi bat dau = cuoi cookie - lengthofPackage (khong phai cuoi
        # file, vi exe Linux con co section header ELF sau cookie).
        goi_bat_dau = cookie_pos + 88 - lengthofPackage
        if goi_bat_dau < 0 or goi_bat_dau >= size:
            return False, ("gói PyInstaller nằm ngoài file "
                           "(lengthofPackage=%d)" % lengthofPackage)
        toc_pos = goi_bat_dau + toc_offset
        if toc_pos < 0 or toc_pos + toc_length > size:
            return False, "bảng TOC nằm ngoài file"
        with open(path, "rb") as f:
            f.seek(toc_pos)
            toc = f.read(toc_length)
        ten = set()
        i = 0
        while i + 4 <= len(toc):
            (entry_len,) = struct.unpack("!I", toc[i:i + 4])
            if entry_len <= 0 or i + entry_len > len(toc):
                break
            entry = toc[i:i + entry_len]
            if len(entry) >= 18:
                ten_raw = entry[18:]
                ten_file = ten_raw.split(b"\x00", 1)[0].decode(
                    "utf-8", "replace")
                ten.add(ten_file)
            i += entry_len
        if not ten:
            return False, "không đọc được bảng TOC"
        ten_thap = {t.lower() for t in ten}
        if ten_dll.lower() not in ten_thap:
            return False, ("không tìm thấy %s trong file (file có thể "
                           "thiếu)" % ten_dll)
        return True, ""
    except Exception as e:
        return False, "lỗi đọc file: %s" % e


def kiem_tra_file_cap_nhat(file_moi, kich_thuoc_mong_doi):
    """Kiem tra file exe moi tai ve truoc khi thay file cu (v1.3).
    Tra ve '' neu hop le, hoac chuoi ly do loi neu khong hop le.
    Kiem tra: ton tai, kich thuoc khop voi size tren Release (bat
    duoc truong hop tai chua xong), header PE, cookie PyInstaller +
    python311.dll nhung trong file."""
    if not os.path.isfile(file_moi):
        return "không tìm thấy file đã tải"
    thuc_te = os.path.getsize(file_moi)
    if kich_thuoc_mong_doi and thuc_te != kich_thuoc_mong_doi:
        return ("file tải về thiếu/không đủ: chỉ có %d/%d byte (tải chưa "
                "xong hoặc mạng ngắt)" % (thuc_te, kich_thuoc_mong_doi))
    if thuc_te < 1000000:
        return "file tải về quá nhỏ (%d byte), không hợp lệ" % thuc_te
    if not kiem_chung_pe(file_moi):
        return "file tải về không phải exe Windows hợp lệ"
    ok_pi, ly_do = kiem_chung_pyinstaller(file_moi)
    if not ok_pi:
        return "file tải về không phải exe PyInstaller hợp lệ (%s)" % ly_do
    return ""


def kiem_tra_cap_nhat():
    """Kiem tra ban moi tren GitHub. Tra ve dict:
    {version_moi, tag, tai_url, ten_file, kich_thuoc} hoac None neu da la
    ban moi nhat. Uu tien doc GitHub Releases (latest); neu API loi thi
    doc version.json raw tren main. Raise RuntimeError neu khong doc
    duoc. Repo public nen KHONG can token."""
    # 1) Thu Releases/latest.
    try:
        data = goi_github_api(GITHUB_API_LATEST_RELEASE)
        tag = (data.get("tag_name") or "").strip()
        if tag and so_sanh_version(tag, VERSION) > 0:
            tai_url = None
            ten_file = None
            kich_thuoc = None
            for asset in data.get("assets") or []:
                if (asset.get("name") or "") == EXE_TEN:
                    # Link tai truc tiep, khong can auth (repo public).
                    tai_url = asset.get("browser_download_url")
                    ten_file = asset.get("name")
                    kich_thuoc = asset.get("size")
                    break
            return {"version_moi": tag.lstrip("vV"), "tag": tag,
                    "tai_url": tai_url, "ten_file": ten_file,
                    "kich_thuoc": kich_thuoc}
        if tag:
            return None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise RuntimeError("GitHub API bao loi HTTP %d." % e.code)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError("Khong ket noi duoc GitHub: %s" % e)
    # 2) Chua co Release (404) hoac API loi: doc version.json raw tren main.
    try:
        req = urllib.request.Request(GITHUB_RAW_VERSION_JSON,
                                     headers={"User-Agent": UA_TRINH_DUYET})
        with mo_url_co_fallback_ssl(req, 60) as resp:
            noi_dung = json.loads(resp.read().decode("utf-8"))
        ver = (noi_dung.get("version") or "").strip()
        if ver and so_sanh_version(ver, VERSION) > 0:
            return {"version_moi": ver, "tag": "v" + ver,
                    "tai_url": None, "ten_file": None, "kich_thuoc": None}
        return None
    except Exception as e:
        raise RuntimeError("Khong doc duoc version tren GitHub: %s" % e)


def tai_ban_moi_va_cap_nhat(tai_url, kich_thuoc_mong_doi=None,
                            log_cb=None):
    """Tai exe ban moi ve file tam <exe>.new, KIEM CHUNG file truoc khi
    thay (v1.3): kich thuoc khop voi size tren Release, header PE,
    cookie PyInstaller + python311.dll nhung trong file. File loi thi
    BAO LOI ro rang, XOA file loi, KHONG thay file cu (tool cu van chay
    duoc). Dat thi ghi script cap nhat (capnhat.bat) roi tra ve
    (duong_dan_script, duong_dan_backup_exe_cu). Script cho tool thoat
    roi moi thay exe (co sao luu exe cu thanh .bak de khoi phuc neu
    exe moi van loi). Nguoi goi phai thoat tool ngay sau khi chay
    script nay."""
    exe_hien_tai = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None
    if not exe_hien_tai:
        raise RuntimeError("Dang chay dang ma nguon (.py), khong tu va exe duoc. "
                           "Hay dung ban .exe da cai.")
    thu_muc = os.path.dirname(exe_hien_tai)
    ten_exe = os.path.basename(exe_hien_tai)
    file_moi = os.path.join(thu_muc, ten_exe + ".new")
    bak_path = os.path.join(thu_muc, ten_exe + ".bak")
    if log_cb:
        log_cb("Dang tai ban moi ve...")
    tai_file_qua_url(tai_url, file_moi, 600, log_cb, "ban moi",
                     headers={"Accept": "application/octet-stream"})
    loi = kiem_tra_file_cap_nhat(file_moi, kich_thuoc_mong_doi)
    if loi:
        _xoa_file_quiet(file_moi)
        raise RuntimeError("%s. Đã xóa file lỗi, tool cũ vẫn chạy bình "
                           "thường." % loi)
    if log_cb:
        log_cb("Đã kiểm chứng file mới: %d byte, exe PyInstaller hợp lệ "
               "(có python311.dll)."
               % os.path.getsize(file_moi))
    kich_thuoc = os.path.getsize(file_moi)
    bat_path = os.path.join(thu_muc, "capnhat.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\r\n")
        f.write("chcp 65001 >nul\r\n")
        f.write('set "EXE=%s"\r\n' % exe_hien_tai)
        f.write('set "NEW=%s"\r\n' % file_moi)
        f.write('set "BAK=%s"\r\n' % bak_path)
        f.write('set "KICHTHUOC=%d"\r\n' % kich_thuoc)
        f.write("set /a DEM=0\r\n")
        # Cho file .new tai xong that: ton tai, dung kich thuoc, on dinh
        # qua 2 lan kiem tra cach nhau 1 giay (tranh thay file khi van
        # dang tai do).
        f.write(":doi_tai\r\n")
        f.write('if exist "%NEW%" goto kiem_tra_kich_thuoc\r\n')
        f.write("set /a DEM+=1\r\n")
        f.write("if %DEM% GEQ 30 goto loi_tai\r\n")
        f.write("ping -n 2 127.0.0.1 >nul\r\n")
        f.write("goto doi_tai\r\n")
        f.write(":kiem_tra_kich_thuoc\r\n")
        f.write('for %%I in ("%NEW%") do set SZ=%%~zI\r\n')
        f.write('if "%SZ%"=="%KICHTHUOC%" goto kiem_tra_on_dinh\r\n')
        f.write("set /a DEM+=1\r\n")
        f.write("if %DEM% GEQ 30 goto loi_tai\r\n")
        f.write("ping -n 2 127.0.0.1 >nul\r\n")
        f.write("goto doi_tai\r\n")
        f.write(":kiem_tra_on_dinh\r\n")
        f.write("ping -n 2 127.0.0.1 >nul\r\n")
        f.write('for %%I in ("%NEW%") do set SZ2=%%~zI\r\n')
        f.write('if "%SZ2%"=="%KICHTHUOC%" goto sao_luu\r\n')
        f.write("goto doi_tai\r\n")
        # Sao luu exe cu truoc khi thay (de khoi phuc neu exe moi loi).
        f.write(":sao_luu\r\n")
        f.write('copy /y "%EXE%" "%BAK%" >nul 2>&1\r\n')
        # Cho exe cu thoat han roi thay file.
        f.write(":doi_thoat\r\n")
        f.write("ping -n 2 127.0.0.1 >nul\r\n")
        f.write('move /y "%NEW%" "%EXE%" >nul 2>&1\r\n')
        f.write("if errorlevel 1 goto doi_thoat\r\n")
        f.write('start "" "%EXE%"\r\n')
        f.write('del "%%~f0"\r\n')
        f.write("goto het\r\n")
        f.write(":loi_tai\r\n")
        f.write('echo Khong thay file cap nhat hop le, giu nguyen ban cu. '
                '> "%~dp0capnhat-loi.txt"\r\n')
        f.write('del "%%~f0"\r\n')
        f.write(":het\r\n")
    return bat_path, bak_path


def _dinh_dang_toc_do(he_so):
    """Hien thi toc do dang he so nhan (giong trang web test): '1.00x',
    '1.35x', '0.50x'."""
    return "%.2fx" % float(he_so)


def _toc_do_sang_phan_tram(he_so):
    """Doi he so nhan (1.35x) sang phan tram cho edge-tts/SAPI (+35)."""
    return int(round((float(he_so) - 1.0) * 100))


def _toc_do_sang_edge(he_so):
    """Doi he so nhan sang chuoi rate edge-tts nhan ('+35%').
    Edge-tts nhan rate dang '+35%' cho toc do 1.35x."""
    return "%+d%%" % _toc_do_sang_phan_tram(he_so)


def _chuyen_toc_do_cu(gia_tri):
    """Chuyen toc do tu config cu (v1.0-1.2 luu dang phan tram so nguyen,
    vd 9 = +9%) sang he so nhan v1.3 (1.09x). Config moi da luu so thuc
    (vd 1.35) thi giu nguyen."""
    if isinstance(gia_tri, bool):
        return 1.0
    if isinstance(gia_tri, int):
        # So nguyen -50..50: phan tram cu -> he so nhan.
        if -50 <= gia_tri <= 50:
            return round(1.0 + gia_tri / 100.0, 2)
        return 1.0
    try:
        he_so = float(gia_tri)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(2.0, he_so))


def _dinh_dang_cao_do(hz):
    return ("+" if hz >= 0 else "") + str(int(hz)) + "Hz"


def _tao_connector(bo_xac_minh):
    if not bo_xac_minh:
        return None
    import aiohttp
    ctx = ssl._create_unverified_context()
    return aiohttp.TCPConnector(ssl=ctx)


# ---------------- may chu giong du phong (v1.2) ----------------
# Nguyen nhan loi "No audio was received" tren may that (11/2026,
# edge-tts issue #490): Microsoft siet endpoint goc
# speech.platform.bing.com - nhieu may bi tu choi 403 hoac bi ngat
# khong tra audio du token Sec-MS-GEC v2 da dung (edge-tts 7.3.1).
# Cach sua da duoc FluentVoice Pro 1.6.3 chung minh (10/2026): doi
# sang may chu moi cua Microsoft api.msedgeservices.com (cung giong,
# cung token TRUSTED_CLIENT_TOKEN), giu nguyen suot phien.
EDGE_ALT_WSS_URL = ("wss://api.msedgeservices.com/tts/cognitiveservices/"
                    "websocket/v1?Ocp-Apim-Subscription-Key={token}")
_dung_may_chu_phu = False  # da chuyen sang may chu phu trong phien nay
_khoa_may_chu = threading.Lock()


def _lay_proxy_he_thong():
    """Proxy he thong neu co (bien moi truong https_proxy/HTTPS_PROXY).
    May nha thuong khong co proxy -> tra None (khong doi hanh vi)."""
    return (os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
            or os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY"))


def _ten_may_chu(url):
    try:
        return url.split("/")[2]
    except Exception:
        return url


def _chuyen_sang_may_chu_phu(log_cb=None):
    """Doi edge-tts sang may chu phu api.msedgeservices.com cho den het
    phien (giong FluentVoice Pro 1.6.3). Tra ve True neu vua chuyen,
    False neu da o may chu phu roi."""
    global _dung_may_chu_phu
    import edge_tts.communicate as comm
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN
    with _khoa_may_chu:
        if _dung_may_chu_phu:
            return False
        comm.WSS_URL = EDGE_ALT_WSS_URL.format(token=TRUSTED_CLIENT_TOKEN)
        _dung_may_chu_phu = True
    if log_cb:
        log_cb("  -> May chu giong goc tu choi ket noi, chuyen sang may chu "
               "phu api.msedgeservices.com...")
    return True


def _mo_ta_loi_giong(e):
    """Phan loai loi doc giong de log ro rang.
    Tra ve (ma, giai_thich). Ma: '403' | '429' | 'khong-co-audio' |
    'ssl' | 'mang' | 'khac'."""
    ten = type(e).__name__
    s = str(e)
    status = getattr(e, "status", None)
    if status == 403 or " 403" in s or s.startswith("403"):
        return ("403", "Microsoft tu choi ket noi (HTTP 403) - may chu "
                       "giong goc siet ket noi tu tool ngoai trinh duyet")
    if status == 429 or " 429" in s or s.startswith("429"):
        return ("429", "bi gioi han toc do (HTTP 429) - Microsoft chan tam, "
                       "doi vai giay roi thu lai")
    if ten == "NoAudioReceived" or "No audio was received" in s:
        return ("khong-co-audio", "may chu chap nhan ket noi nhung ngat "
                                   "khong tra audio (Microsoft tu choi ngam)")
    if la_loi_chung_chi_ssl(e):
        return ("ssl", "loi chung chi SSL - proxy/phan mem diet virus chan "
                       "chung chi")
    if "timeout" in s.lower() or "timed out" in s.lower():
        return ("mang", "het thoi gian cho - mang cham hoac may chu tre")
    return ("khac", "%s: %s" % (ten, s))


async def _doc_mot_doan(text, voice, toc_do, cao_do, duong_dan_ra,
                        bo_xac_minh, proxy=None):
    import edge_tts
    import edge_tts.communicate as _comm
    # edge-tts truyen thang ssl=_SSL_CTX (certifi) vao ws_connect, ghi de
    # context cua connector -> muon bo xac minh that thi phai doi ca
    # _SSL_CTX cua edge-tts (neu khong, fallback bo xac minh o v1.1 chi
    # la hinh thuc, WSS van xac minh nhu thuong).
    try:
        if bo_xac_minh:
            _comm._SSL_CTX = ssl._create_unverified_context()
        else:
            import certifi
            _comm._SSL_CTX = ssl.create_default_context(
                cafile=certifi.where())
    except Exception:
        pass
    comm = edge_tts.Communicate(
        text, voice,
        # v1.3: toc_do la he so nhan tren giao dien (1.35x) - doi sang
        # dang '+35%' truoc khi dua cho edge-tts.
        rate=_toc_do_sang_edge(toc_do),
        pitch=_dinh_dang_cao_do(cao_do),
        connector=_tao_connector(bo_xac_minh),
        proxy=proxy,
    )
    await comm.save(duong_dan_ra)


def _doc_mot_doan_co_failover(text, voice, toc_do, cao_do, duong_dan_ra,
                              log_cb=None):
    """Doc 1 doan ngan thanh file MP3, co failover may chu giong.
    Thu tu: may chu goc (SSL xac minh -> bo xac minh) roi may chu phu
    api.msedgeservices.com (SSL xac minh -> bo xac minh). Gap 429 thi
    doi 3 giay truoc khi thu lai. Tra ve (thanh_cong, da_dung_bo_xac_minh,
    thong_bao_loi)."""
    import time
    proxy = _lay_proxy_he_thong()
    if proxy and log_cb:
        log_cb("  (phat hien proxy he thong, dung proxy de goi giong)")
    if _dung_may_chu_phu:
        cac_luot = [("phu", False), ("phu", True)]
    else:
        cac_luot = [("goc", False), ("goc", True),
                    ("phu", False), ("phu", True)]
    loi_cuoi = ""
    for i, (may_chu, bo_xac_minh) in enumerate(cac_luot, 1):
        if may_chu == "phu":
            _chuyen_sang_may_chu_phu(log_cb)
            if i == 3:
                time.sleep(2)  # tranh 429 khi vua doi may chu
        ten_may = ("may chu goc" if may_chu == "goc"
                   else "may chu phu")
        try:
            asyncio.run(_doc_mot_doan(text, voice, toc_do, cao_do,
                                      duong_dan_ra, bo_xac_minh, proxy))
            if os.path.isfile(duong_dan_ra) and os.path.getsize(duong_dan_ra) > 0:
                if log_cb and may_chu == "phu":
                    log_cb("  OK qua may chu phu api.msedgeservices.com")
                return True, bo_xac_minh, ""
            raise RuntimeError("file am thanh rong (0 byte)")
        except Exception as e:
            ma, giai_thich = _mo_ta_loi_giong(e)
            loi_cuoi = "%s [%s]" % (giai_thich, ma)
            if log_cb:
                log_cb("  Thu lan %d/%d (%s, %s) loi [%s]: %s"
                       % (i, len(cac_luot), ten_may,
                          "bo xac minh SSL" if bo_xac_minh else "SSL xac minh",
                          ma, giai_thich))
            if ma == "429":
                time.sleep(3)
            continue
    return False, False, loi_cuoi


def doc_thanh_mp3(text, voice, toc_do, cao_do, duong_dan_ra, log_cb=None):
    """Doc 1 cau thanh file MP3 (co failover may chu giong, xem
    _doc_mot_doan_co_failover). toc_do la HE SO NHAN (v1.3: 1.0x mac
    dinh, 0.5x-2.0x) - doi sang dang '+35%' trong _doc_mot_doan truoc
    khi dua cho edge-tts. Tra ve (thanh_cong, da_dung_bo_xac_minh,
    thong_bao_loi). v1.3: doc loi thi XOA file dich (neu co) de khong de
    lai file MP3 hong (0 byte / doan giua chung) lam hong buoc gop sau."""
    doan_list = tach_cau_dai(text)
    if len(doan_list) == 1:
        ok, bo_xac_minh, loi = _doc_mot_doan_co_failover(
            text, voice, toc_do, cao_do, duong_dan_ra, log_cb)
        if not ok:
            _xoa_file_quiet(duong_dan_ra)
        return ok, bo_xac_minh, loi
    # Cau dai: doc tung doan roi noi lai bang pydub
    import tempfile
    from pydub import AudioSegment
    am_thanh = AudioSegment.empty()
    for j, doan in enumerate(doan_list):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tam_path = tmp.name
        ok, _, loi = doc_thanh_mp3(doan, voice, toc_do, cao_do, tam_path, log_cb)
        try:
            if ok:
                am_thanh += AudioSegment.from_file(tam_path, format="mp3")
            else:
                _xoa_file_quiet(duong_dan_ra)
                return False, False, "doan %d loi: %s" % (j + 1, loi)
        finally:
            try:
                os.remove(tam_path)
            except OSError:
                pass
    am_thanh.export(duong_dan_ra, format="mp3")
    return True, False, ""


# ---------------- giong may (SAPI tren Windows, v1.3) ----------------
# Giong tieng Viet co san tren may Windows (vd Microsoft An) qua
# PowerShell + System.Speech (co san trong .NET Framework, khong can
# cai them thu vien Python nao). Dung de so sanh chat giong voi HoaiMy
# online truoc khi quyet dinh dung giong nao de xuat.
# - Nghe thu: doc thang ra loa (khong can file, khong can ffmpeg).
# - Xuat MP3: ghi ra WAV tam roi chuyen sang MP3 bang ffmpeg.

def _ps_quote(s):
    """Nhung chuoi vao chuoi don PowerShell (nhan doi dau ')."""
    return "'" + str(s).replace("'", "''") + "'"


def _ps_giong_may(text, toc_do, cao_do, wav_path, dung_ssml):
    """Tao script PowerShell doc 1 doan bang SAPI (System.Speech).
    wav_path=None -> phat ra loa; khac None -> ghi ra file WAV.
    Giong: uu tien giong tieng Viet (vi-*) nu, neu khong co thi lay
    giong mac dinh cua may. Toc do qua thuoc tinh Rate (-10..10);
    cao do chi chinh duoc qua SSML prosody (neu dung_ssml)."""
    from xml.sax.saxutils import escape as xml_escape
    # v1.3: toc_do la he so nhan (1.35x) - doi sang phan tram (+35) roi
    # moi doi sang thang Rate -10..10 cua SAPI.
    phan_tram = _toc_do_sang_phan_tram(toc_do)
    rate_plain = max(-10, min(10, int(round(phan_tram / 5.0))))
    ssml = ""
    if dung_ssml:
        rate_str = "medium" if phan_tram == 0 else ("%+d%%" % phan_tram)
        pitch_str = "default" if cao_do == 0 else ("%+dHz" % cao_do)
        ssml = ('<speak version="1.0" '
                'xmlns="http://www.w3.org/2001/10/synthesis" '
                'xml:lang="vi-VN"><prosody rate="%s" pitch="%s">%s'
                '</prosody></speak>'
                % (rate_str, pitch_str, xml_escape(text)))
    wav_ps = "$null" if wav_path is None else _ps_quote(wav_path)
    dung = "$true" if dung_ssml else "$false"
    return "\n".join([
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
        "$ErrorActionPreference = 'Stop'",
        "Add-Type -AssemblyName System.Speech",
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$tatCa = $synth.GetInstalledVoices() | Where-Object { $_.Enabled }",
        "$vi = @($tatCa | Where-Object { "
        "$_.VoiceInfo.Culture.Name -like 'vi*' })",
        "if ($vi.Count -eq 0) { $vi = @($tatCa) }",
        "if ($vi.Count -eq 0) { Write-Error 'NO_VOICE'; exit 1 }",
        "$chon = $vi | Where-Object { $_.VoiceInfo.Gender -eq 'Female' } "
        "| Select-Object -First 1",
        "if (-not $chon) { $chon = $vi | Select-Object -First 1 }",
        "$synth.SelectVoice($chon.VoiceInfo.Name)",
        "Write-Output ('VOICE:' + $chon.VoiceInfo.Name)",
        "$wav = %s" % wav_ps,
        "if ($wav) { $synth.SetOutputToWaveFile($wav) }",
        "$daDoc = $false",
        "if (%s) {" % dung,
        "    try {",
        "        $synth.SpeakSsml(%s)" % _ps_quote(ssml),
        "        $daDoc = $true",
        "        Write-Output 'MODE:SSML'",
        "    } catch {",
        "        Write-Output ('SSML_FAIL:' + $_.Exception.Message)",
        "        if ($wav) {",
        "            $synth.SetOutputToDefaultAudioDevice()",
        "            Remove-Item -LiteralPath $wav -ErrorAction "
        "SilentlyContinue",
        "            $synth.SetOutputToWaveFile($wav)",
        "        }",
        "    }",
        "}",
        "if (-not $daDoc) {",
        "    $synth.Rate = %d" % rate_plain,
        "    $synth.Speak(%s)" % _ps_quote(text),
        "    Write-Output 'MODE:PLAIN'",
        "}",
        "$synth.Dispose()",
    ])


def _chay_giong_may(text, toc_do, cao_do, wav_path, log_cb=None, dung=None):
    """Chay PowerShell System.Speech doc 1 doan.
    wav_path=None -> phat ra loa; wav_path=... -> ghi ra file WAV.
    `dung` (threading.Event, tuy chon): khi duoc dat thi tat tien trinh
    PowerShell ngay (nut 'Dung' khi nghe thu). Tra ve (thanh_cong,
    ten_giong, loi)."""
    if not sys.platform.startswith("win"):
        return False, "", "giọng máy chỉ dùng được trên Windows"
    import tempfile
    dung_ssml = (cao_do != 0)
    ps = _ps_giong_may(text, toc_do, cao_do, wav_path, dung_ssml)
    fd, ps_path = tempfile.mkstemp(suffix=".ps1")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
            f.write(ps)
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", ps_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace")
        except Exception as e:
            return False, "", "không chạy được PowerShell: %s" % e
        # Cho tien trinh xong, vua cho vua kiem tra nut Dung / het gio.
        bat_dau = time.monotonic()
        while proc.poll() is None:
            if dung is not None and dung.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                proc.wait()
                return False, "", "đã dừng nghe thử"
            if time.monotonic() - bat_dau > 180:
                try:
                    proc.kill()
                except Exception:
                    pass
                proc.wait()
                return False, "", "hết thời gian chờ giọng máy (180s)"
            time.sleep(0.1)
        out, err = proc.communicate()
        out = (out or "") + "\n" + (err or "")
        ten_giong = ""
        for dong in out.splitlines():
            if dong.strip().startswith("VOICE:"):
                ten_giong = dong.strip()[len("VOICE:"):].strip()
        if "NO_VOICE" in out or proc.returncode != 0:
            return False, ten_giong, _tom_tat_loi(
                out.strip() or "PowerShell báo lỗi (mã %d)" % proc.returncode)
        if dung_ssml and "MODE:PLAIN" in out and log_cb:
            log_cb("  (giọng máy không nhận cao độ, đã đọc bằng giọng "
                   "thường)")
        return True, ten_giong, ""
    finally:
        _xoa_file_quiet(ps_path)


def nghe_giong_may(text, toc_do, cao_do, log_cb=None, dung=None):
    """Doc 1 doan bang giong may ra loa (khong tao file). Tra ve
    (thanh_cong, loi)."""
    ok, ten_giong, loi = _chay_giong_may(text, toc_do, cao_do, None, log_cb,
                                         dung)
    if ok and log_cb and ten_giong:
        log_cb("  Giọng máy đang dùng: %s" % ten_giong)
    return ok, loi


def _doc_giong_may_1_doan(text, toc_do, cao_do, duong_dan_ra, log_cb,
                          ffmpeg):
    """Doc 1 doan ngan bang giong may ra file WAV tam, chuyen sang MP3."""
    import tempfile
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        ok, ten_giong, loi = _chay_giong_may(text, toc_do, cao_do,
                                             wav_path, log_cb)
        if not ok:
            return False, False, loi
        if log_cb and ten_giong:
            log_cb("  Giọng máy đang dùng: %s" % ten_giong)
        try:
            r = subprocess.run([ffmpeg, "-y", "-i", wav_path,
                                duong_dan_ra],
                               capture_output=True, timeout=120)
        except Exception as e:
            return False, False, "lỗi chạy ffmpeg: %s" % e
        if (r.returncode != 0 or not os.path.isfile(duong_dan_ra)
                or os.path.getsize(duong_dan_ra) == 0):
            return False, False, "ffmpeg không chuyển được WAV sang MP3"
        return True, False, ""
    finally:
        _xoa_file_quiet(wav_path)


def doc_giong_may(text, toc_do, cao_do, duong_dan_ra, log_cb=None,
                  ffmpeg=None):
    """Doc 1 cau bang giong may tren Windows thanh file MP3.
    Tra ve (thanh_cong, False, thong_bao_loi). Can ffmpeg de chuyen
    WAV sang MP3."""
    if not sys.platform.startswith("win"):
        return False, False, "giọng máy chỉ dùng được trên Windows"
    if not ffmpeg:
        return False, False, ("cần ffmpeg để xuất MP3 bằng giọng máy "
                              "(đặt ffmpeg.exe cạnh tool hoặc thêm vào "
                              "PATH)")
    doan_list = tach_cau_dai(text)
    if len(doan_list) == 1:
        return _doc_giong_may_1_doan(text, toc_do, cao_do, duong_dan_ra,
                                     log_cb, ffmpeg)
    from pydub import AudioSegment
    am_thanh = AudioSegment.empty()
    for j, doan in enumerate(doan_list):
        with tempfile.NamedTemporaryFile(suffix=".mp3",
                                         delete=False) as tmp:
            tam_path = tmp.name
        ok, _, loi = _doc_giong_may_1_doan(doan, toc_do, cao_do, tam_path,
                                           log_cb, ffmpeg)
        try:
            if ok:
                am_thanh += AudioSegment.from_file(tam_path, format="mp3")
            else:
                _xoa_file_quiet(duong_dan_ra)
                return False, False, "doan %d loi: %s" % (j + 1, loi)
        finally:
            _xoa_file_quiet(tam_path)
    am_thanh.export(duong_dan_ra, format="mp3")
    return True, False, ""


def doc_cau_thanh_mp3(text, voice, toc_do, cao_do, duong_dan_ra,
                      log_cb=None, ffmpeg=None):
    """Doc 1 cau thanh file MP3, chon duong giong theo `voice`:
    'may' -> giong SAPI tren may Windows (PowerShell System.Speech);
    con lai -> Edge TTS online (HoaiMy/NamMinh).
    Tra ve (thanh_cong, da_dung_bo_xac_minh, thong_bao_loi)."""
    if voice == "may":
        return doc_giong_may(text, toc_do, cao_do, duong_dan_ra, log_cb,
                             ffmpeg)
    return doc_thanh_mp3(text, voice, toc_do, cao_do, duong_dan_ra, log_cb)


# ---------------- toc do tu dong theo tung cau (v1.4, theo iContent) ----------------
# Trong file SRT co cau dai can doc nhanh moi kip slot, co cau ngan doc
# dung nhip la du. iContent lam toc do RIENG tung cau (cau 2 = 1.60x, cau
# 4 = 1.00x...) va co muc "Doc nhanh hon toi da 1.35x" - cau nao can
# nhanh hon muc do thi AI rut gon (o day tool chi tang toc toi da den
# muc do toi da roi ghi canh bao tran slot, khong tu rut gon van ban).
# Cach lam: tao audio o toc do co ban, DO thoi luong that cua file, neu
# can nhanh hon thi dung ffmpeg atempo tang toc file da tao (khong goi
# lai API TTS). Vi vay toc do thuc cua cau chi biet sau khi da doc xong
# cau do - khong uoc luong truoc bang van ban (chi dung uoc luong khi
# khong do duoc file that).
TOC_DO_DOC_TRUNG_BINH_KY_TU_GIAY = 13.5  # toc do doc trung binh tieng
# Viet o 1.00x (ky tu/giay), chi dung de UOC LUONG khi khong do duoc
# thoi luong file that (vd: thieu ffmpeg).
DUNG_SAI_TRAN_SLOT_MS = 100  # dung sai khi so thoi luong audio voi
# slot SRT (ms). File MP3 sau khi ma hoa lai (atempo) thuong dai them
# ~50ms do padding cua bo ma hoa - tran duoi 100ms la khong dang ke
# (nghe khong ra, cau sau bat dau dung moc van de len), khong dem la
# tran slot de khoi bao canh bao nhieu vo ich.


def _uoc_luong_thoi_luong_ms(text, toc_do=1.0):
    """Uoc luong thoi luong doc (ms) tu do dai van ban, khi khong do
    duoc file audio that. Chi la uoc luong - duong chinh van la do
    thoi luong that cua file sau khi tao."""
    ky_tu = len((text or "").strip())
    if ky_tu == 0:
        return 0
    return int(ky_tu / TOC_DO_DOC_TRUNG_BINH_KY_TU_GIAY * 1000
               / max(0.5, float(toc_do)))


def _do_dai_mp3_ms(duong_dan, ffmpeg):
    """Do thoi luong file MP3 (ms). Uu tien ffprobe (nhanh, chinh xac);
    neu khong co thi dung pydub. Tra ve None neu khong do duoc
    (vd: thieu ffmpeg, file loi)."""
    if not os.path.isfile(duong_dan):
        return None
    try:
        if os.path.getsize(duong_dan) == 0:
            return None
    except OSError:
        return None
    ffprobe = tim_ffprobe(ffmpeg) if ffmpeg else None
    if ffprobe:
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "format=duration", "-of",
                 "default=noprint_wrappers=1:nokey=1", duong_dan],
                capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return int(float(r.stdout.strip()) * 1000)
        except Exception:
            pass
    try:
        from pydub import AudioSegment
        return len(AudioSegment.from_file(duong_dan, format="mp3"))
    except Exception:
        return None


def _tinh_toc_do_can(slot_ms, do_dai_ms, toc_do_co_ban, toc_do_toi_da):
    """Tinh toc do thuc te can dung cho 1 cau (he so nhan so voi 1.00x).
    - slot_ms: do dai slot SRT cua cau (ket_thuc - bat_dau).
    - do_dai_ms: thoi luong audio da tao o toc_do_co_ban (None neu
      khong do duoc).
    Tra ve (toc_do_thuc_te, he_so_atempo, vuot_toc_do_toi_da):
    - Doc vua slot thi toc_do_thuc = toc_do_co_ban, he_so = 1.0.
    - Can nhanh hon: he_so = do_dai/slot; toc_do_thuc =
      toc_do_co_ban * he_so, nhung KHONG vuot toc_do_toi_da (toc do toi
      da hieu dung it nhat bang toc do co ban - khong the cham lai duoi
      toc do da doc).
    - vuot_toc_do_toi_da=True khi can nhanh hon ca toc do toi da (cau
      do se tran slot du da o toc do toi da)."""
    try:
        co_ban = float(toc_do_co_ban)
    except (TypeError, ValueError):
        co_ban = 1.0
    try:
        toi_da = float(toc_do_toi_da)
    except (TypeError, ValueError):
        toi_da = 1.35
    toi_da = max(toi_da, co_ban)  # khong cham lai duoi toc do co ban
    if not slot_ms or slot_ms <= 0 or not do_dai_ms or do_dai_ms <= 0:
        return co_ban, 1.0, False
    if do_dai_ms <= slot_ms:
        return co_ban, 1.0, False
    he_so = do_dai_ms / float(slot_ms)
    toc_do_thuc = co_ban * he_so
    if toc_do_thuc > toi_da:
        return toi_da, toi_da / co_ban, True
    return toc_do_thuc, he_so, False


def _chuoi_atempo(he_so):
    """Tach he so tang toc thanh chuoi filter atempo cua ffmpeg (moi
    atempo chi nhan 0.5-2.0). vd: 1.6 -> 'atempo=1.6000';
    3.2 -> 'atempo=2.0000,atempo=1.6000'."""
    chuoi = []
    con = float(he_so)
    while con > 2.0:
        chuoi.append("atempo=2.0000")
        con /= 2.0
    chuoi.append("atempo=%.4f" % con)
    return ",".join(chuoi)


def _tang_toc_mp3(duong_dan, he_so, ffmpeg):
    """Tang toc file MP3 tai cho bang ffmpeg atempo (ghi qua file tam
    roi chep de len file goc). Tra ve True neu xong, False neu loi
    (khong co ffmpeg, he_so khong hop le, ffmpeg bao loi)."""
    if not ffmpeg or not he_so or he_so <= 1.0:
        return False
    import tempfile
    fd, tam = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        r = subprocess.run([ffmpeg, "-y", "-i", duong_dan, "-vn",
                            "-af", _chuoi_atempo(he_so),
                            "-b:a", "128k", tam],
                           capture_output=True, timeout=120)
        if (r.returncode != 0 or not os.path.isfile(tam)
                or os.path.getsize(tam) == 0):
            return False
        shutil.copyfile(tam, duong_dan)
        return True
    except Exception:
        return False
    finally:
        _xoa_file_quiet(tam)


def _ap_dung_toc_do_tu_dong(duong_dan, cau, toc_do_co_ban, toc_do_toi_da,
                            tu_dong, ffmpeg, log_cb=None):
    """Ap dung toc do tu dong theo slot SRT cho 1 cau vua doc xong.
    Tra ve toc_do_thuc_te (he so nhan) cua cau do.
    - Tat tu_dong: tra ve toc_do_co_ban, khong lam gi (hanh vi cu v1.3).
    - Do thoi luong that cua file (ffprobe/pydub); khong do duoc thi
      uoc luong tu do dai van ban.
    - Can nhanh hon thi dung ffmpeg atempo tang toc file tai cho.
    - Khong kip du o toc do toi da (hoac khong tang toc duoc) thi ghi
      log canh bao 'Câu X đọc hết Ys nhưng slot chỉ có Zs (tràn sang
      câu sau)'."""
    try:
        co_ban = float(toc_do_co_ban)
    except (TypeError, ValueError):
        co_ban = 1.0
    if not tu_dong:
        return co_ban
    slot_ms = cau["ket_thuc_ms"] - cau["bat_dau_ms"]
    if slot_ms <= 0:
        return co_ban
    do_dai = _do_dai_mp3_ms(duong_dan, ffmpeg)
    if do_dai is None:
        do_dai = _uoc_luong_thoi_luong_ms(cau["text"], co_ban)
        if log_cb and do_dai > 0:
            log_cb("  (câu %d: không đo được thời lượng file, ước lượng "
                   "%.1fs từ độ dài văn bản)" % (cau["chi_so"],
                                                do_dai / 1000.0))
    if do_dai <= 0:
        return co_ban
    toc_do_thuc, he_so, vuot_max = _tinh_toc_do_can(
        slot_ms, do_dai, co_ban, toc_do_toi_da)
    if he_so > 1.005:
        if ffmpeg and _tang_toc_mp3(duong_dan, he_so, ffmpeg):
            if log_cb:
                log_cb("  Câu %d: đọc %.1fs, slot %.1fs -> tăng tốc lên "
                       "%.2fx" % (cau["chi_so"], do_dai / 1000.0,
                                  slot_ms / 1000.0, toc_do_thuc))
        else:
            if log_cb:
                log_cb("  Câu %d: cần %.2fx mới kịp slot nhưng không tăng "
                       "tốc được (thiếu ffmpeg) - giữ tốc độ %.2fx"
                       % (cau["chi_so"], toc_do_thuc, co_ban))
            toc_do_thuc = co_ban
            he_so = 1.0
    # Kiem tra tran slot sau khi tang toc (do lai thoi luong that neu
    # vua tang toc; neu khong thi dung so da do/uoc luong).
    do_dai_cuoi = do_dai
    if he_so > 1.005:
        do_dai_moi = _do_dai_mp3_ms(duong_dan, ffmpeg)
        do_dai_cuoi = (do_dai_moi if do_dai_moi is not None
                       else int(do_dai / he_so))
    if do_dai_cuoi > slot_ms + DUNG_SAI_TRAN_SLOT_MS:
        if log_cb:
            log_cb("  Cảnh báo: Câu %d đọc hết %.1fs nhưng slot chỉ có "
                   "%.1fs (tràn sang câu sau)"
                   % (cau["chi_so"], do_dai_cuoi / 1000.0,
                      slot_ms / 1000.0))
    return toc_do_thuc


def _phat_mp3(path, dung=None):
    """Phat 1 file MP3 ra loa NGAY trong tool (dung cho nut 'Nghe thu
    giong'). Windows: dung winmm (MCI) co san - phat khong cho roi
    tu cho xong, KHONG mo trinh phat ngoai, KHONG luu file. `dung`
    (threading.Event, tuy chon): khi duoc dat thi dung phat ngay (nut
    'Dung' khi nghe thu). Tra ve (thanh_cong, loi)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW("close tts_nghe", None, 0, 0)
            r = winmm.mciSendStringW(
                'open "%s" alias tts_nghe' % path, None, 0, 0)
            if r != 0:
                return False, "không mở được file âm thanh để phát (mã %d)" % r
            r = winmm.mciSendStringW("play tts_nghe", None, 0, 0)
            if r != 0:
                winmm.mciSendStringW("close tts_nghe", None, 0, 0)
                return False, "không phát được audio (mã %d)" % r
            # Cho phat xong hoac bi dung (poll trang thai MCI).
            buf = ctypes.create_unicode_buffer(64)
            bat_dau = time.monotonic()
            da_phat = False
            while True:
                if dung is not None and dung.is_set():
                    winmm.mciSendStringW("stop tts_nghe", None, 0, 0)
                    winmm.mciSendStringW("close tts_nghe", None, 0, 0)
                    return False, "đã dừng nghe thử"
                winmm.mciSendStringW("status tts_nghe mode", buf, 64, 0)
                che_do = buf.value.strip().lower()
                if che_do == "playing":
                    da_phat = True
                elif da_phat:
                    break
                elif time.monotonic() - bat_dau > 2:
                    # Khong thay phat (file rat ngan hoac loi) - thoat.
                    break
                time.sleep(0.1)
            winmm.mciSendStringW("close tts_nghe", None, 0, 0)
            return True, ""
        except Exception as e:
            return False, "không phát được audio: %s" % e
    # Khong phai Windows (chi dung khi test): thu ffplay neu co.
    try:
        proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit",
                                 "-loglevel", "error", path],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        while proc.poll() is None:
            if dung is not None and dung.is_set():
                proc.kill()
                proc.wait()
                return False, "đã dừng nghe thử"
            time.sleep(0.1)
        return True, ""
    except Exception as e:
        return False, "không phát được audio trên hệ này: %s" % e


# ---------------- gop file long tieng ----------------

class GopDan:
    """Gop dan (merge incremental) cho che do 'Gop 1 file long tieng'
    (v1.3): moi cau doc xong la ghep NGAY vao file WAV tam, dung moc
    thoi gian SRT cua no (ghi PCM truc tiep vao dung vi tri, cho chua
    toi thi de lang). Khong doi den cuoi moi gop 1 lan nhu truoc.
    Loi ich: huy giua chung hay loi giua chung thi file tam van giu
    cac cau da xong (khong mat trang); 1 cau loi khong lam hong ca
    file gop (chi de lang o slot cua no roi di tiep); mo file tam ra
    nghe thu duoc ngay ca khi chua chay xong. Xong thi chuyen WAV tam
    -> MP3 1 lan bang ffmpeg, roi xoa file tam.
    Vi sao phai doc tung cau rieng roi moi gop: API giong Microsoft
    (edge-tts) chi nhan 1 doan van moi lan goi - khong goi 1 lan cho
    ca 100 cau duoc - nen tool doc tung cau rieng roi ghep lai dung
    moc thoi gian SRT thanh 1 file long tieng duy nhat."""

    def __init__(self, duong_dan_wav, duong_dan_mp3, tong_ms=0, log_cb=None):
        self.wav = duong_dan_wav
        self.mp3 = duong_dan_mp3
        # tong_ms: moc ket thuc cua cau cuoi trong SRT - file gop phai
        # dai du den moc nay (du cau cuoi doc ngan hon slot cua no).
        self.tong_ms = tong_ms
        self.log_cb = log_cb
        self.frame_rate = None
        self.channels = None
        self.sample_width = 2
        self.block_align = None
        self.so_cau = 0       # so cau da ghep vao file tam
        self.bo_qua = 0       # so cau loi da bo qua (khong co audio)
        self.tran_slot = 0    # so cau doc dai hon slot cua no
        self.da_tao = False   # file WAV tam da duoc tao (co cau dau tien)

    def _ghi_header_vao(self, f, data_size):
        """Ghi (lai) header WAV 44 byte voi data_size hien tai (f dang mo)."""
        import struct
        byte_rate = self.frame_rate * self.block_align
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE", b"fmt ", 16, 1,
            self.channels, self.frame_rate, byte_rate, self.block_align,
            self.sample_width * 8, b"data", data_size)
        f.seek(0)
        f.write(header)

    def _khoi_tao(self, am_thanh):
        """Tao file WAV tam tu audio cua cau dau tien (lay thong so
        frame_rate/channels/sample_width tu no). File duoc tao du dai
        tong_ms ngay tu dau (phan chua toi la lang) de mo ra nghe thu
        duoc ngay ca khi chua chay xong."""
        self.frame_rate = am_thanh.frame_rate
        self.channels = am_thanh.channels
        self.sample_width = am_thanh.sample_width
        self.block_align = self.channels * self.sample_width
        data_size = 0
        if self.tong_ms > 0:
            data_size = (self.tong_ms * self.frame_rate // 1000
                         * self.block_align)
        with open(self.wav, "wb") as f:
            f.write(b"\x00" * 44)
            if data_size > 0:
                # Mo rong file (sparse, khong ghi that) cho du tong_ms.
                f.truncate(44 + data_size)
                self._ghi_header_vao(f, data_size)
        self.da_tao = True

    def them_cau(self, cau, duong_dan_mp3_cau):
        """Ghep 1 cau vua doc xong vao file WAV tam, dung moc thoi gian
        SRT cua no. Cau nao khong co audio (thieu file, file rong, file
        loi khong giai ma duoc) thi BO QUA - cho cua no giu nguyen
        khoang lang - cac cau khac van ghep binh thuong. Tra ve True
        neu ghep duoc, False neu bo qua."""
        try:
            from pydub import AudioSegment
            am = AudioSegment.from_file(duong_dan_mp3_cau, format="mp3")
        except Exception:
            if self.log_cb:
                self.log_cb("  Đã bỏ qua câu %d (file audio lỗi, không đọc "
                            "được)" % cau["chi_so"])
            self.bo_qua += 1
            return False
        if len(am) == 0:
            if self.log_cb:
                self.log_cb("  Đã bỏ qua câu %d (file audio rỗng, không có "
                            "audio)" % cau["chi_so"])
            self.bo_qua += 1
            return False
        if not self.da_tao:
            self._khoi_tao(am)
        am = (am.set_frame_rate(self.frame_rate)
                .set_channels(self.channels)
                .set_sample_width(self.sample_width))
        dai = len(am)
        cho_trong = cau["ket_thuc_ms"] - cau["bat_dau_ms"]
        # v1.4: dung sai 100ms (padding MP3) - tran it hon thi khong
        # dem la tran slot.
        if dai > cho_trong + DUNG_SAI_TRAN_SLOT_MS:
            self.tran_slot += 1
            if self.log_cb:
                self.log_cb("  Canh bao: cau %d doc het %.1fs nhung slot "
                            "chi co %.1fs (phan tran se bi cat khi cau sau "
                            "bat dau)" % (cau["chi_so"], dai / 1000.0,
                                         cho_trong / 1000.0))
        vi_tri = 44 + (cau["bat_dau_ms"] * self.frame_rate // 1000) \
            * self.block_align
        du_lieu = am.raw_data
        with open(self.wav, "r+b") as f:
            f.seek(vi_tri)
            f.write(du_lieu)
            f.seek(0, 2)
            data_size = f.tell() - 44
            self._ghi_header_vao(f, data_size)
        self.so_cau += 1
        return True

    def do_dai_ms(self):
        """Do dai hien tai cua file WAV tam (ms)."""
        if not self.da_tao or not os.path.isfile(self.wav):
            return 0
        data_size = os.path.getsize(self.wav) - 44
        if data_size <= 0 or not self.frame_rate or not self.block_align:
            return 0
        return int(data_size * 1000 / (self.frame_rate * self.block_align))

    def hoan_tat(self, ffmpeg):
        """Chuyen WAV tam -> MP3 dich, xoa file WAV tam. Tra ve
        (thanh_cong, do_dai_ms)."""
        if not self.da_tao or self.so_cau == 0:
            return False, 0
        # Dam bao file dai du tong_ms (phong khi file bi ngan hon do
        # cau cuoi doc ngan hon slot cua no).
        if self.tong_ms > 0:
            can_bytes = (self.tong_ms * self.frame_rate // 1000
                         * self.block_align)
            if os.path.getsize(self.wav) - 44 < can_bytes:
                with open(self.wav, "r+b") as f:
                    f.truncate(44 + can_bytes)
                    self._ghi_header_vao(f, can_bytes)
        tong_ms = self.do_dai_ms()
        try:
            r = subprocess.run([ffmpeg, "-y", "-i", self.wav,
                                "-b:a", "128k", self.mp3],
                               capture_output=True, timeout=600)
        except Exception:
            return False, 0
        if (r.returncode != 0 or not os.path.isfile(self.mp3)
                or os.path.getsize(self.mp3) == 0):
            return False, 0
        _xoa_file_quiet(self.wav)
        return True, tong_ms


# ---------------- luu tien trinh de tiep tuc (v1.3) ----------------
# Khi xuat bi huy giua chung (hoac dung vi con cau loi), tien trinh duoc
# luu vao tien-trinh.json trong thu muc xuat: da xong den cau nao, file
# MP3 dang tao la file nao, che do dau ra, giong/toc do/cao do dang dung.
# Nut "Tiep tuc" doc tiep tu cau chua xong va noi vao file cu; xuat xong
# 100% thi xoa tien trinh (khong con gi de tiep tuc).
TEN_FILE_TIEN_TRINH = "tien-trinh.json"


def _luu_tien_trinh(thu_muc, du_lieu):
    """Ghi tien trinh xuat dang do vao thu_muc/tien-trinh.json."""
    try:
        os.makedirs(thu_muc, exist_ok=True)
        with open(os.path.join(thu_muc, TEN_FILE_TIEN_TRINH), "w",
                  encoding="utf-8") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _doc_tien_trinh(thu_muc):
    """Doc tien-trinh.json trong thu muc (tra ve dict hoac None)."""
    try:
        with open(os.path.join(thu_muc, TEN_FILE_TIEN_TRINH), "r",
                  encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _xoa_tien_trinh(thu_muc):
    """Xoa file tien trinh (khi xuat xong 100%)."""
    _xoa_file_quiet(os.path.join(thu_muc, TEN_FILE_TIEN_TRINH))


def _thu_muc_co_ket_qua(thu_muc):
    """Thu muc da co ket qua xuat nao chua (file MP3 gop, file cau rieng,
    hay file tien trinh)? Dung de biet co can tao thu muc moi khi
    'Sub lai tu dau' hay khong."""
    if not os.path.isdir(thu_muc):
        return False
    if os.path.isfile(os.path.join(thu_muc, TEN_FILE_TIEN_TRINH)):
        return True
    try:
        for ten in os.listdir(thu_muc):
            if ten.lower().endswith(".mp3"):
                return True
    except OSError:
        return False
    tc = os.path.join(thu_muc, "tung-cau")
    if os.path.isdir(tc):
        try:
            for ten in os.listdir(tc):
                if ten.lower().endswith(".mp3"):
                    return True
        except OSError:
            pass
    return False


def _thu_muc_xuat_moi(thu_muc_goc, ten_goc):
    """Thu muc xuat cho lan sub moi. Neu thu muc mac dinh da co ket qua
    (file MP3 cu / tien trinh cu) thi dung ten moi 'ten (1)', 'ten (2)'...
    de KHONG ghi de file cu (khoi mat cong da sub)."""
    base = os.path.join(thu_muc_goc, ten_goc)
    if not _thu_muc_co_ket_qua(base):
        return base
    n = 1
    while True:
        cand = os.path.join(thu_muc_goc, "%s (%d)" % (ten_goc, n))
        if not _thu_muc_co_ket_qua(cand):
            return cand
        n += 1


# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE + " v" + VERSION)
        self.geometry("920x640")
        self.resizable(True, True)
        self.cfg = doc_config()
        self.hang_doi = queue.Queue()
        self.dang_chay = False
        self._yeu_cau_huy = threading.Event()  # co huy: worker kiem tra
        # giua cac cau, dung sau khi cau dang doc xong (khong ngat giua
        # cau, khong treo giao dien).
        # v1.3: tien trinh dang do de nut "Tiep tuc" dung (None neu khong
        # co); thu muc xuat dang dung cho file SRT da nap (mac dinh
        # <thu muc luu>/<ten file SRT>, doi khi "Sub lai tu dau" tao
        # thu muc moi).
        self.tien_trinh = None
        self.thu_muc_xuat = None
        self.cac_cau = []  # v1.3: danh sach cau SRT da nap (nut Nghe thu)
        # v1.3: trang thai nghe thu giong (nut PLAY phat ra loa).
        self.dang_nghe = False
        self._dung_nghe = threading.Event()  # nut Dung dat co nay
        self._dung_ui()
        self.after(200, self._xu_ly_hang_doi)

    # ----- giao dien -----
    def _dung_ui(self):
        pad = {"padx": 8, "pady": 4}
        f = tk.Frame(self)
        f.pack(fill="x", **pad)

        tk.Label(f, text="File SRT:").grid(row=0, column=0, sticky="w")
        self.e_srt = tk.Entry(f, width=62)
        self.e_srt.grid(row=0, column=1, sticky="we")
        self.btn_chon_srt = tk.Button(f, text="Chọn...",
                                      command=self._chon_srt)
        self.btn_chon_srt.grid(row=0, column=2)
        f.columnconfigure(1, weight=1)

        tk.Label(f, text="Thư mục lưu:").grid(row=1, column=0, sticky="w")
        self.e_luu = tk.Entry(f, width=62)
        self.e_luu.grid(row=1, column=1, sticky="we")
        self.e_luu.insert(0, self.cfg.get("thu_muc_luu", ""))
        self.btn_chon_luu = tk.Button(f, text="Chọn...",
                                      command=self._chon_thu_muc)
        self.btn_chon_luu.grid(row=1, column=2)

        f2 = tk.Frame(self)
        f2.pack(fill="x", **pad)
        tk.Label(f2, text="Giọng đọc:").grid(row=0, column=0, sticky="w")
        self.cb_giong = ttk.Combobox(f2, values=list(GIONG.keys()),
                                     state="readonly", width=22)
        self.cb_giong.set(self.cfg.get("giong", GIONG_MAC_DINH))
        self.cb_giong.grid(row=0, column=1, sticky="w", padx=4)
        # Doi giong thi tien trinh cu khong con hop le -> danh gia lai
        # nut "Tiep tuc" (v1.3).
        self.cb_giong.bind("<<ComboboxSelected>>",
                           lambda e: self._cap_nhat_nut_tiep_tuc())

        # v1.3: toc do dang HE SO NHAN giong trang web test (0.5x-2.0x,
        # buoc 0.01 - 1.35x chinh duoc, gia tri config cu nhu 1.09x
        # cung giu nguyen duoc), mac dinh 1.00x.
        tk.Label(f2, text="Tốc độ:").grid(row=1, column=0, sticky="w")
        self.sl_toc_do = tk.Scale(f2, from_=0.5, to=2.0, resolution=0.01,
                                  orient="horizontal", length=220)
        self.sl_toc_do.set(_chuyen_toc_do_cu(self.cfg.get("toc_do", 1.0)))
        self.sl_toc_do.grid(row=1, column=1, sticky="w", padx=4)
        self.lb_toc_do = tk.Label(f2, text="1.00x")
        self.lb_toc_do.grid(row=1, column=2, sticky="w")
        self.sl_toc_do.configure(command=self._doi_toc_do)

        # v1.4 - Toc do tu dong theo tung cau (theo iContent): cau dai
        # doc nhanh hon moi kip slot, cau ngan doc dung nhip. Bat thi
        # moi cau tu tang toc toi da den "Toc do toi da" (mac dinh
        # 1.35x); tat thi moi cau doc dung toc do co ban (hanh vi cu
        # v1.3).
        self.var_tu_dong_toc_do = tk.BooleanVar(
            value=bool(self.cfg.get("tu_dong_toc_do", True)))
        self.cb_tu_dong = tk.Checkbutton(
            f2, text="Tự động chỉnh tốc độ từng câu",
            variable=self.var_tu_dong_toc_do,
            command=self._doi_tu_dong_toc_do)
        self.cb_tu_dong.grid(row=2, column=1, sticky="w", padx=4)
        tk.Label(f2, text="Tốc độ tối đa:").grid(row=3, column=0,
                                                 sticky="w")
        self.sl_toc_do_toi_da = tk.Scale(
            f2, from_=1.0, to=2.0, resolution=0.01, orient="horizontal",
            length=220)
        self.sl_toc_do_toi_da.set(
            max(1.0, min(2.0, float(self.cfg.get("toc_do_toi_da", 1.35)))))
        self.sl_toc_do_toi_da.grid(row=3, column=1, sticky="w", padx=4)
        self.lb_toc_do_toi_da = tk.Label(f2, text="1.35x")
        self.lb_toc_do_toi_da.grid(row=3, column=2, sticky="w")
        self.sl_toc_do_toi_da.configure(command=self._doi_toc_do_toi_da)
        if not self.var_tu_dong_toc_do.get():
            self.sl_toc_do_toi_da.configure(state="disabled")

        tk.Label(f2, text="Cao độ:").grid(row=4, column=0, sticky="w")
        self.sl_cao_do = tk.Scale(f2, from_=-20, to=20, orient="horizontal",
                                  length=220)
        self.sl_cao_do.set(int(self.cfg.get("cao_do", 0)))
        self.sl_cao_do.grid(row=4, column=1, sticky="w", padx=4)
        self.lb_cao_do = tk.Label(f2, text="+0Hz")
        self.lb_cao_do.grid(row=4, column=2, sticky="w")
        self.sl_cao_do.configure(command=self._doi_cao_do)
        # v1.3 - Nghe thu giong: go 1 doan van ngan vao o nay (de trong
        # thi nghe cau dang chon trong danh sach), bam nut PLAY la doc
        # va PHAT TIENG RA LOA NGAY trong tool (khong tao file MP3,
        # khong mo trinh phat ngoai). Nut Dung de dung giua chung.
        tk.Label(f2, text="Nghe thử:").grid(row=5, column=0, sticky="w")
        self.e_nghe_thu = tk.Entry(f2, width=30)
        self.e_nghe_thu.grid(row=5, column=1, sticky="w", padx=4)
        self.btn_nghe_thu = tk.Button(f2, text="▶ Nghe thử",
                                      command=self.bam_nghe_thu)
        self.btn_nghe_thu.grid(row=5, column=2, sticky="w", padx=2)
        self.btn_dung_nghe = tk.Button(f2, text="Dừng",
                                       command=self._dung_nghe_thu,
                                       state="disabled")
        self.btn_dung_nghe.grid(row=5, column=3, sticky="w", padx=2)
        self.lb_toc_do.configure(text=_dinh_dang_toc_do(self.sl_toc_do.get()))
        self.lb_toc_do_toi_da.configure(
            text=_dinh_dang_toc_do(self.sl_toc_do_toi_da.get()))
        self.lb_cao_do.configure(text=_dinh_dang_cao_do(self.sl_cao_do.get()))

        f3 = tk.Frame(self)
        f3.pack(fill="x", **pad)
        tk.Label(f3, text="Đầu ra:").grid(row=0, column=0, sticky="w")
        self.che_do = tk.StringVar(value=self.cfg.get("che_do", "gop"))
        tk.Radiobutton(f3, text="Gộp 1 file lồng tiếng (MP3)",
                       variable=self.che_do, value="gop",
                       command=self._cap_nhat_nut_tiep_tuc).grid(
                           row=0, column=1, sticky="w")
        tk.Radiobutton(f3, text="Từng câu riêng (MP3)",
                       variable=self.che_do, value="rieng",
                       command=self._cap_nhat_nut_tiep_tuc).grid(
                           row=0, column=2, sticky="w")
        tk.Radiobutton(f3, text="Cả hai",
                       variable=self.che_do, value="ca_hai",
                       command=self._cap_nhat_nut_tiep_tuc).grid(
                           row=0, column=3, sticky="w")

        # Danh sach cau trong file SRT: hien ngay khi chon file, cap nhat
        # trang thai tung cau trong luc xu ly (Cho/Dang doc/Xong/Loi).
        f_ds = tk.Frame(self)
        f_ds.pack(fill="both", expand=True, **pad)
        self.lb_so_cau = tk.Label(f_ds, text="Chưa chọn file SRT.",
                                  anchor="w")
        self.lb_so_cau.pack(fill="x")
        cot = ("stt", "bat_dau", "ket_thuc", "noi_dung", "trang_thai")
        self.tree_cau = ttk.Treeview(f_ds, columns=cot, show="headings",
                                     height=6)
        self.tree_cau.heading("stt", text="#")
        self.tree_cau.heading("bat_dau", text="Bắt đầu")
        self.tree_cau.heading("ket_thuc", text="Kết thúc")
        self.tree_cau.heading("noi_dung", text="Nội dung")
        self.tree_cau.heading("trang_thai", text="Trạng thái")
        self.tree_cau.column("stt", width=40, anchor="center")
        self.tree_cau.column("bat_dau", width=95, anchor="center")
        self.tree_cau.column("ket_thuc", width=95, anchor="center")
        self.tree_cau.column("noi_dung", width=300)
        self.tree_cau.column("trang_thai", width=130)
        sb_tree = ttk.Scrollbar(f_ds, orient="vertical",
                                command=self.tree_cau.yview)
        self.tree_cau.configure(yscrollcommand=sb_tree.set)
        self.tree_cau.pack(side="left", fill="both", expand=True)
        sb_tree.pack(side="left", fill="y")
        self._tree_ids = {}
        self.thu_muc_ket_qua = None
        self.file_gop = None

        f4 = tk.Frame(self)
        f4.pack(fill="x", **pad)
        # Nut chinh: xuat MP3 long tieng (nut to, chu dam).
        self.btn_bat_dau = tk.Button(
            f4, text="XUẤT MP3 LỒNG TIẾNG", command=self._bat_dau,
            font=("TkDefaultFont", 11, "bold"), padx=10, pady=4)
        self.btn_bat_dau.pack(side="left", padx=4)
        # v1.3 - nut "Tiep tuc": chi sang khi co tien trinh dang do da luu
        # (da xong den cau nao, file MP3 nao); bam thi doc tiep tu cau
        # chua xong va noi vao file cu, khong doc lai cau da xong.
        self.btn_tiep_tuc = tk.Button(
            f4, text="Tiếp tục", command=self._bat_dau_tiep_tuc,
            state="disabled", padx=10, pady=4)
        self.btn_tiep_tuc.pack(side="left", padx=4)
        # v1.3 - nut "Sub lai tu dau": doc lai tu cau 1, tao file MP3 moi
        # (thu muc moi ten (1), (2)... neu file cu da co, khong ghi de).
        self.btn_sub_lai = tk.Button(
            f4, text="Sub lại từ đầu", command=self._bat_dau_sub_lai,
            state="disabled", padx=10, pady=4)
        self.btn_sub_lai.pack(side="left", padx=4)
        # Nut Huy: chi bat khi dang chay, bam la dung sau cau hien tai.
        self.btn_huy = tk.Button(f4, text="Hủy", command=self._bam_huy,
                                 state="disabled", padx=10, pady=4)
        self.btn_huy.pack(side="left", padx=4)
        self.btn_kiem_tra = tk.Button(
            f4, text="Kiểm tra kết nối giọng",
            command=self._kiem_tra_giong)
        self.btn_kiem_tra.pack(side="left", padx=4)
        self.btn_cap_nhat = tk.Button(
            f4, text="Kiểm tra cập nhật",
            command=self.bam_kiem_tra_cap_nhat)
        self.btn_cap_nhat.pack(side="left", padx=4)
        tk.Button(f4, text="Mở thư mục kết quả",
                  command=self._mo_thu_muc_ket_qua).pack(side="left", padx=4)

        self.lb_tien_trinh = tk.Label(self, text="Chưa chạy.")
        self.lb_tien_trinh.pack(fill="x", padx=8)
        self.thanh_tien_trinh = ttk.Progressbar(self, orient="horizontal",
                                                mode="determinate")
        self.thanh_tien_trinh.pack(fill="x", padx=8, pady=4)
        # Dong ket qua sau khi xuat xong: duong dan + do dai file MP3.
        self.lb_ket_qua = tk.Label(self, text="", anchor="w", wraplength=680,
                                   justify="left", fg="green")
        self.lb_ket_qua.pack(fill="x", padx=8)

        tk.Label(self, text="Nhật ký:").pack(anchor="w", padx=8)
        self.txt_log = tk.Text(self, height=16, wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=4)
        sb = tk.Scrollbar(self.txt_log, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)

    # ----- doi toc do / cao do (v1.3: doi cai dat thi tien trinh cu co
    # the khong con hop le -> danh gia lai nut "Tiep tuc") -----
    def _doi_toc_do(self, v):
        # v1.3: toc do la he so nhan (1.35x) - hien thi '1.35x'.
        self.lb_toc_do.configure(text=_dinh_dang_toc_do(float(v)))
        self._cap_nhat_nut_tiep_tuc()

    def _doi_tu_dong_toc_do(self):
        # v1.4: bat/tat tu dong toc do - thanh Toc do toi da chi co
        # nghia khi bat (tat thi mo di). Doi cai dat thi tien trinh cu
        # co the khong con hop le -> danh gia lai nut "Tiep tuc".
        if self.var_tu_dong_toc_do.get():
            self.sl_toc_do_toi_da.configure(state="normal")
        else:
            self.sl_toc_do_toi_da.configure(state="disabled")
        self._cap_nhat_nut_tiep_tuc()

    def _doi_toc_do_toi_da(self, v):
        # v1.4: toc do toi da la he so nhan (1.35x) - hien thi '1.35x'.
        self.lb_toc_do_toi_da.configure(text=_dinh_dang_toc_do(float(v)))
        self._cap_nhat_nut_tiep_tuc()

    def _doi_cao_do(self, v):
        self.lb_cao_do.configure(text=_dinh_dang_cao_do(int(float(v))))
        self._cap_nhat_nut_tiep_tuc()

    # ----- khoa / mo nut khi dang chay (v1.3) -----
    def _khoa_nut_khi_chay(self, cho_huy=True):
        """Vo hieu hoa cac nut hanh dong trong luc dang xuat (hoac dang
        kiem tra giong): nut Kiem tra ket noi giong, Kiem tra cap nhat,
        2 nut Chon... file/thu muc, nut Tiep tuc, nut Sub lai tu dau va
        nut XUAT deu mo di - chi de nut Huy sang (neu cho_huy). Tranh
        truong hop bam kiem tra cung luc voi dang xuat gay xung dot
        (ca hai cung goi giong)."""
        for b in (self.btn_chon_srt, self.btn_chon_luu, self.btn_kiem_tra,
                  self.btn_cap_nhat, self.btn_tiep_tuc, self.btn_sub_lai,
                  self.btn_bat_dau, self.btn_nghe_thu):
            b.configure(state="disabled")
        self.btn_dung_nghe.configure(state="disabled")
        self.btn_huy.configure(state="normal" if cho_huy else "disabled")

    def _mo_khoa_nut(self):
        """Bat lai cac nut sau khi xuat/kiem tra xong (hoac da huy).
        Nut Tiep tuc / Sub lai tu dau thi danh gia lai theo tien trinh
        da luu (co the vua duoc luu khi huy)."""
        for b in (self.btn_chon_srt, self.btn_chon_luu, self.btn_kiem_tra,
                  self.btn_cap_nhat, self.btn_bat_dau, self.btn_nghe_thu):
            b.configure(state="normal")
        self.btn_dung_nghe.configure(state="disabled")
        self.btn_huy.configure(state="disabled")
        self._cap_nhat_nut_tiep_tuc()

    # ----- nut "Tiep tuc" / "Sub lai tu dau" (v1.3) -----
    def _cap_nhat_nut_tiep_tuc(self):
        """Danh gia lai nut Tiep tuc / Sub lai tu dau theo file SRT da nap
        va tien trinh da luu. Goi sau khi nap SRT, doi cai dat (giong/toc
        do/cao do/che do/thu muc luu), xuat xong hoac da huy.
        - Sub lai tu dau: sang khi da nap file SRT (co danh sach cau).
        - Tiep tuc: chi sang khi co tien trinh dang do HOP LE (dung file
          SRT, dung giong/toc do/cao do/che do, con cau chua xong, file
          cac cau da xong van con)."""
        co_srt = bool(self._tree_ids)
        self.btn_sub_lai.configure(state="normal" if co_srt else "disabled")
        self.tien_trinh = self._tien_trinh_hop_le() if co_srt else None
        self.btn_tiep_tuc.configure(
            state="normal" if self.tien_trinh else "disabled")

    def _tien_trinh_hop_le(self):
        """Doc tien-trinh.json trong thu muc xuat hien tai (va cac thu
        muc (1), (2)... neu lan xuat truoc tao thu muc moi), kiem tra
        con hop le khong. Tra ve dict tien trinh da loc (chi giu cau
        nao co file audio that) hoac None neu khong dung duoc nua (doi
        file SRT, doi giong/toc do/cao do/che do, khong con cau chua
        xong, hoac file cac cau da xong da mat). Neu co nhieu tien
        trinh thi lay cai co nhieu cau xong nhat."""
        if not self.thu_muc_xuat:
            return None
        srt = self.e_srt.get().strip()
        if not srt or not os.path.isfile(srt):
            return None
        try:
            st = os.stat(srt)
        except OSError:
            return None
        # Cac thu muc ung vien: thu muc mac dinh + cac thu muc (1),
        # (2)... (lan xuat truoc co the da tao thu muc moi vi thu muc
        # cu da co ket qua).
        thu_muc_goc = os.path.dirname(self.thu_muc_xuat)
        ten_goc = os.path.basename(self.thu_muc_xuat)
        ung_vien = [self.thu_muc_xuat]
        for i in range(1, 21):
            thu_muc_i = os.path.join(thu_muc_goc, "%s (%d)" % (ten_goc, i))
            if os.path.isdir(thu_muc_i):
                ung_vien.append(thu_muc_i)
            else:
                break
        tot_nhat = None
        for thu_muc in ung_vien:
            tt = _doc_tien_trinh(thu_muc)
            if not tt:
                continue
            if os.path.abspath(tt.get("srt", "")) != os.path.abspath(srt):
                continue
            if (tt.get("srt_kich_thuoc") != st.st_size
                    or int(tt.get("srt_mtime", -1)) != int(st.st_mtime)):
                continue
            try:
                # v1.3: toc_do la he so nhan (so thuc) - so sanh co
                # dung sai nho vi slider luu dang float.
                toc_do_tt = float(tt.get("toc_do", 1.0))
                toc_do_hien = float(self.sl_toc_do.get())
                # v1.4: toc_do_toi_da + tu_dong_toc_do cung phai khop
                # (doi cai dat toc do thi cac cau con lai doc khac di).
                # Tien trinh v1.3 cu khong co 2 khoa nay -> mac dinh
                # (1.35x, True) nen van hop le neu giao dien dang de
                # mac dinh.
                toi_da_tt = float(tt.get("toc_do_toi_da", 1.35))
                toi_da_hien = float(self.sl_toc_do_toi_da.get())
                tu_dong_tt = bool(tt.get("tu_dong_toc_do", True))
                if (tt.get("giong") != self.cb_giong.get()
                        or abs(toc_do_tt - toc_do_hien) > 0.001
                        or abs(toi_da_tt - toi_da_hien) > 0.001
                        or tu_dong_tt != bool(
                            self.var_tu_dong_toc_do.get())
                        or int(tt.get("cao_do", 0)) != int(self.sl_cao_do.get())
                        or tt.get("che_do") != self.che_do.get()):
                    continue
            except (TypeError, ValueError):
                continue
            tong = int(tt.get("tong_cau", 0))
            if tong != len(self._tree_ids) or tong <= 0:
                continue
            thu_muc_rieng = tt.get("thu_muc_rieng") or os.path.join(
                tt.get("thu_muc", thu_muc), "tung-cau")
            xong = []
            for chi_so in tt.get("cau_da_xong", []):
                try:
                    chi_so = int(chi_so)
                except (TypeError, ValueError):
                    continue
                f = os.path.join(thu_muc_rieng, "%03d.mp3" % chi_so)
                # Chi tinh la xong neu file audio that su ton tai VA co
                # du lieu (file 0 byte do doc loi de lai thi phai doc
                # lai).
                if os.path.isfile(f) and os.path.getsize(f) > 0:
                    xong.append(chi_so)
            if not xong or len(xong) >= tong:
                continue
            tt = dict(tt)
            tt["cau_da_xong"] = sorted(set(xong))
            tt["thu_muc_rieng"] = thu_muc_rieng
            tt["thu_muc"] = tt.get("thu_muc", thu_muc)
            # v1.4: toc do thuc tung cau da xong (de hien lai trang thai
            # "Xong (1.60x)" khi noi lai file cu; khoa JSON la chuoi nen
            # doi lai sang so nguyen).
            toc_do_cau = {}
            try:
                for k, v in (tt.get("toc_do_cau") or {}).items():
                    toc_do_cau[int(k)] = float(v)
            except (TypeError, ValueError):
                toc_do_cau = {}
            tt["toc_do_cau"] = toc_do_cau
            if tot_nhat is None or len(xong) > len(
                    tot_nhat["cau_da_xong"]):
                tot_nhat = tt
        return tot_nhat

    # ----- chon file / danh sach cau -----
    def _chon_srt(self):
        p = filedialog.askopenfilename(filetypes=[("Phụ đề SRT", "*.srt"),
                                                 ("Mọi file", "*.*")])
        if p:
            self.e_srt.delete(0, "end")
            self.e_srt.insert(0, p)
            self._nap_danh_sach_cau(p)

    def _nap_danh_sach_cau(self, duong_dan):
        """Import file SRT: doc ngay va hien danh sach cau + thoi gian.
        Tra ve list cau, hoac None neu loi."""
        for item in self.tree_cau.get_children():
            self.tree_cau.delete(item)
        self._tree_ids = {}
        try:
            cac_cau = doc_srt(duong_dan)
        except Exception as e:
            self.lb_so_cau.configure(
                text="Lỗi đọc file SRT: %s" % e)
            messagebox.showerror(APP_TITLE, "Lỗi đọc file SRT:\n%s" % e)
            return None
        if not cac_cau:
            self.lb_so_cau.configure(
                text="Không tìm thấy câu phụ đề nào trong file này.")
            self.cac_cau = []
            return []
        # v1.3: giu danh sach cau de nut 'Nghe thu' lay cau dang chon.
        self.cac_cau = cac_cau
        for cau in cac_cau:
            iid = self.tree_cau.insert("", "end", values=(
                cau["chi_so"],
                _dinh_dang_ms(cau["bat_dau_ms"]),
                _dinh_dang_ms(cau["ket_thuc_ms"]),
                cau["text"][:80],
                "Chờ"))
            self._tree_ids[cau["chi_so"]] = iid
        tong_ms = max(c["ket_thuc_ms"] for c in cac_cau)
        self.lb_so_cau.configure(
            text="Đã nạp %d câu, tổng dài %.1f giây (từ %s đến %s)." % (
                len(cac_cau), tong_ms / 1000.0,
                _dinh_dang_ms(cac_cau[0]["bat_dau_ms"]),
                _dinh_dang_ms(tong_ms)))
        self._log("Đã nạp %d câu từ file SRT." % len(cac_cau))
        # v1.3: thu muc xuat mac dinh cho file SRT nay + danh gia lai
        # nut "Tiep tuc" (co tien trinh dang do cua file nay khong?).
        ten_goc = os.path.splitext(os.path.basename(duong_dan))[0]
        thu_muc_goc = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        self.thu_muc_xuat = os.path.join(thu_muc_goc, ten_goc)
        self._cap_nhat_nut_tiep_tuc()
        return cac_cau

    def _dat_trang_thai_cau(self, chi_so, trang_thai):
        """Dat trang thai 1 cau trong danh sach (goi tu luong worker,
        qua hang doi de dung luong chinh cap nhat giao dien)."""
        self.hang_doi.put(("trang_thai_cau", chi_so, trang_thai))

    def _chon_thu_muc(self):
        p = filedialog.askdirectory()
        if p:
            self.e_luu.delete(0, "end")
            self.e_luu.insert(0, p)
            # Doi thu muc luu thi thu muc xuat doi theo -> danh gia lai
            # nut "Tiep tuc" (v1.3).
            if self._tree_ids:
                srt = self.e_srt.get().strip()
                ten_goc = os.path.splitext(os.path.basename(srt))[0]
                self.thu_muc_xuat = os.path.join(p, ten_goc)
            self._cap_nhat_nut_tiep_tuc()

    def _mo_thu_muc_ket_qua(self):
        # Uu tien mo dung thu muc chua file MP3 vua xuat; chua co thi mo
        # thu muc luu da chon.
        p = self.thu_muc_ket_qua or self.e_luu.get().strip() \
            or mac_dinh_thu_muc_luu()
        if os.path.isdir(p):
            if sys.platform.startswith("win"):
                os.startfile(p)
            else:
                messagebox.showinfo(APP_TITLE, "Thư mục kết quả:\n" + p)
        else:
            messagebox.showinfo(APP_TITLE, "Chưa có thư mục kết quả:\n" + p)

    # ----- log / tien trinh -----
    def _log(self, s):
        self.hang_doi.put(("log", s))

    def _tien_trinh(self, phan_tram, nhan):
        self.hang_doi.put(("tien_trinh", phan_tram, nhan))

    def _xu_ly_hang_doi(self):
        try:
            while True:
                muc = self.hang_doi.get_nowait()
                if muc[0] == "log":
                    self.txt_log.insert("end", muc[1] + "\n")
                    self.txt_log.see("end")
                elif muc[0] == "tien_trinh":
                    self.thanh_tien_trinh["value"] = muc[1]
                    self.lb_tien_trinh.configure(text=muc[2])
                elif muc[0] == "trang_thai_cau":
                    iid = self._tree_ids.get(muc[1])
                    if iid and self.tree_cau.exists(iid):
                        vals = list(self.tree_cau.item(iid, "values"))
                        vals[4] = muc[2]
                        self.tree_cau.item(iid, values=tuple(vals))
                        self.tree_cau.see(iid)
                elif muc[0] == "ket_qua":
                    self.lb_ket_qua.configure(text=muc[1])
                elif muc[0] == "cap_nhat_xong":
                    self._cap_nhat_xong(muc[1])
                elif muc[0] == "cap_nhat_loi":
                    self._cap_nhat_loi(muc[1])
                elif muc[0] == "tai_moi_xong":
                    self._tai_ban_moi_xong(muc[1])
                elif muc[0] == "tai_moi_loi":
                    self._tai_ban_moi_loi(muc[1])
                elif muc[0] == "nghe_xong":
                    # v1.3: nghe thu xong (tu nhien hoac bam Dung) - mo
                    # lai nut Nghe thu, tat nut Dung.
                    self.dang_nghe = False
                    self._dung_nghe.clear()
                    if not self.dang_chay:
                        self.btn_nghe_thu.configure(state="normal")
                    self.btn_dung_nghe.configure(state="disabled")
                elif muc[0] == "xong":
                    self.dang_chay = False
                    self._mo_khoa_nut()
        except queue.Empty:
            pass
        self.after(200, self._xu_ly_hang_doi)

    def _luu_cai_dat_hien_tai(self):
        self.cfg.update({
            "giong": self.cb_giong.get(),
            # v1.3: toc_do luu dang he so nhan (1.35x).
            "toc_do": float(self.sl_toc_do.get()),
            # v1.4: toc do toi da + bat/tat tu dong toc do tung cau.
            "toc_do_toi_da": float(self.sl_toc_do_toi_da.get()),
            "tu_dong_toc_do": bool(self.var_tu_dong_toc_do.get()),
            "cao_do": int(self.sl_cao_do.get()),
            "thu_muc_luu": self.e_luu.get().strip(),
            "che_do": self.che_do.get(),
        })
        luu_config(self.cfg)

    # ----- kiem tra giong -----
    def _kiem_tra_giong(self):
        if self.dang_chay:
            return
        self._luu_cai_dat_hien_tai()
        # Lay het gia tri giao dien o luong chinh, truyen sang luong worker
        # (luong worker khong doc truc tiep widget tkinter - khong an toan).
        ts = {
            "voice": GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH]),
            "giong_hien_thi": self.cb_giong.get(),
            "toc_do": float(self.sl_toc_do.get()),
            "cao_do": int(self.sl_cao_do.get()),
            "thu_muc": self.e_luu.get().strip() or mac_dinh_thu_muc_luu(),
        }
        self.dang_chay = True
        # v1.3: khoa cac nut khac trong luc kiem tra (khong cho Huy vi
        # kiem tra chi doc 1 cau ngan, xong ngay).
        self._khoa_nut_khi_chay(cho_huy=False)
        threading.Thread(target=self._chay_kiem_tra, args=(ts,),
                         daemon=True).start()

    def _chay_kiem_tra(self, ts):
        voice = ts["voice"]
        # v1.3 - giong may: khong can edge-tts, doc thu thang ra loa
        # (khong can file, khong can ffmpeg).
        if voice == "may":
            self._log("Kiểm tra giọng %s (giọng tiếng Việt có sẵn trên "
                      "máy Windows)..." % ts["giong_hien_thi"])
            ok, loi = nghe_giong_may(MAU_DOC_THU, ts["toc_do"],
                                     ts["cao_do"], log_cb=self._log)
            if ok:
                self._log("OK! Đã đọc thử ra loa bằng giọng máy.")
            else:
                self._log("LỖI: không dùng được giọng máy. %s" % loi)
            self.hang_doi.put(("xong",))
            return
        try:
            import edge_tts
            ver = getattr(edge_tts, "__version__", "?")
            import edge_tts.communicate as _comm
            may_chu = _ten_may_chu(_comm.WSS_URL)
        except Exception:
            ver, may_chu = "?", "?"
        self._log("Kiểm tra giọng %s (%s)..." % (ts["giong_hien_thi"], voice))
        self._log("edge-tts %s; máy chủ giọng: %s" % (ver, may_chu))
        thu_muc = ts["thu_muc"]
        try:
            os.makedirs(thu_muc, exist_ok=True)
        except OSError as e:
            self._log("Lỗi tạo thư mục: %s" % e)
            self.hang_doi.put(("xong",))
            return
        dich = os.path.join(thu_muc, "doc-thu.mp3")
        ok, bo_xac_minh, loi = doc_cau_thanh_mp3(
            MAU_DOC_THU, voice, ts["toc_do"], ts["cao_do"], dich,
            log_cb=self._log)
        if ok:
            self._log("OK! Đã tạo file đọc thử: %s%s" % (
                dich, " (đã dùng chế độ bỏ xác minh SSL)" if bo_xac_minh else ""))
        else:
            self._log("LỖI: không tạo được giọng. %s" % loi)
            self._log("Tool đã thử cả máy chủ gốc speech.platform.bing.com "
                      "và máy chủ phụ api.msedgeservices.com. Kiểm tra mạng "
                      "rồi bấm lại; nếu vẫn lỗi, xem mã lỗi [403/429/"
                      "khong-co-audio] trong log ở trên.")
        self.hang_doi.put(("xong",))

    # ----- nghe thu giong (nut PLAY phat ra loa, v1.3) -----
    def bam_nghe_thu(self):
        """Nut '▶ Nghe thu': doc 1 cau va PHAT TIENG RA LOA NGAY trong
        tool (khong tao file MP3, khong mo trinh phat ngoai). Lay van
        ban tu o go (neu co) hoac tu cau dang chon trong danh sach.
        Khong nghe duoc trong luc dang xuat (tranh 2 viec cung goi
        giong 1 luc)."""
        if self.dang_chay or self.dang_nghe:
            return
        text = self.e_nghe_thu.get().strip()
        if not text:
            # Lay cau dang chon trong danh sach (neu co). _tree_ids map
            # chi_so -> iid nen phai tim nguoc chi_so tu iid da chon.
            chon = self.tree_cau.selection()
            if chon:
                iid_chon = chon[0]
                chi_so = None
                for cs, iid in self._tree_ids.items():
                    if iid == iid_chon:
                        chi_so = cs
                        break
                if chi_so is not None:
                    for cau in (self.cac_cau or []):
                        if cau["chi_so"] == chi_so:
                            text = cau["text"]
                            break
        if not text:
            messagebox.showinfo(
                APP_TITLE,
                "Hãy gõ 1 đoạn văn ngắn vào ô Nghe thử, hoặc chọn 1 câu "
                "trong danh sách rồi bấm ▶ Nghe thử.")
            return
        voice = GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH])
        toc_do = float(self.sl_toc_do.get())
        cao_do = int(self.sl_cao_do.get())
        self.dang_nghe = True
        self._dung_nghe.clear()
        self.btn_nghe_thu.configure(state="disabled")
        self.btn_dung_nghe.configure(state="normal")
        self._log("Nghe thử giọng %s: %s"
                  % (self.cb_giong.get(), text[:80]))
        threading.Thread(target=self._nghe_thu_worker,
                         args=(text, voice, toc_do, cao_do),
                         daemon=True).start()

    def _nghe_thu_worker(self, text, voice, toc_do, cao_do):
        """Luong nghe thu: giong may thi doc thang ra loa; giong online
        thi doc ra file MP3 tam roi phat ra loa trong tool (MCI), xong
        xoa file tam (khong luu file)."""
        try:
            if voice == "may":
                ok, loi = nghe_giong_may(text, toc_do, cao_do,
                                         log_cb=self._log,
                                         dung=self._dung_nghe)
                if not ok:
                    self._log("LỖI nghe thử giọng máy: %s" % loi)
            else:
                import tempfile
                fd, tam_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                try:
                    ok, _, loi = doc_thanh_mp3(
                        text, voice, toc_do, cao_do, tam_path,
                        log_cb=self._log)
                    if not ok:
                        self._log("LỖI nghe thử: %s" % loi)
                    elif not self._dung_nghe.is_set():
                        ok_phat, loi_phat = _phat_mp3(
                            tam_path, dung=self._dung_nghe)
                        if not ok_phat and "đã dừng" not in loi_phat:
                            self._log("LỖI phát âm thanh: %s" % loi_phat)
                finally:
                    _xoa_file_quiet(tam_path)
        except Exception as e:
            self._log("LỖI nghe thử: %s" % _tom_tat_loi(e))
        finally:
            self.hang_doi.put(("nghe_xong",))

    def _dung_nghe_thu(self):
        """Nut 'Dung': dung nghe thu giua chung (dung phat audio /
        tat tien trinh giong may)."""
        if not self.dang_nghe:
            return
        self._dung_nghe.set()
        self._log("Đã dừng nghe thử.")

    # ----- tu cap nhat (v1.1, theo mau Chipchipdownload v6.2) -----
    # Repo PUBLIC nen khong can token: doc Releases qua API khong xac thuc.
    def bam_kiem_tra_cap_nhat(self):
        """Nut Kiem tra cap nhat: kiem tra ban moi tren GitHub Releases,
        co ban moi thi hoi roi tai exe ve tu va len (capnhat.bat)."""
        if self.dang_chay:
            return
        self._log("Đang kiểm tra bản mới trên GitHub...")
        threading.Thread(target=self._cap_nhat_worker, daemon=True).start()

    def _cap_nhat_worker(self):
        try:
            ket_qua = kiem_tra_cap_nhat()
            self.hang_doi.put(("cap_nhat_xong", ket_qua))
        except Exception as e:
            self.hang_doi.put(("cap_nhat_loi", str(e)))

    def _cap_nhat_xong(self, ket_qua):
        if not ket_qua:
            self._log("Đang dùng bản mới nhất: v%s." % VERSION)
            messagebox.showinfo("Đã là bản mới nhất",
                                "Bạn đang dùng bản mới nhất: v%s." % VERSION)
            return
        ver_moi = ket_qua["version_moi"]
        self._log("Có bản mới: v%s (đang dùng v%s)." % (ver_moi, VERSION))
        if not ket_qua.get("tai_url"):
            messagebox.showinfo(
                "Có bản mới: v%s" % ver_moi,
                "Đã có bản v%s nhưng bản này chưa có file exe đính kèm "
                "trên Release.\n\nTải bản mới bằng tay tại:\n%s"
                % (ver_moi, GITHUB_RELEASES_URL))
            return
        if not messagebox.askyesno(
                "Có bản mới: v%s" % ver_moi,
                "Bản đang dùng: v%s → Bản mới: v%s.\n\n"
                "Bấm Có để tải exe mới về và vá lên bản đang dùng "
                "(không cần cài lại, giữ nguyên cài đặt). "
                "Tool sẽ tự thoát rồi mở lại bản mới."
                % (VERSION, ver_moi)):
            return
        threading.Thread(target=self._tai_ban_moi_worker,
                         args=(ket_qua["tai_url"],
                               ket_qua.get("kich_thuoc")),
                         daemon=True).start()

    def _cap_nhat_loi(self, msg):
        self._log("Không kiểm tra được cập nhật: %s" % msg)
        messagebox.showerror(
            "Không kiểm tra được cập nhật",
            msg + "\n\nBản đang dùng: v%s.\nLấy bản mới bằng tay tại:\n%s"
            % (VERSION, GITHUB_RELEASES_URL))

    def _tai_ban_moi_worker(self, tai_url, kich_thuoc=None):
        try:
            bat_path, bak_path = tai_ban_moi_va_cap_nhat(
                tai_url, kich_thuoc, log_cb=self._log)
            self.hang_doi.put(("tai_moi_xong", (bat_path, bak_path)))
        except Exception as e:
            self.hang_doi.put(("tai_moi_loi", str(e)))

    def _tai_ban_moi_xong(self, ket_qua):
        bat_path, bak_path = ket_qua
        # Chay script cap nhat (cho tool thoat roi thay exe + mo lai).
        try:
            subprocess.Popen(["cmd", "/c", bat_path],
                             creationflags=subprocess.CREATE_NO_WINDOW
                             if sys.platform == "win32" else 0)
        except Exception:
            subprocess.Popen(bat_path, shell=True)
        messagebox.showinfo(
            "Đang cập nhật...",
            "Đã tải xong bản mới (đã kiểm chứng file hợp lệ). Tool sẽ "
            "thoát ngay, script cập nhật sẽ thay exe cũ bằng exe mới rồi "
            "tự mở lại tool.\n\nBản cũ được sao lưu tại:\n%s\n"
            "(nếu bản mới lỗi thì đổi tên file .bak này thành .exe để "
            "khôi phục)." % bak_path)
        try:
            self.destroy()
        finally:
            os._exit(0)

    def _tai_ban_moi_loi(self, msg):
        self._log("Lỗi tải bản mới: %s" % msg)
        messagebox.showerror("Lỗi tải bản mới", msg)

    # ----- chay chinh -----
    def _bam_huy(self):
        """Nut Huy: dat co, worker se dung sau khi cau dang doc xong
        (khong ngat giua cau). Mo nut ngay de khong bam 2 lan."""
        if not self.dang_chay:
            return
        self._yeu_cau_huy.set()
        self.btn_huy.configure(state="disabled")
        self._log("Đã bấm Hủy — sẽ dừng sau khi câu đang đọc xong...")

    def _bat_dau(self):
        """Nut XUAT MP3 LONG TIENG: xuat moi tu cau 1 vao thu muc mac
        dinh (neu thu muc da co ket qua cu thi tu dong dung thu muc
        moi ten (1), (2)... de khong ghi de - giong nut 'Sub lai tu
        dau')."""
        if self.dang_chay:
            return
        srt = self.e_srt.get().strip()
        if not srt or not os.path.isfile(srt):
            messagebox.showwarning(APP_TITLE, "Hãy chọn file SRT trước.")
            return
        # Neu danh sach cau chua nap (vd: go duong dan tay), nap ngay.
        if not self._tree_ids:
            if self._nap_danh_sach_cau(srt) is None:
                return
        ffmpeg = tim_ffmpeg()
        che_do = self.che_do.get()
        if che_do in ("gop", "ca_hai") and not ffmpeg:
            messagebox.showwarning(
                APP_TITLE,
                "Chế độ gộp cần ffmpeg. Không tìm thấy ffmpeg trong PATH "
                "hay cạnh file exe.\nHãy đặt ffmpeg.exe cạnh tool rồi chạy lại, "
                "hoặc chọn chế độ 'Từng câu riêng'.")
            return
        thu_muc_goc = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        ten_goc = os.path.splitext(os.path.basename(srt))[0]
        thu_muc_moi = _thu_muc_xuat_moi(thu_muc_goc, ten_goc)
        if thu_muc_moi != os.path.join(thu_muc_goc, ten_goc):
            self._log("Thư mục cũ đã có kết quả, xuất lần này vào thư mục "
                      "mới (không ghi đè file cũ): %s" % thu_muc_moi)
        self.thu_muc_xuat = thu_muc_moi
        self._bat_dau_chung(srt, ffmpeg, thu_muc_ghi_de=thu_muc_moi)

    def _bat_dau_tiep_tuc(self):
        """Nut Tiep tuc: doc tiep tu cau chua xong va noi vao file cu
        (khong doc lai cac cau da xong, khong tao file moi). Chi sang
        khi co tien trinh dang do hop le."""
        if self.dang_chay:
            return
        tt = self._tien_trinh_hop_le()
        if not tt:
            messagebox.showinfo(
                APP_TITLE,
                "Không còn tiến trình dở dang nào khớp với file SRT và "
                "cài đặt hiện tại (có thể anh đã đổi file SRT, giọng, "
                "tốc độ, cao độ hoặc chế độ đầu ra).")
            self._cap_nhat_nut_tiep_tuc()
            return
        srt = self.e_srt.get().strip()
        ffmpeg = tim_ffmpeg()
        if tt["che_do"] in ("gop", "ca_hai") and not ffmpeg:
            messagebox.showwarning(
                APP_TITLE,
                "Chế độ gộp cần ffmpeg. Không tìm thấy ffmpeg trong PATH "
                "hay cạnh file exe.\nHãy đặt ffmpeg.exe cạnh tool rồi chạy lại, "
                "hoặc chọn chế độ 'Từng câu riêng'.")
            return
        # Dong bo giao dien theo cai dat da luu trong tien trinh (de cac
        # cau moi doc cung giong/toc do/cao do/che do voi cau cu).
        self.cb_giong.set(tt["giong"])
        # v1.3: toc_do luu dang he so nhan (1.35x).
        self.sl_toc_do.set(float(tt["toc_do"]))
        # v1.4: toc_do_toi_da + tu_dong_toc_do (mac dinh v1.3 cu).
        self.sl_toc_do_toi_da.set(
            max(1.0, min(2.0, float(tt.get("toc_do_toi_da", 1.35)))))
        self.var_tu_dong_toc_do.set(bool(tt.get("tu_dong_toc_do", True)))
        if self.var_tu_dong_toc_do.get():
            self.sl_toc_do_toi_da.configure(state="normal")
        else:
            self.sl_toc_do_toi_da.configure(state="disabled")
        self.sl_cao_do.set(int(tt["cao_do"]))
        self.che_do.set(tt["che_do"])
        self.lb_toc_do.configure(
            text=_dinh_dang_toc_do(float(tt["toc_do"])))
        self.lb_toc_do_toi_da.configure(
            text=_dinh_dang_toc_do(float(tt.get("toc_do_toi_da", 1.35))))
        self.lb_cao_do.configure(
            text=_dinh_dang_cao_do(int(tt["cao_do"])))
        self.thu_muc_xuat = tt["thu_muc"]
        self._log("Tiếp tục từ tiến trình đã lưu: đã xong %d/%d câu, đọc "
                  "tiếp từ câu chưa xong và nối vào file cũ."
                  % (len(tt["cau_da_xong"]), tt["tong_cau"]))
        self._bat_dau_chung(srt, ffmpeg, thu_muc_ghi_de=tt["thu_muc"],
                            cau_da_xong_truoc=set(tt["cau_da_xong"]),
                            toc_do_cau_truoc=tt.get("toc_do_cau") or {},
                            la_tiep_tuc=True)

    def _bat_dau_sub_lai(self):
        """Nut Sub lai tu dau: doc lai tu cau 1, tao file MP3 moi (thu
        muc moi ten (1), (2)... neu file cu da co - khong ghi de file
        cu)."""
        if self.dang_chay:
            return
        srt = self.e_srt.get().strip()
        if not srt or not os.path.isfile(srt):
            messagebox.showwarning(APP_TITLE, "Hãy chọn file SRT trước.")
            return
        if not self._tree_ids:
            if self._nap_danh_sach_cau(srt) is None:
                return
        ffmpeg = tim_ffmpeg()
        che_do = self.che_do.get()
        if che_do in ("gop", "ca_hai") and not ffmpeg:
            messagebox.showwarning(
                APP_TITLE,
                "Chế độ gộp cần ffmpeg. Không tìm thấy ffmpeg trong PATH "
                "hay cạnh file exe.\nHãy đặt ffmpeg.exe cạnh tool rồi chạy lại, "
                "hoặc chọn chế độ 'Từng câu riêng'.")
            return
        thu_muc_goc = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        ten_goc = os.path.splitext(os.path.basename(srt))[0]
        thu_muc_moi = _thu_muc_xuat_moi(thu_muc_goc, ten_goc)
        self.thu_muc_xuat = thu_muc_moi
        if thu_muc_moi != os.path.join(thu_muc_goc, ten_goc):
            self._log("Sub lại từ đầu vào thư mục mới (không ghi đè file "
                      "cũ): %s" % thu_muc_moi)
        else:
            self._log("Sub lại từ đầu (chưa có kết quả cũ).")
        self._bat_dau_chung(srt, ffmpeg, thu_muc_ghi_de=thu_muc_moi)

    def _bat_dau_chung(self, srt, ffmpeg, thu_muc_ghi_de=None,
                       cau_da_xong_truoc=None, la_tiep_tuc=False,
                       toc_do_cau_truoc=None):
        """Chuan bi chung truoc khi chay worker xuat (lay het gia tri
        giao dien o luong chinh, khoa nut, mo worker)."""
        self._luu_cai_dat_hien_tai()
        # Lay het gia tri giao dien o luong chinh, truyen sang luong worker
        # (luong worker khong doc truc tiep widget tkinter - khong an toan).
        ts = {
            "voice": GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH]),
            "giong_hien_thi": self.cb_giong.get(),
            # v1.3: toc_do la he so nhan (1.35x).
            "toc_do": float(self.sl_toc_do.get()),
            # v1.4: toc do toi da + bat/tat tu dong toc do tung cau.
            "toc_do_toi_da": float(self.sl_toc_do_toi_da.get()),
            "tu_dong_toc_do": bool(self.var_tu_dong_toc_do.get()),
            "cao_do": int(self.sl_cao_do.get()),
            "che_do": self.che_do.get(),
            "thu_muc_goc": self.e_luu.get().strip() or mac_dinh_thu_muc_luu(),
        }
        self.dang_chay = True
        self._yeu_cau_huy.clear()
        # v1.3: khoa cac nut khac trong luc xuat (chi de nut Huy sang).
        # Neu dang nghe thu thi dung phat luon (tranh 2 viec cung goi
        # giong 1 luc).
        self._dung_nghe.set()
        self._khoa_nut_khi_chay(cho_huy=True)
        self.hang_doi.put(("ket_qua", ""))
        threading.Thread(target=self._chay,
                         args=(srt, ffmpeg, ts, thu_muc_ghi_de,
                               cau_da_xong_truoc, la_tiep_tuc,
                               toc_do_cau_truoc),
                         daemon=True).start()

    def _chay(self, srt, ffmpeg, ts, thu_muc_ghi_de=None,
              cau_da_xong_truoc=None, la_tiep_tuc=False,
              toc_do_cau_truoc=None):
        from pydub import AudioSegment
        if ffmpeg:
            AudioSegment.converter = ffmpeg
        voice = ts["voice"]
        toc_do = ts["toc_do"]
        cao_do = ts["cao_do"]
        che_do = ts["che_do"]
        thu_muc_goc = ts["thu_muc_goc"]
        # v1.4: toc do toi da + bat/tat tu dong toc do tung cau.
        toc_do_toi_da = ts.get("toc_do_toi_da", 1.35)
        tu_dong_toc_do = ts.get("tu_dong_toc_do", True)
        ten_goc = os.path.splitext(os.path.basename(srt))[0]
        # v1.3: thu muc xuat co the duoc chi dinh truoc (Tiep tuc: dung
        # lai thu muc cu; Xuat moi/Sub lai: thu muc moi (1), (2)...).
        thu_muc = thu_muc_ghi_de or os.path.join(thu_muc_goc, ten_goc)
        thu_muc_rieng = os.path.join(thu_muc, "tung-cau")
        self.thu_muc_ket_qua = thu_muc
        self.file_gop = None
        try:
            os.makedirs(thu_muc_rieng, exist_ok=True)
        except OSError as e:
            self._log("Lỗi tạo thư mục: %s" % e)
            self.hang_doi.put(("xong",))
            return
        # v1.3: chay moi (khong phai Tiep tuc) thi xoa tien trinh cu cua
        # thu muc nay (lan chay moi thay the no).
        if not la_tiep_tuc:
            _xoa_tien_trinh(thu_muc)
        try:
            cac_cau = doc_srt(srt)
        except Exception as e:
            self._log("Lỗi đọc file SRT: %s" % e)
            self.hang_doi.put(("xong",))
            return
        if not cac_cau:
            self._log("Không tìm thấy câu phụ đề nào trong file SRT.")
            self.hang_doi.put(("xong",))
            return
        tong = len(cac_cau)
        self._log("Đọc %d câu bằng giọng %s (%s), tốc độ %s, cao độ %s"
                  % (tong, ts["giong_hien_thi"], voice,
                     _dinh_dang_toc_do(toc_do), _dinh_dang_cao_do(cao_do)))
        # v1.4: bao ro che do toc do tu dong dang dung (de anh biet cau
        # dai se tu tang toc toi da bao nhieu).
        if tu_dong_toc_do:
            if not ffmpeg:
                self._log("Tự động chỉnh tốc độ từng câu đang BẬT nhưng "
                          "không tìm thấy ffmpeg (cần ffmpeg để đo thời "
                          "lượng và tăng tốc) - các câu sẽ đọc ở tốc độ "
                          "cơ bản %s." % _dinh_dang_toc_do(toc_do))
            else:
                self._log("Tự động chỉnh tốc độ từng câu: câu dài tự "
                          "tăng tốc tối đa %s (đo thời lượng thật rồi "
                          "dùng ffmpeg atempo, không gọi lại API giọng)."
                          % _dinh_dang_toc_do(toc_do_toi_da))
        self._log("Thư mục lưu: %s" % thu_muc)
        for cau in cac_cau:
            self._dat_trang_thai_cau(cau["chi_so"], "Chờ")
        loi_cau = {}  # chi_so -> ly do loi
        can_gop = che_do in ("gop", "ca_hai")
        so_cau_xong = 0  # dem that, dung ca khi huy giua chung
        cau_da_xong = set()  # chi_so cac cau da doc xong
        # v1.4: toc do thuc tung cau da xong (de luu vao tien trinh va
        # hien lai trang thai "Xong (1.60x)" khi Tiep tuc).
        toc_do_cau = dict(toc_do_cau_truoc or {})
        da_huy = False
        cau_dung = 0  # chi so cau dang doc luc bam Huy
        # v1.3 - GHEP DAN: moi cau doc xong la ghep ngay vao file long
        # tieng dang tao (dung moc thoi gian SRT), khong doi den cuoi
        # moi gop 1 lan. Huy giua chung hay loi giua chung thi file
        # gop van giu cac cau da xong; mo file ra nghe thu duoc ngay ca
        # khi chua chay xong.
        gop = None
        dich_gop = None
        if can_gop:
            dich_gop = os.path.join(thu_muc, ten_goc + "_long-tieng.mp3")
            gop = GopDan(
                os.path.join(thu_muc, ten_goc + "_long-tieng-tam.wav"),
                dich_gop,
                tong_ms=max(c["ket_thuc_ms"] for c in cac_cau),
                log_cb=self._log)
            self._log("Gộp dần: mỗi câu đọc xong sẽ ghép ngay vào file "
                      "lồng tiếng (đúng timestamp SRT). Vì API giọng "
                      "Microsoft chỉ nhận 1 đoạn văn mỗi lần gọi nên "
                      "tool phải đọc từng câu riêng rồi mới ghép lại "
                      "thành 1 file duy nhất - không gọi 1 lần cho cả "
                      "%d câu được." % tong)
        # v1.3 - TIEP TUC: cac cau da xong o lan truoc thi danh dau Xong
        # va noi lai vao file gop (doc lai file MP3 tung cau da co,
        # khong goi lai API giong). Cau nao file bi hong thi doc lai.
        if la_tiep_tuc and cau_da_xong_truoc:
            cau_hong = set()
            for cau in cac_cau:
                if cau["chi_so"] in cau_da_xong_truoc:
                    dich_cu = os.path.join(
                        thu_muc_rieng, "%03d.mp3" % cau["chi_so"])
                    if (gop is not None
                            and not gop.them_cau(cau, dich_cu)):
                        cau_hong.add(cau["chi_so"])
                        continue
                    cau_da_xong.add(cau["chi_so"])
                    so_cau_xong += 1
                    # v1.4: hien lai toc do thuc cua cau da xong (neu co
                    # luu trong tien trinh).
                    toc_do_cu = toc_do_cau.get(cau["chi_so"])
                    if tu_dong_toc_do and toc_do_cu is not None:
                        self._dat_trang_thai_cau(
                            cau["chi_so"], "Xong (%.2fx)" % toc_do_cu)
                    else:
                        self._dat_trang_thai_cau(cau["chi_so"], "Xong")
            if cau_hong:
                self._log("Có %d câu đã xong nhưng file bị hỏng, sẽ đọc "
                          "lại: %s" % (len(cau_hong), sorted(cau_hong)))
            self._log("Đã nối lại %d câu đã xong vào file gộp."
                      % len(cau_da_xong))

        def doc_1_cau(cau, i):
            """Doc 1 cau, cap nhat tien trinh + trang thai trong danh sach.
            Cau xong thi GHEP NGAY vao file gop (neu che do gop).
            Tra ve True neu xong."""
            nonlocal so_cau_xong
            dich = os.path.join(thu_muc_rieng, "%03d.mp3" % cau["chi_so"])
            self._tien_trinh(int((i - 1) * 100 / tong),
                             "Đang đọc câu %d/%d..." % (i, tong))
            self._dat_trang_thai_cau(cau["chi_so"], "Đang đọc...")
            self._log("Câu %d/%d (%.1fs): %s" % (
                i, tong, (cau["ket_thuc_ms"] - cau["bat_dau_ms"]) / 1000.0,
                cau["text"][:80]))
            ok, bo_xac_minh, loi = doc_cau_thanh_mp3(
                cau["text"], voice, toc_do, cao_do, dich,
                log_cb=self._log, ffmpeg=ffmpeg)
            if not ok:
                self._dat_trang_thai_cau(cau["chi_so"], "Lỗi: " + (loi or "?")[:60])
                self._log("  -> LỖI câu %d: %s" % (cau["chi_so"], loi))
                return False
            # v1.4: toc do tu dong theo slot SRT - do thoi luong that
            # cua file vua tao roi dung ffmpeg atempo tang toc neu can
            # (khong goi lai API giong). Trang thai hien toc do thuc
            # cua cau (vd "Xong (1.60x)").
            toc_do_thuc = _ap_dung_toc_do_tu_dong(
                dich, cau, toc_do, toc_do_toi_da, tu_dong_toc_do, ffmpeg,
                log_cb=self._log)
            toc_do_cau[cau["chi_so"]] = toc_do_thuc
            so_cau_xong += 1
            cau_da_xong.add(cau["chi_so"])
            if tu_dong_toc_do:
                self._dat_trang_thai_cau(cau["chi_so"],
                                         "Xong (%.2fx)" % toc_do_thuc)
            else:
                self._dat_trang_thai_cau(cau["chi_so"], "Xong")
            if bo_xac_minh:
                self._log("  -> Xong (đã dùng chế độ bỏ xác minh SSL)")
            # v1.3: ghep ngay cau vua xong vao file long tieng.
            if gop is not None:
                gop.them_cau(cau, dich)
            return True

        # Luot 1: doc het cac cau (dung ngay khi bam Huy). Cau nao da
        # xong o lan truoc (Tiep tuc) thi bo qua, khong doc lai.
        for i, cau in enumerate(cac_cau, 1):
            if self._yeu_cau_huy.is_set():
                da_huy = True
                cau_dung = i
                break
            if cau["chi_so"] in cau_da_xong:
                continue
            if not doc_1_cau(cau, i):
                loi_cau[cau["chi_so"]] = True
        # Luot 2: cau nao loi thi THU LAI 1 lan nua (loi mang thoang qua),
        # ghi ro ket qua tung cau, khong lang le bo qua. Bo qua neu da huy.
        if loi_cau and not da_huy:
            self._log("Thử lại %d câu lỗi: %s" % (len(loi_cau),
                                                  sorted(loi_cau)))
            for i, cau in enumerate(cac_cau, 1):
                if self._yeu_cau_huy.is_set():
                    da_huy = True
                    cau_dung = i
                    break
                if cau["chi_so"] not in loi_cau:
                    continue
                self._log("Đọc lại câu %d..." % cau["chi_so"])
                if doc_1_cau(cau, i):
                    del loi_cau[cau["chi_so"]]
                    self._log("  -> Câu %d đọc lại THÀNH CÔNG." % cau["chi_so"])
                else:
                    self._log("  -> Câu %d vẫn lỗi sau khi thử lại." % cau["chi_so"])
        so_xong = so_cau_xong
        if da_huy:
            self._tien_trinh(int(so_xong * 100 / tong),
                             "Đã hủy ở câu %d/%d." % (cau_dung, tong))
            self._log("Đã hủy ở câu %d/%d. Đã xong %d câu, giữ nguyên file "
                      "các câu đã xong trong %s."
                      % (cau_dung, tong, so_xong, thu_muc_rieng))
        else:
            self._tien_trinh(100, "Đã đọc xong %d/%d câu." % (so_xong, tong))
        if loi_cau:
            self._log("Cảnh báo: %d câu vẫn lỗi sau 2 lượt: %s"
                      % (len(loi_cau), sorted(loi_cau)))
            # v1.3: cau loi khong co audio - slot cua no giu khoang lang
            # trong file gop, khong lam hong file gop.
            for chi_so in sorted(loi_cau):
                self._log("Đã bỏ qua câu %d (không có audio) - slot của "
                          "nó giữ khoảng lặng trong file gộp." % chi_so)
        # v1.3 - HOAN TAT file gop dan: chuyen WAV tam -> MP3 1 lan.
        # Chi ghi 1 dong loi ngan ra giao dien khi gap su co; log chi
        # tiet ffmpeg chi ghi vao file ffmpeg-loi.log trong thu muc
        # ket qua (khong hien tab log dai nhay lien tuc len man hinh).
        tong_ms_gop = 0
        if can_gop and gop is not None and gop.so_cau > 0:
            self._log("Đang hoàn tất file lồng tiếng: %s" % dich_gop)
            try:
                ok_gop, tong_ms_gop = gop.hoan_tat(ffmpeg)
                if ok_gop:
                    self.file_gop = dich_gop
                    self._log("XONG file gộp: %s (dài %.1fs, %d câu bị "
                              "tràn slot, %d câu lỗi đã bỏ qua)"
                              % (dich_gop, tong_ms_gop / 1000.0,
                                 gop.tran_slot, gop.bo_qua))
                else:
                    self._log("LỖI hoàn tất file gộp (xem chi tiết trong "
                              "file ffmpeg-loi.log ở thư mục kết quả).")
                    _ghi_log_loi_ffmpeg(thu_muc, "hoan_tat tra ve False")
            except Exception as e:
                _ghi_log_loi_ffmpeg(thu_muc, traceback.format_exc())
                self._log("LỖI hoàn tất file gộp: %s (xem chi tiết trong "
                          "file ffmpeg-loi.log ở thư mục kết quả)"
                          % _tom_tat_loi(e))
        elif can_gop:
            self._log("Không có câu nào đọc xong nên không tạo file gộp.")
        # v1.3 - LUU/XOA tien trinh: con cau chua xong (huy giua chung
        # hoac loi) thi luu de bam 'Tiep tuc' doc not; xong tron ven
        # 100% thi xoa (khong con gi de tiep tuc).
        if 0 < so_xong < tong:
            try:
                st = os.stat(srt)
                _luu_tien_trinh(thu_muc, {
                    "srt": srt,
                    "srt_kich_thuoc": st.st_size,
                    "srt_mtime": int(st.st_mtime),
                    "tong_cau": tong,
                    "cau_da_xong": sorted(cau_da_xong),
                    "file_gop": dich_gop,
                    "che_do": che_do,
                    "giong": ts["giong_hien_thi"],
                    "toc_do": float(toc_do),
                    # v1.4: toc do toi da + bat/tat tu dong + toc do thuc
                    # tung cau da xong (de Tiep tuc noi dung toc do).
                    "toc_do_toi_da": float(toc_do_toi_da),
                    "tu_dong_toc_do": bool(tu_dong_toc_do),
                    "toc_do_cau": {str(k): float(v)
                                   for k, v in toc_do_cau.items()},
                    "cao_do": int(cao_do),
                    "thu_muc": thu_muc,
                    "thu_muc_rieng": thu_muc_rieng,
                })
                self._log("Đã lưu tiến trình (xong %d/%d câu) - bấm "
                          "'Tiếp tục' để đọc nốt các câu còn lại."
                          % (so_xong, tong))
            except Exception:
                pass
        else:
            _xoa_tien_trinh(thu_muc)
        # Bao ro ket qua: duong dan + do dai file MP3 long tieng.
        if dich_gop and os.path.isfile(dich_gop):
            if da_huy:
                ket_qua = ("ĐÃ HỦY ở câu %d/%d. Đã xong %d/%d câu. File MP3 "
                           "lồng tiếng (dang dở, chỉ có các câu đã xong):"
                           "\n%s\nĐộ dài: %.1f giây."
                           % (cau_dung, tong, so_xong, tong,
                              dich_gop, tong_ms_gop / 1000.0))
            else:
                ket_qua = ("HOÀN TẤT: %d/%d câu. File MP3 lồng tiếng:\n%s\n"
                           "Độ dài: %.1f giây."
                           % (so_xong, tong, dich_gop, tong_ms_gop / 1000.0))
            if loi_cau:
                ket_qua += " (còn %d câu lỗi: %s)" % (len(loi_cau),
                                                      sorted(loi_cau))
            self.hang_doi.put(("ket_qua", ket_qua))
            self._log(ket_qua)
        elif che_do == "rieng":
            if da_huy:
                ket_qua = ("ĐÃ HỦY ở câu %d/%d. Đã xong %d/%d câu. File "
                           "từng câu đã xong nằm trong:\n%s"
                           % (cau_dung, tong, so_xong, tong, thu_muc_rieng))
            else:
                ket_qua = ("HOÀN TẤT: %d/%d câu. File từng câu nằm trong:\n%s"
                           % (so_xong, tong, thu_muc_rieng))
            self.hang_doi.put(("ket_qua", ket_qua))
            self._log(ket_qua)
        elif da_huy:
            ket_qua = ("ĐÃ HỦY ở câu %d/%d. Chưa xong câu nào."
                       % (cau_dung, tong))
            self.hang_doi.put(("ket_qua", ket_qua))
            self._log(ket_qua)
        self._log("Thư mục kết quả: %s (bấm 'Mở thư mục kết quả' để xem)"
                  % thu_muc)
        self.hang_doi.put(("xong",))

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
