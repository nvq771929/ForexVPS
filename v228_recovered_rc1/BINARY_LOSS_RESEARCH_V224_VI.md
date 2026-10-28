> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# V2.24 — nghiên cứu nguyên nhân thua Binary Option

## Phạm vi

Đây là công cụ đọc dữ liệu, không thay đổi quyết định EA. Tách ba điều:

1. **Sự kiện xác minh được:** giá BID ở biên vào/hết hạn, LOCK, hủy native,
   MFE/MAE và thời điểm nhịp thuận/bất lợi trên tick đã ghi.
2. **Liên hệ thống kê:** chiến lược, bối cảnh, phiên, momentum, xác nhận,
   khoảng trống tới vùng đích. Phải so sánh cả WIN và LOSS.
3. **Nguyên nhân và thay đổi có hiệu quả:** cần replay chính sách đã cố định,
   mẫu độc lập và demo forward. Một liên hệ chưa chứng minh được điều này.

Không dùng dữ liệu Binary để khẳng định nguyên nhân thua Forex. Forex V222
được giữ nguyên, kể cả quản lý rủi ro/thoát lệnh/bình quân giá.

## Chạy trên dữ liệu V219 hiện có

Cài Python dependencies bằng `Install-Demo-Learning.cmd` nếu chưa có, rồi chạy:

```bat
Review-Binary-Losses.cmd --source "D:\Research\v219_sessions_6m_p1_TESTER_EURUSD" --development-end-exclusive 2026-01-15 --broker-utc-offset-minutes 0
```

Thay đường dẫn bằng **bản sao Tester đã hoàn tất**, có `tester_complete.csv`,
BIN, sổ `manual_v218_*` và input CSV gốc. Không dùng thư mục Forex hoặc journal
đang thay đổi. Nếu MT4 vẫn chạy, dùng bản sao đã chụp khi dừng ghi dữ liệu.

Biên phát triển là ngày broker, loại trừ từ 00:00 ngày đó. Chốt biên trước khi
xem kết quả; không di chuyển biên để làm đẹp số liệu. Chỉ truyền offset khi đã
xác minh cho toàn kỳ; thiếu offset thì `SESSION_UNKNOWN`. Với bộ đã xác nhận
UTC+0 01/10/2025–27/03/2026 dùng 0 như ví dụ. Không lấy TimeGMT hiện tại để
gắn phiên cho lịch sử.

Công cụ xác minh snapshot native, sổ manual so với LOCK/BIN và quote biên,
định danh/sequence/clock input, hash đúng byte đọc và độ ổn định nguồn. CSV
input chỉ là quan sát cục bộ, không phải chứng thực feed độc lập. Không tự
điền tick thiếu. Công cụ có thể mất thời gian đọc toàn bộ journal.

## Kết quả

`binary_loss_review_v224.zip` chứa:

- `signals.csv/json`: từng tín hiệu, dữ liệu `lock_*` có trước entry; dữ liệu
  `expost_*` chỉ dành cho giải thích sau khi đã biết kết quả.
- `strata.csv`: đối chiếu WIN/LOSS theo chiến lược, regime, phiên, tháng/hướng.
- `hypotheses.json`: 7 giả thuyết định trước, so sánh trong cùng chiến lược/
  phiên, khoảng tham khảo bootstrap theo ngày. Không tự chọn bộ lọc giao dịch.
- `summary.json`: định danh nguồn, mốc phát triển, bằng chứng thiếu, kết luận.

`expost_first_favourable_second` là lần đầu có giá thuận **ít nhất 1 point**
so với entry; không có nghĩa cả phút đầu đi thuận. `expost_final_below_entry_second`
là lúc bắt đầu đoạn cuối cùng luôn ở phía bất lợi; không có nghĩa thị trường
đã đảo xu hướng cấu trúc. Đồng hồ tính từ tick entry thực sự được ghi.

Các quan sát cuối phút dùng tick đã có, không nội suy. MFE/MAE chỉ là cực trị
trên đường giá quan sát. Không dùng MFE, thời điểm hồi hoặc nhãn 10/15 phút
làm đầu vào dự báo. Kỳ hạn 10/15 phút là chẩn đoán hồi cứu theo cùng entry,
không phải replay danh mục khả thi: occupancy và lựa chọn tín hiệu có thể đổi.

## Quyết định hiện tại

Bộ phát triển có 139 tín hiệu, 66 WIN/73 LOSS. Mẫu nhỏ hơn tiêu chuẩn train
400 kết quả quyết định; không hạ tiêu chuẩn để fit/activate một bộ lọc.
Các giả thuyết hiện chưa chứng minh được một điều kiện loại lỗ đáng tin cậy.
Thử tăng kỳ hạn hoặc hạ ATR phải kiểm tra cả lợi ích lẫn số WIN bị mất, và
không suy diễn lợi nhuận Olymp từ kết quả BID MT4.

Số liệu và chẩn đoán đầy đủ của lượt hiện tại nằm trong gói nghiên cứu riêng.
Không có bản nâng cấp chiến lược đã kiểm định để yêu cầu thay EA đang dùng.
