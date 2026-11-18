# -*- coding: utf-8 -*-
"""
SRT Reader HoaiMy - Doc file phu de SRT bang giong Microsoft Edge TTS.
Giong: HoaiMy (nu, vi-VN-HoaiMyNeural) mac dinh, NamMinh (nam, vi-VN-NamMinhNeural).
Khong can API key: dung dich vu Edge TTS mien phi (speech.platform.bing.com).
Dau ra: tung cau rieng (MP3) va/hoac 1 file gop dat dung moc thoi gian SRT (dub track).
Phien ban: 1.0
"""
import asyncio
import json
import os
import re
import ssl
import sys
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "SRT Reader HoaiMy"
VERSION = "1.0"
GITHUB_REPO = "Cyandeptrai/srt-reader-hoaimy"

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
        "che_do": "ca_hai",
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
        self.che_do = tk.StringVar(value=self.cfg.get("che_do", "ca_hai"))
        tk.Radiobutton(f3, text="Từng câu riêng (MP3)",
                       variable=self.che_do, value="rieng").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(f3, text="Gộp 1 file lồng tiếng (MP3)",
                       variable=self.che_do, value="gop").grid(row=0, column=2, sticky="w")
        tk.Radiobutton(f3, text="Cả hai",
                       variable=self.che_do, value="ca_hai").grid(row=0, column=3, sticky="w")

        f4 = tk.Frame(self)
        f4.pack(fill="x", **pad)
        self.btn_bat_dau = tk.Button(f4, text="BẮT ĐẦU ĐỌC", command=self._bat_dau)
        self.btn_bat_dau.pack(side="left", padx=4)
        tk.Button(f4, text="Kiểm tra kết nối giọng",
                  command=self._kiem_tra_giong).pack(side="left", padx=4)
        tk.Button(f4, text="Mở thư mục lưu",
                  command=self._mo_thu_muc_luu).pack(side="left", padx=4)

        self.lb_tien_trinh = tk.Label(self, text="Chưa chạy.")
        self.lb_tien_trinh.pack(fill="x", padx=8)
        self.thanh_tien_trinh = ttk.Progressbar(self, orient="horizontal",
                                                mode="determinate")
        self.thanh_tien_trinh.pack(fill="x", padx=8, pady=4)

        tk.Label(self, text="Nhật ký:").pack(anchor="w", padx=8)
        self.txt_log = tk.Text(self, height=16, wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=4)
        sb = tk.Scrollbar(self.txt_log, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)

    # ----- chon file -----
    def _chon_srt(self):
        p = filedialog.askopenfilename(filetypes=[("Phụ đề SRT", "*.srt"),
                                                 ("Mọi file", "*.*")])
        if p:
            self.e_srt.delete(0, "end")
            self.e_srt.insert(0, p)

    def _chon_thu_muc(self):
        p = filedialog.askdirectory()
        if p:
            self.e_luu.delete(0, "end")
            self.e_luu.insert(0, p)

    def _mo_thu_muc_luu(self):
        p = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        if os.path.isdir(p):
            if sys.platform.startswith("win"):
                os.startfile(p)
            else:
                messagebox.showinfo(APP_TITLE, "Thư mục lưu:\n" + p)
        else:
            messagebox.showinfo(APP_TITLE, "Chưa có thư mục lưu:\n" + p)

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
        self.dang_chay = True
        self.btn_bat_dau.configure(state="disabled")
        threading.Thread(target=self._chay_kiem_tra, daemon=True).start()

    def _chay_kiem_tra(self):
        voice = GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH])
        self._log("Kiểm tra giọng %s (%s)..." % (self.cb_giong.get(), voice))
        thu_muc = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        try:
            os.makedirs(thu_muc, exist_ok=True)
        except OSError as e:
            self._log("Lỗi tạo thư mục: %s" % e)
            self.hang_doi.put(("xong",))
            return
        dich = os.path.join(thu_muc, "doc-thu.mp3")
        ok, bo_xac_minh, loi = doc_thanh_mp3(
            MAU_DOC_THU, voice, int(self.sl_toc_do.get()),
            int(self.sl_cao_do.get()), dich, log_cb=self._log)
        if ok:
            self._log("OK! Đã tạo file đọc thử: %s%s" % (
                dich, " (đã dùng chế độ bỏ xác minh SSL)" if bo_xac_minh else ""))
        else:
            self._log("LỖI: không tạo được giọng. %s" % loi)
            self._log("Kiểm tra mạng rồi bấm lại. Giọng lấy từ "
                      "speech.platform.bing.com, cần mạng mở tới Microsoft.")
        self.hang_doi.put(("xong",))

    # ----- chay chinh -----
    def _bat_dau(self):
        if self.dang_chay:
            return
        srt = self.e_srt.get().strip()
        if not srt or not os.path.isfile(srt):
            messagebox.showwarning(APP_TITLE, "Hãy chọn file SRT trước.")
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
        self.dang_chay = True
        self.btn_bat_dau.configure(state="disabled")
        threading.Thread(target=self._chay, args=(srt, ffmpeg), daemon=True).start()

    def _chay(self, srt, ffmpeg):
        from pydub import AudioSegment
        if ffmpeg:
            AudioSegment.converter = ffmpeg
        voice = GIONG.get(self.cb_giong.get(), GIONG[GIONG_MAC_DINH])
        toc_do = int(self.sl_toc_do.get())
        cao_do = int(self.sl_cao_do.get())
        che_do = self.che_do.get()
        thu_muc_goc = self.e_luu.get().strip() or mac_dinh_thu_muc_luu()
        ten_goc = os.path.splitext(os.path.basename(srt))[0]
        thu_muc = os.path.join(thu_muc_goc, ten_goc)
        thu_muc_rieng = os.path.join(thu_muc, "tung-cau")
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
                  % (tong, self.cb_giong.get(), voice,
                     _dinh_dang_toc_do(toc_do), _dinh_dang_cao_do(cao_do)))
        self._log("Thư mục lưu: %s" % thu_muc)
        loi_cau = []
        can_gop = che_do in ("gop", "ca_hai")
        for i, cau in enumerate(cac_cau, 1):
            dich = os.path.join(thu_muc_rieng, "%03d.mp3" % cau["chi_so"])
            # Luon doc tung cau (phuc vu ca 2 che do); file rieng giu lai de doi chieu.
            self._tien_trinh(int((i - 1) * 100 / tong),
                             "Đang đọc câu %d/%d..." % (i, tong))
            self._log("Câu %d/%d (%.1fs): %s" % (
                i, tong, (cau["ket_thuc_ms"] - cau["bat_dau_ms"]) / 1000.0,
                cau["text"][:80]))
            ok, bo_xac_minh, loi = doc_thanh_mp3(
                cau["text"], voice, toc_do, cao_do, dich, log_cb=self._log)
            if not ok:
                loi_cau.append(cau["chi_so"])
                self._log("  -> LỖI câu %d: %s" % (cau["chi_so"], loi))
            elif bo_xac_minh:
                self._log("  -> Xong (đã dùng chế độ bỏ xác minh SSL)")
        self._tien_trinh(100, "Đã đọc xong %d/%d câu." % (tong - len(loi_cau), tong))
        if loi_cau:
            self._log("Cảnh báo: %d câu lỗi: %s" % (len(loi_cau), loi_cau))
        if can_gop:
            dich_gop = os.path.join(thu_muc, ten_goc + "_long-tieng.mp3")
            self._log("Đang gộp thành 1 file lồng tiếng: %s" % dich_gop)
            try:
                ok, tong_ms, canh_bao = gop_long_tieng(
                    cac_cau, thu_muc_rieng, dich_gop, log_cb=self._log)
                if ok:
                    self._log("XONG file gộp: %s (dài %.1fs, %d câu bị tràn slot)"
                              % (dich_gop, tong_ms / 1000.0, canh_bao))
                else:
                    self._log("LỖI gộp file.")
            except Exception as e:
                self._log("LỖI gộp file: %s" % e)
        self._log("HOÀN TẤT. Thư mục kết quả: %s" % thu_muc)
        self.hang_doi.put(("xong",))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
