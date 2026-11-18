# SRT Reader HoaiMy

Tool đọc file phụ đề SRT thành giọng nói tiếng Việt bằng Microsoft Edge TTS
(giọng **HoaiMy** nữ / **NamMinh** nam) hoặc bằng **giọng máy (cũ)** — giọng
tiếng Việt có sẵn trên máy Windows (SAPI, ví dụ Microsoft An, để so sánh
chất giọng với HoaiMy trước khi quyết định dùng giọng nào). **Không cần API
key** — giọng HoaiMy/NamMinh dùng dịch vụ Edge TTS miễn phí của Microsoft
(`speech.platform.bing.com`).

File nguồn: `SRT-Reader-HoaiMy.py`. Chạy trực tiếp file
`SRT-Reader-HoaiMy.exe` (build từ GitHub Actions, Windows), không cần cài đặt.

## Cách dùng

1. Bấm **Chọn...** ở dòng File SRT, chọn file `.srt` cần đọc — danh sách
   câu + thời gian bắt đầu/kết thúc hiện ngay bên dưới, để anh kiểm tra
   trước khi xuất.
2. Chọn giọng đọc: **HoaiMy (nữ)** mặc định, **NamMinh (nam)**, hoặc
   **Giọng máy (cũ)** (giọng tiếng Việt có sẵn trên máy Windows).
3. Chỉnh **Tốc độ** dạng hệ số nhân **0.5x đến 2.0x** (mặc định **1.00x**,
   giống trang web test — ví dụ chỉnh lên **1.35x**) và **Cao độ**
   (-20Hz đến +20Hz) nếu cần. Tốc độ lưu trong `config.json` dạng hệ số
   nhân; config cũ (lưu dạng phần trăm, ví dụ +9%) tự đổi sang 1.09x.
   - **Tự động chỉnh tốc độ từng câu** (mặc định **BẬT**): trong file SRT
     có câu dài cần đọc nhanh mới kịp slot, có câu ngắn đọc đúng nhịp là
     đủ — giống cách iContent làm tốc độ riêng từng câu (câu 2 = 1.60x,
     câu 4 = 1.00x...). Khi bật, tool **đo thời lượng thật** của từng câu
     sau khi đọc ở tốc độ cơ bản, rồi dùng **ffmpeg atempo** tăng tốc
     file đó cho vừa slot (không gọi lại API giọng) — tốc độ thực của
     từng câu hiện trong cột Trạng thái (ví dụ `Xong (1.60x)`).
     **Tốc độ tối đa** mặc định **1.35x** (chỉnh được 1.00x–2.00x): câu
     nào cần nhanh hơn mức này thì vẫn chỉ đọc ở tốc độ tối đa, tool ghi
     cảnh báo vào nhật ký "Câu X đọc hết Ys nhưng slot chỉ có Zs (tràn
     sang câu sau)". Tắt checkbox thì mọi câu đọc đúng tốc độ cơ bản đã
     chọn (hành vi cũ).
4. Chọn đầu ra (mặc định là **Gộp 1 file lồng tiếng**):
   - **Gộp 1 file lồng tiếng (MP3)**: 1 file duy nhất, mỗi câu nằm đúng mốc
     thời gian trong SRT (khoảng trống giữa các câu là im lặng) — dùng làm
     track lồng tiếng, ghép vào video là khớp.
   - **Từng câu riêng (MP3)**: mỗi câu phụ đề thành 1 file `001.mp3`, `002.mp3`...
   - **Cả hai**: làm cả 2 loại trên.
5. Bấm nút **XUẤT MP3 LỒNG TIẾNG** (nút chính). Tiến độ hiện theo từng câu
   (câu mấy / tổng mấy câu), trạng thái từng câu hiện ngay trong danh sách
   (Chờ / Đang đọc... / Xong / Lỗi). Câu nào lỗi sẽ được **thử lại 1 lượt**
   nữa rồi mới ghi lỗi rõ lý do vào nhật ký — không lặng lẽ bỏ qua.
   - Trong lúc đang xuất, các nút **Kiểm tra kết nối giọng**, **Kiểm tra
     cập nhật** và 2 nút **Chọn...** đều mờ đi (không bấm được) để tránh
     2 việc cùng gọi giọng 1 lúc gây xung đột — chỉ nút **Hủy** sáng.
   - Bấm **Hủy** thì tool dừng sau câu đang đọc, **vẫn lưu** các câu đã
     xong (file từng câu + file lồng tiếng dở có đủ các câu đã xong),
     báo rõ "Đã hủy ở câu X/100", và lưu tiến trình vào `tien-trinh.json`.
   - Nút **Tiếp tục** (chỉ sáng khi có tiến trình dở dang đã lưu, đúng
     file SRT + đúng giọng/tốc độ/cao độ/chế độ): bấm là đọc tiếp từ câu
     chưa xong và **nối vào file cũ** — không đọc lại các câu đã xong,
     không tạo file mới. Đổi file SRT khác hoặc đổi giọng/tốc độ/cao độ
     thì tiến trình cũ không còn hợp lệ, nút mờ đi.
   - Nút **Sub lại từ đầu**: đọc lại từ câu 1, tạo file MP3 mới (thư mục
     mới tên `(1)`, `(2)`... nếu file cũ đã có — không ghi đè file cũ).
6. Xuất xong, tool báo rõ **đường dẫn file MP3 + độ dài** ở dòng kết quả
   và trong nhật ký; bấm **Mở thư mục kết quả** để xem file.
7. Nút **▶ Nghe thử** (kèm ô gõ văn bản ngắn): gõ 1 đoạn văn ngắn, hoặc
   để trống rồi chọn 1 câu trong danh sách, bấm là tool đọc câu đó và
   **phát tiếng ra loa ngay trong tool** (không tạo file MP3, không mở
   trình phát ngoài) — để test chất giọng trước khi xuất cả file dài.
   Nút **Dừng** dừng nghe thử giữa chừng. Giọng máy thì đọc thẳng ra loa;
   giọng HoaiMy/NamMinh thì đọc ra file tạm rồi phát trong tool, xong
   tự xóa file tạm.
8. Nút **Kiểm tra kết nối giọng** đọc thử 1 câu mẫu để kiểm tra mạng tới
   Microsoft trước khi chạy file dài (giọng máy thì đọc thử ra loa luôn,
   không cần mạng).
9. Nút **Kiểm tra cập nhật**: khi có bản mới trên GitHub Releases, tool
   hỏi rồi tự tải exe mới về và vá lên (không cần tải tay, giữ nguyên
   cài đặt). Repo này là public nên không cần token GitHub. Trước khi
   thay, tool **kiểm chứng file mới** (kích thước khớp với Release,
   header PE, có `python311.dll` nhúng trong file) — file lỗi/thiếu thì
   báo lỗi rõ ràng và **giữ nguyên tool cũ** (không thay, không hỏng).
   Script cập nhật đợi file tải xong thật mới thay, và **sao lưu exe cũ
   thành `.bak`** để khôi phục nếu bản mới lỗi.

Kết quả lưu vào `<Thư mục lưu>\<tên file SRT>\` (mặc định
`Desktop\SRT-HoaiMy\`). Cài đặt (giọng, tốc độ, cao độ, thư mục lưu, chế độ)
lưu vào `config.json` cạnh file exe, mở lại tool vẫn giữ nguyên.

## Vì sao tool đọc từng câu riêng rồi mới gộp?

API giọng Microsoft (edge-tts) chỉ nhận **1 đoạn văn mỗi lần gọi** — không
gọi 1 lần cho cả 100 câu được — nên tool phải đọc từng câu riêng, rồi mới
ghép các câu lại đúng mốc thời gian SRT thành **1 file lồng tiếng duy nhất**.
Từ v1.3, tool **ghép dần**: mỗi câu đọc xong là ghép ngay câu đó vào file
lồng tiếng đang tạo (đúng timestamp của nó, chỗ chưa tới thì để lặng),
không đợi đến cuối mới gộp 1 lần. Nhờ vậy: hủy giữa chừng hay lỗi giữa
chừng thì file gộp vẫn có sẵn các câu đã xong (không mất trắng); 1 câu lỗi
không làm hỏng cả file gộp (chỉ để lặng ở slot của nó rồi đi tiếp); mở
file gộp ra nghe thử được ngay cả khi chưa chạy xong.

## Lưu ý

- Cần mạng mở tới Microsoft (`speech.platform.bing.com`). Nếu mạng chặn,
  tool tự thử lại 3 lần, lần 2 trở đi bỏ qua xác minh chứng chỉ SSL
  (giống cách sửa lỗi SSL của Chipchipdownload v6.3) rồi mới báo lỗi.
  Từ v1.2, tool tự chuyển sang máy chủ giọng phụ `api.msedgeservices.com`
  khi máy chủ gốc từ chối (403 / ngắt không trả audio / 429).
- Chế độ gộp cần **ffmpeg** (tìm trong PATH hoặc đặt `ffmpeg.exe` cạnh tool).
  Trên máy CYAN đã có sẵn ở `C:\iContent\ffmpeg\bin`. Giọng máy xuất MP3
  cũng cần ffmpeg (chuyển WAV sang MP3).
- Câu nào đọc hết dài hơn slot thời gian của nó trong SRT sẽ bị tràn —
  tool ghi cảnh báo vào nhật ký, phần tràn sẽ bị cắt khi câu sau bắt đầu.
  Muốn hết tràn thì tăng **Tốc độ tối đa** (mặc định 1.35x, tối đa 2.00x)
  hoặc nới thời gian trong file SRT. Khi **Tự động chỉnh tốc độ từng
  câu** đang bật, tool tự tăng tốc từng câu dài cho vừa slot (dùng ffmpeg
  atempo, không gọi lại API giọng) — chỉ câu nào nhanh hơn cả tốc độ tối
  đa vẫn không kịp mới bị tràn và ghi cảnh báo "tràn sang câu sau".
  Tốc độ thực của từng câu hiện trong cột Trạng thái (ví dụ `Xong
  (1.60x)`).
- Câu lỗi (không tạo được audio): tool **không tạo file MP3 lỗi** cho câu
  đó; khi gộp thì **bỏ qua câu lỗi** (để khoảng lặng đúng độ dài slot của
  nó), các câu khác vẫn gộp bình thường, và ghi rõ vào nhật ký
  "Đã bỏ qua câu X (không có audio)". Khi gộp gặp sự cố, tool chỉ hiện
  1 dòng lỗi ngắn gọn ra giao diện — log chi tiết của ffmpeg chỉ ghi vào
  file `ffmpeg-loi.log` trong thư mục kết quả, không hiện lên màn hình.
- Câu dài quá 500 ký tự sẽ tự tách nhỏ ra đọc rồi nối lại.
- Giọng máy chỉ dùng được trên **Windows** (dùng PowerShell + System.Speech
  có sẵn trong máy, không cần cài thêm gì). Trên máy khác, chọn HoaiMy
  hoặc NamMinh để xuất.

## Chạy từ source (Windows)

```
pip install edge-tts pydub
python SRT-Reader-HoaiMy.py
```

## Cập nhật

Bản mới phát hành qua GitHub Releases của repo này (tag `vX.Y`).
File `version.json` ghi phiên bản hiện tại. Trong tool, bấm nút
**Kiểm tra cập nhật** là tự lên bản mới nhất (tải exe về, kiểm chứng file,
thay exe cũ, mở lại tool) — không cần tải tay.
