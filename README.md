# SRT Reader HoaiMy

Tool đọc file phụ đề SRT thành giọng nói tiếng Việt bằng Microsoft Edge TTS
(giọng **HoaiMy** nữ / **NamMinh** nam). **Không cần API key** — dùng dịch vụ
Edge TTS miễn phí của Microsoft (`speech.platform.bing.com`).

File nguồn: `SRT-Reader-HoaiMy.py`. Chạy trực tiếp file
`SRT-Reader-HoaiMy.exe` (build từ GitHub Actions, Windows), không cần cài đặt.

## Cách dùng

1. Bấm **Chọn...** ở dòng File SRT, chọn file `.srt` cần đọc — danh sách
   câu + thời gian bắt đầu/kết thúc hiện ngay bên dưới, để anh kiểm tra
   trước khi xuất.
2. Chọn giọng đọc: **HoaiMy (nữ)** mặc định, hoặc **NamMinh (nam)**.
3. Chỉnh **Tốc độ** (-50% đến +50%) và **Cao độ** (-20Hz đến +20Hz) nếu cần.
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
6. Xuất xong, tool báo rõ **đường dẫn file MP3 + độ dài** ở dòng kết quả
   và trong nhật ký; bấm **Mở thư mục kết quả** để xem file.
7. Nút **Kiểm tra kết nối giọng** đọc thử 1 câu mẫu để kiểm tra mạng tới
   Microsoft trước khi chạy file dài.
8. Nút **Kiểm tra cập nhật**: khi có bản mới trên GitHub Releases, tool
   hỏi rồi tự tải exe mới về và vá lên (không cần tải tay, giữ nguyên
   cài đặt). Repo này là public nên không cần token GitHub.

Kết quả lưu vào `<Thư mục lưu>\<tên file SRT>\` (mặc định
`Desktop\SRT-HoaiMy\`). Cài đặt (giọng, tốc độ, cao độ, thư mục lưu, chế độ)
lưu vào `config.json` cạnh file exe, mở lại tool vẫn giữ nguyên.

## Lưu ý

- Cần mạng mở tới Microsoft (`speech.platform.bing.com`). Nếu mạng chặn,
  tool tự thử lại 3 lần, lần 2 trở đi bỏ qua xác minh chứng chỉ SSL
  (giống cách sửa lỗi SSL của Chipchipdownload v6.3) rồi mới báo lỗi.
- Chế độ gộp cần **ffmpeg** (tìm trong PATH hoặc đặt `ffmpeg.exe` cạnh tool).
  Trên máy CYAN đã có sẵn ở `C:\iContent\ffmpeg\bin`.
- Câu nào đọc hết dài hơn slot thời gian của nó trong SRT sẽ bị tràn sang
  câu sau — tool ghi cảnh báo vào nhật ký. Muốn hết tràn thì tăng tốc độ đọc
  hoặc nới thời gian trong file SRT.
- Câu dài quá 500 ký tự sẽ tự tách nhỏ ra đọc rồi nối lại.

## Chạy từ source (Windows)

```
pip install edge-tts pydub
python SRT-Reader-HoaiMy.py
```

## Cập nhật

Bản mới phát hành qua GitHub Releases của repo này (tag `vX.Y`).
File `version.json` ghi phiên bản hiện tại. Trong tool, bấm nút
**Kiểm tra cập nhật** là tự lên bản mới nhất (tải exe về, thay exe cũ,
mở lại tool) — không cần tải tay.
