# -*- coding: utf-8 -*-
"""
SRT Reader HoaiMy - Doc file phu de SRT bang giong Microsoft Edge TTS.
Giong: HoaiMy (nu, vi-VN-HoaiMyNeural) mac dinh, NamMinh (nam, vi-VN-NamMinhNeural).
Khong can API key: dung dich vu Edge TTS mien phi (speech.platform.bing.com).
Dau ra: tung cau rieng (MP3) va/hoac 1 file gop dat dung moc thoi gian SRT (dub track).
Phien ban: 1.1 (them tu cap nhat giong Chipchipdownload v6.2)
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
import queue
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "SRT Reader HoaiMy"
VERSION = "1.1"
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

GIONG = {
    "HoaiMy (nữ)": "vi-VN-HoaiMyNeural",
    "NamMinh (nam)": "vi-VN-NamMinhNeural",
}
GIONG_MAC_DINH = "HoaiMy (nữ)"
MAU_DOC_THU = "Xin chào, đây là giọng đọc thử của HoaiMy."
SO_LAN_THU_TOI_DA = 3
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
        "toc_do": 0,
        "cao_do": 0,
        "thu_muc_luu": mac_dinh_thu_muc_luu(),
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


def kiem_tra_cap_nhat():
    """Kiem tra ban moi tren GitHub. Tra ve dict:
    {version_moi, tag, tai_url, ten_file} hoac None neu da la ban moi nhat.
    Uu tien doc GitHub Releases (latest); neu API loi thi doc version.json
    raw tren main. Raise RuntimeError neu khong doc duoc.
    Repo public nen KHONG can token."""
    # 1) Thu Releases/latest.
    try:
        data = goi_github_api(GITHUB_API_LATEST_RELEASE)
        tag = (data.get("tag_name") or "").strip()
        if tag and so_sanh_version(tag, VERSION) > 0:
            tai_url = None
            ten_file = None
            for asset in data.get("assets") or []:
                if (asset.get("name") or "") == EXE_TEN:
                    # Link tai truc tiep, khong can auth (repo public).
                    tai_url = asset.get("browser_download_url")
                    ten_file = asset.get("name")
                    break
            return {"version_moi": tag.lstrip("vV"), "tag": tag,
                    "tai_url": tai_url, "ten_file": ten_file}
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
                    "tai_url": None, "ten_file": None}
        return None
    except Exception as e:
        raise RuntimeError("Khong doc duoc version tren GitHub: %s" % e)


def tai_ban_moi_va_cap_nhat(tai_url, log_cb=None):
    """Tai exe ban moi ve file tam <exe>.new, kiem chung dinh dang PE, ghi
    script cap nhat (capnhat.bat) roi tra ve duong dan script. Script cho
    tool thoat (file exe het bi khoa) roi thay exe cu bang exe moi va mo lai
    tool. Nguoi goi phai thoat tool ngay sau khi chay script nay."""
    exe_hien_tai = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None
    if not exe_hien_tai:
        raise RuntimeError("Dang chay dang ma nguon (.py), khong tu va exe duoc. "
                           "Hay dung ban .exe da cai.")
    thu_muc = os.path.dirname(exe_hien_tai)
    ten_exe = os.path.basename(exe_hien_tai)
    file_moi = os.path.join(thu_muc, ten_exe + ".new")
    if log_cb:
        log_cb("Dang tai ban moi ve...")
    tai_file_qua_url(tai_url, file_moi, 600, log_cb, "ban moi",
                     headers={"Accept": "application/octet-stream"})
    if not os.path.isfile(file_moi) or os.path.getsize(file_moi) < 1000000:
        _xoa_file_quiet(file_moi)
        raise RuntimeError("Tai ban moi ve nhung file khong hop le.")
    if not kiem_chung_pe(file_moi):
        _xoa_file_quiet(file_moi)
        raise RuntimeError("File tai ve khong phai exe Windows hop le "
                           "(co the la trang loi). Da xoa file hong.")
    bat_path = os.path.join(thu_muc, "capnhat.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\r\n")
        f.write("chcp 65001 >nul\r\n")
        f.write(":cho\r\n")
        f.write("ping -n 2 127.0.0.1 >nul\r\n")
        f.write('move /y "%s" "%s" >nul 2>&1\r\n' % (file_moi, exe_hien_tai))
        f.write("if errorlevel 1 goto cho\r\n")
        f.write('start "" "%s"\r\n' % exe_hien_tai)
        f.write('del "%%~f0"\r\n')
    return bat_path


def _dinh_dang_toc_do(phan_tram):
    return ("+" if phan_tram >= 0 else "") + str(int(phan_tram)) + "%"


def _dinh_dang_cao_do(hz):
    return ("+" if hz >= 0 else "") + str(int(hz)) + "Hz"


def _tao_connector(bo_xac_minh):
    if not bo_xac_minh:
        return None
    import aiohttp
    ctx = ssl._create_unverified_context()
    return aiohttp.TCPConnector(ssl=ctx)


async def _doc_mot_doan(text, voice, toc_do, cao_do, duong_dan_ra, bo_xac_minh):
    import edge_tts
    comm = edge_tts.Communicate(
        text, voice,
        rate=_dinh_dang_toc_do(toc_do),
        pitch=_dinh_dang_cao_do(cao_do),
        connector=_tao_connector(bo_xac_minh),
    )
    await comm.save(duong_dan_ra)


def doc_thanh_mp3(text, voice, toc_do, cao_do, duong_dan_ra, log_cb=None):
    """Doc 1 cau thanh file MP3. Thu toi da 3 lan, fallback bo xac minh SSL
    khi gap loi chung chi (giong cach sua loi SSL cua Chipchipdownload v6.3).
    Tra ve (thanh_cong, da_dung_bo_xac_minh, thong_bao_loi)."""
    doan_list = tach_cau_dai(text)
    if len(doan_list) == 1:
        for lan in range(1, SO_LAN_THU_TOI_DA + 1):
            bo_xac_minh = (lan >= 2)
            try:
                asyncio.run(_doc_mot_doan(text, voice, toc_do, cao_do,
                                          duong_dan_ra, bo_xac_minh))
                if os.path.isfile(duong_dan_ra) and os.path.getsize(duong_dan_ra) > 0:
                    return True, bo_xac_minh, ""
                raise RuntimeError("file am thanh rong (0 byte)")
            except Exception as e:
                if log_cb:
                    log_cb("  Thu lan %d/%d loi: %s" % (lan, SO_LAN_THU_TOI_DA, e))
                if lan < SO_LAN_THU_TOI_DA and la_loi_chung_chi_ssl(e):
                    if log_cb:
                        log_cb("  -> Thu lai bo qua xac minh chung chi SSL...")
                    continue
                if lan < SO_LAN_THU_TOI_DA:
                    continue
                return False, bo_xac_minh, str(e)
        return False, False, "khong ro loi"
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
                return False, False, "doan %d loi: %s" % (j + 1, loi)
        finally:
            try:
                os.remove(tam_path)
            except OSError:
                pass
    am_thanh.export(duong_dan_ra, format="mp3")
    return True, False, ""


# ---------------- gop file long tieng ----------------

def gop_long_tieng(cac_cau, thu_muc_am_thanh, duong_dan_ra, log_cb=None):
    """Gop cac file MP3 tung cau thanh 1 file, dat dung moc thoi gian SRT.
    cac_cau: list dict co 'chi_so','bat_dau_ms','ket_thuc_ms'.
    Tra ve (thanh_cong, thoi_luong_ms, so_cau_canh_bao)."""
    from pydub import AudioSegment
    if not cac_cau:
        return False, 0, 0
    tong_ms = max(c["ket_thuc_ms"] for c in cac_cau)
    ket_qua = AudioSegment.silent(duration=tong_ms)
    canh_bao = 0
    for c in cac_cau:
        ten = os.path.join(thu_muc_am_thanh, "%03d.mp3" % c["chi_so"])
        if not os.path.isfile(ten):
            if log_cb:
                log_cb("  Canh bao: thieu file cau %d, bo qua" % c["chi_so"])
            continue
        am = AudioSegment.from_file(ten, format="mp3")
        dai = len(am)
        cho_trong = c["ket_thuc_ms"] - c["bat_dau_ms"]
        if dai > cho_trong:
            canh_bao += 1
            if log_cb:
                log_cb("  Canh bao: cau %d doc het %.1fs nhung slot chi co %.1fs "
                       "(se lan sang cau sau)" % (c["chi_so"], dai / 1000.0,
                                                  cho_trong / 1000.0))
        ket_qua = ket_qua.overlay(am, position=c["bat_dau_ms"])
    ket_qua.export(duong_dan_ra, format="mp3")
    return True, tong_ms, canh_bao


# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE + " v" + VERSION)
        self.geometry("720x620")
        self.resizable(True, True)
        self.cfg = doc_config()
        self.hang_doi = queue.Queue()
        self.dang_chay = False
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
        tk.Button(f, text="Chọn...", command=self._chon_srt).grid(row=0, column=2)
        f.columnconfigure(1, weight=1)

        tk.Label(f, text="Thư mục lưu:").grid(row=1, column=0, sticky="w")
        self.e_luu = tk.Entry(f, width=62)
        self.e_luu.grid(row=1, column=1, sticky="we")
        self.e_luu.insert(0, self.cfg.get("thu_muc_luu", ""))
        tk.Button(f, text="Chọn...", command=self._chon_thu_muc).grid(row=1, column=2)

        f2 = tk.Frame(self)
        f2.pack(fill="x", **pad)
        tk.Label(f2, text="Giọng đọc:").grid(row=0, column=0, sticky="w")
        self.cb_giong = ttk.Combobox(f2, values=list(GIONG.keys()),
                                     state="readonly", width=22)
        self.cb_giong.set(self.cfg.get("giong", GIONG_MAC_DINH))
        self.cb_giong.grid(row=0, column=1, sticky="w", padx=4)

        tk.Label(f2, text="Tốc độ:").grid(row=1, column=0, sticky="w")
        self.sl_toc_do = tk.Scale(f2, from_=-50, to=50, orient="horizontal",
                                  length=220)
        self.sl_toc_do.set(int(self.cfg.get("toc_do", 0)))
        self.sl_toc_do.grid(row=1, column=1, sticky="w", padx=4)
        self.lb_toc_do = tk.Label(f2, text="+0%")
        self.lb_toc_do.grid(row=1, column=2, sticky="w")
        self.sl_toc_do.configure(command=lambda v: self.lb_toc_do.configure(
            text=_dinh_dang_toc_do(int(float(v)))))

        tk.Label(f2, text="Cao độ:").grid(row=2, column=0, sticky="w")
        self.sl_cao_do = tk.Scale(f2, from_=-20, to=20, orient="horizontal",
                                  length=220)
        self.sl_cao_do.set(int(self.cfg.get("cao_do", 0)))
        self.sl_cao_do.grid(row=2, column=1, sticky="w", padx=4)
        self.lb_cao_do = tk.Label(f2, text="+0Hz")
        self.lb_cao_do.grid(row=2, column=2, sticky="w")
        self.sl_cao_do.configure(command=lambda v: self.lb_cao_do.configure(
            text=_dinh_dang_cao_do(int(float(v)))))
        self.lb_toc_do.configure(text=_dinh_dang_toc_do(self.sl_toc_do.get()))
        self.lb_cao_do.configure(text=_dinh_dang_cao_do(self.sl_cao_do.get()))

        f3 = tk.Frame(self)
        f3.pack(fill="x", **pad)
        tk.Label(f3, text="Đầu ra:").grid(row=0, column=0, sticky="w")
        self.che_do = tk.StringVar(value=self.cfg.get("che_do", "gop"))
        tk.Radiobutton(f3, text="Gộp 1 file lồng tiếng (MP3)",
                       variable=self.che_do, value="gop").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(f3, text="Từng câu riêng (MP3)",
                       variable=self.che_do, value="rieng").grid(row=0, column=2, sticky="w")
        tk.Radiobutton(f3, text="Cả hai",
                       variable=self.che_do, value="ca_hai").grid(row=0, column=3, sticky="w")

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
        tk.Button(f4, text="Kiểm tra kết nối giọng",
                  command=self._kiem_tra_giong).pack(side="left", padx=4)
        tk.Button(f4, text="Kiểm tra cập nhật",
                  command=self.bam_kiem_tra_cap_nhat).pack(side="left", padx=4)
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
            return []
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
                elif muc[0] == "xong":
                    self.dang_chay = False
                    self.btn_bat_dau.configure(state="normal")
        except queue.Empty:
            pass
        self.after(200, self._xu_ly_hang_doi)

    def _luu_cai_dat_hien_tai(self):
        self.cfg.update({
            "giong": self.cb_giong.get(),
            "toc_do": int(self.sl_toc_do.get()),
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
            "toc_do": int(self.sl_toc_do.get()),
            "cao_do": int(self.sl_cao_do.get()),
            "thu_muc": self.e_luu.get().strip() or mac_dinh_thu_muc_luu(),
        }
        self.dang_chay = True
        self.btn_bat_dau.configure(state="disabled")
        threading.Thread(target=self._chay_kiem_tra, args=(ts,),
                         daemon=True).start()

    def _chay_kiem_tra(self, ts):
        voice = ts["voice"]
        self._log("Kiểm tra giọng %s (%s)..." % (ts["giong_hien_thi"], voice))
        thu_muc = ts["thu_muc"]
        try:
            os.makedirs(thu_muc, exist_ok=True)
        except OSError as e:
            self._log("Lỗi tạo thư mục: %s" % e)
            self.hang_doi.put(("xong",))
            return
        dich = os.path.join(thu_muc, "doc-thu.mp3")
        ok, bo_xac_minh, loi = doc_thanh_mp3(
            MAU_DOC_THU, voice, ts["toc_do"], ts["cao_do"], dich,
            log_cb=self._log)
        if ok:
            self._log("OK! Đã tạo file đọc thử: %s%s" % (
                dich, " (đã dùng chế độ bỏ xác minh SSL)" if bo_xac_minh else ""))
        else:
            self._log("LỖI: không tạo được giọng. %s" % loi)
            self._log("Kiểm tra mạng rồi bấm lại. Giọng lấy từ "
                      "speech.platform.bing.com, cần mạng mở tới Microsoft.")
        self.hang_doi.put(("xong",))

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
                         args=(ket_qua["tai_url"],), daemon=True).start()

    def _cap_nhat_loi(self, msg):
        self._log("Không kiểm tra được cập nhật: %s" % msg)
        messagebox.showerror(
            "Không kiểm tra được cập nhật",
            msg + "\n\nBản đang dùng: v%s.\nLấy bản mới bằng tay tại:\n%s"
            % (VERSION, GITHUB_RELEASES_URL))

    def _tai_ban_moi_worker(self, tai_url):
        try:
            bat_path = tai_ban_moi_va_cap_nhat(tai_url, log_cb=self._log)
            self.hang_doi.put(("tai_moi_xong", bat_path))
        except Exception as e:
            self.hang_doi.put(("tai_moi_loi", str(e)))

    def _tai_ban_moi_xong(self, bat_path):
        # Chay script cap nhat (cho tool thoat roi thay exe + mo lai).
        try:
            subprocess.Popen(["cmd", "/c", bat_path],
                             creationflags=subprocess.CREATE_NO_WINDOW
                             if sys.platform == "win32" else 0)
        except Exception:
            subprocess.Popen(bat_path, shell=True)
        messagebox.showinfo(
            "Đang cập nhật...",
            "Đã tải xong bản mới. Tool sẽ thoát ngay, script cập nhật sẽ "
            "thay exe cũ bằng exe mới rồi tự mở lại tool.")
        try:
            self.destroy()
        finally:
            os._exit(0)

    def _tai_ban_moi_loi(self, msg):
        self._log("Lỗi tải bản mới: %s" % msg)
        messagebox.showerror("Lỗi tải bản mới", msg)

    # ----- chay chinh -----
    def _bat_dau(self):
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
        self._luu_cai_dat_hien_tai()
        # Lay het gia tri giao dien o luong chinh, truyen sang luong worker
        # (luong worker khong doc truc tiep widget tkinter - khong an toan).
        ts = {
            "voice": GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH]),
            "giong_hien_thi": self.cb_giong.get(),
            "toc_do": int(self.sl_toc_do.get()),
            "cao_do": int(self.sl_cao_do.get()),
            "che_do": self.che_do.get(),
            "thu_muc_goc": self.e_luu.get().strip() or mac_dinh_thu_muc_luu(),
        }
        self.dang_chay = True
        self.btn_bat_dau.configure(state="disabled")
        self.hang_doi.put(("ket_qua", ""))
        threading.Thread(target=self._chay, args=(srt, ffmpeg, ts),
                         daemon=True).start()

    def _chay(self, srt, ffmpeg, ts):
        from pydub import AudioSegment
        if ffmpeg:
            AudioSegment.converter = ffmpeg
        voice = ts["voice"]
        toc_do = ts["toc_do"]
        cao_do = ts["cao_do"]
        che_do = ts["che_do"]
        thu_muc_goc = ts["thu_muc_goc"]
        ten_goc = os.path.splitext(os.path.basename(srt))[0]
        thu_muc = os.path.join(thu_muc_goc, ten_goc)
        thu_muc_rieng = os.path.join(thu_muc, "tung-cau")
        self.thu_muc_ket_qua = thu_muc
        self.file_gop = None
        try:
            os.makedirs(thu_muc_rieng, exist_ok=True)
        except OSError as e:
            self._log("Lỗi tạo thư mục: %s" % e)
            self.hang_doi.put(("xong",))
            return
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
        self._log("Thư mục lưu: %s" % thu_muc)
        for cau in cac_cau:
            self._dat_trang_thai_cau(cau["chi_so"], "Chờ")
        loi_cau = {}  # chi_so -> ly do loi
        can_gop = che_do in ("gop", "ca_hai")

        def doc_1_cau(cau, i):
            """Doc 1 cau, cap nhat tien trinh + trang thai trong danh sach.
            Tra ve True neu xong."""
            dich = os.path.join(thu_muc_rieng, "%03d.mp3" % cau["chi_so"])
            self._tien_trinh(int((i - 1) * 100 / tong),
                             "Đang đọc câu %d/%d..." % (i, tong))
            self._dat_trang_thai_cau(cau["chi_so"], "Đang đọc...")
            self._log("Câu %d/%d (%.1fs): %s" % (
                i, tong, (cau["ket_thuc_ms"] - cau["bat_dau_ms"]) / 1000.0,
                cau["text"][:80]))
            ok, bo_xac_minh, loi = doc_thanh_mp3(
                cau["text"], voice, toc_do, cao_do, dich, log_cb=self._log)
            if not ok:
                self._dat_trang_thai_cau(cau["chi_so"], "Lỗi: " + (loi or "?")[:60])
                self._log("  -> LỖI câu %d: %s" % (cau["chi_so"], loi))
                return False
            self._dat_trang_thai_cau(cau["chi_so"], "Xong")
            if bo_xac_minh:
                self._log("  -> Xong (đã dùng chế độ bỏ xác minh SSL)")
            return True

        # Luot 1: doc het cac cau.
        for i, cau in enumerate(cac_cau, 1):
            if not doc_1_cau(cau, i):
                loi_cau[cau["chi_so"]] = True
        # Luot 2: cau nao loi thi THU LAI 1 lan nua (loi mang thoang qua),
        # ghi ro ket qua tung cau, khong lang le bo qua.
        if loi_cau:
            self._log("Thử lại %d câu lỗi: %s" % (len(loi_cau),
                                                  sorted(loi_cau)))
            for i, cau in enumerate(cac_cau, 1):
                if cau["chi_so"] not in loi_cau:
                    continue
                self._log("Đọc lại câu %d..." % cau["chi_so"])
                if doc_1_cau(cau, i):
                    del loi_cau[cau["chi_so"]]
                    self._log("  -> Câu %d đọc lại THÀNH CÔNG." % cau["chi_so"])
                else:
                    self._log("  -> Câu %d vẫn lỗi sau khi thử lại." % cau["chi_so"])
        so_xong = tong - len(loi_cau)
        self._tien_trinh(100, "Đã đọc xong %d/%d câu." % (so_xong, tong))
        if loi_cau:
            self._log("Cảnh báo: %d câu vẫn lỗi sau 2 lượt: %s"
                      % (len(loi_cau), sorted(loi_cau)))
        dich_gop = None
        tong_ms_gop = 0
        if can_gop:
            dich_gop = os.path.join(thu_muc, ten_goc + "_long-tieng.mp3")
            self._log("Đang gộp thành 1 file lồng tiếng: %s" % dich_gop)
            try:
                ok, tong_ms_gop, canh_bao = gop_long_tieng(
                    cac_cau, thu_muc_rieng, dich_gop, log_cb=self._log)
                if ok:
                    self.file_gop = dich_gop
                    self._log("XONG file gộp: %s (dài %.1fs, %d câu bị tràn slot)"
                              % (dich_gop, tong_ms_gop / 1000.0, canh_bao))
                else:
                    self._log("LỖI gộp file.")
            except Exception as e:
                self._log("LỖI gộp file: %s" % e)
        # Bao ro ket qua: duong dan + do dai file MP3 long tieng.
        if dich_gop and os.path.isfile(dich_gop):
            ket_qua = ("HOÀN TẤT: %d/%d câu. File MP3 lồng tiếng:\n%s\n"
                       "Độ dài: %.1f giây."
                       % (so_xong, tong, dich_gop, tong_ms_gop / 1000.0))
            if loi_cau:
                ket_qua += " (còn %d câu lỗi: %s)" % (len(loi_cau),
                                                      sorted(loi_cau))
            self.hang_doi.put(("ket_qua", ket_qua))
            self._log(ket_qua)
        elif che_do == "rieng":
            ket_qua = ("HOÀN TẤT: %d/%d câu. File từng câu nằm trong:\n%s"
                       % (so_xong, tong, thu_muc_rieng))
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
