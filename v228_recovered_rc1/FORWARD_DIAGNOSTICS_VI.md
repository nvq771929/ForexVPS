# Thu phiên forward EURUSD M5 để chẩn đoán quote gap

Mục tiêu là kiểm tra điều kiện nhận tick trên chart live và đối chiếu với lịch sử Tester. V2.15 phát tín hiệu để anh vào Olymp Trade demo thủ công; mô phỏng kết quả bằng Bid MT4. Không có đặt lệnh tự động.

## 1. Chuẩn bị

- Cài source và F7 compile `EURUSD_M5_Intelligence_V215.mq4` theo INSTALL_V215_VI.md.
- Mở EURUSD M5 cùng broker/feed với lượt trước khi thị trường đang có tick. Không dùng symbol OTC.
- Gắn V215, Inputs → Load `EURUSD_M5_V215_Forward_Diagnostic.set` trong `MQL4\Presets`.
- Tag: `v215_forward_gap01`; DiagnosticMode=true; RecordReplayInputs=true. Giữ các guard và chiến lược mặc định. Preset dùng font 14 để các dòng chẩn đoán dễ vừa màn hình.
- Dừng EA V213 trên chart cũ nếu nó vẫn phát tín hiệu. Giữ nhật ký cũ để đối chiếu.
- Chạy Install-Demo-Learning.cmd một lần nếu thư mục gói V215 chưa có môi trường Python. Chạy Start-Demo-Learning.cmd và dán trực tiếp journal V215 bên dưới, vì tag chẩn đoán khác tag demo mặc định.

```
<MT4 Data Folder>\MQL4\Files\BO_V2\v215_forward_gap01_EURUSD
```

Symbol có hậu tố thì tên thư mục cũng có hậu tố. Chọn đúng thư mục chứa `demo_policy.csv`. Không cần Tor/IQ bridge hoặc Install-Deep-Learning.

## 2. Thu dữ liệu

Giữ MT4 và cửa sổ bộ học mở trong một phiên ban đầu khoảng 2–4 giờ. Khoảng này chỉ để bắt đầu quan sát, không bảo đảm có tín hiệu hoặc đủ mẫu đánh giá chiến lược. Nếu chưa có ứng viên đã LOCK, tiếp tục thêm phiên với cùng tag và cấu hình.

Theo dõi Dashboard: tuổi tick, gap tick, số khóa, số hủy do khoảng giữa tick/thời gian thiếu tick, ENTRY. Khi có hủy, dòng “Lúc hủy” giữ tuổi giá lưu và tuổi tick tại chính thời điểm hủy, khác tuổi báo giá đang tăng theo thời gian hiện tại.

Sau cuối tuần hoặc khoảng trống, cần đủ 64 nến M5 liên tục để lịch sử SAN_SANG. WAIT không tự chứng minh lỗi. Giữ guard 3 giây; không tăng giới hạn chỉ để có tín hiệu.

Observer và input được ghi ngay khi có sự kiện. `execution_diagnostics_*.csv` chỉ có khi xuất hiện ứng viên với sự kiện LOCK/CANCEL/ENTRY; chưa có file này có thể do chưa có ứng viên, không tự đồng nghĩa lỗi ghi.

## 3. Chốt bản sao ổn định

1. Dừng cửa sổ Start-Demo-Learning bằng Ctrl+C.
2. Gỡ EA V215 khỏi chart hoặc đóng MT4 để nhật ký ngừng thay đổi. Nút “Tạm dừng tín hiệu” trên Dashboard vẫn ghi dữ liệu nên chưa đủ để tạo bản sao ổn định.
3. Sao chép toàn bộ thư mục `v215_forward_gap01_EURUSD` sang nơi riêng, ví dụ `C:\EA_Diagnostics\v215_forward_gap01_EURUSD`.
4. Mở lại MT4/gắn lại V215 nếu muốn tiếp tục thu với cùng tag. Thao tác khởi động lại được ghi trong nhật ký; phần chuẩn bị chưa ENTRY có thể bị hủy theo guard khởi động lại.

Nhật ký live không có `tester_complete.csv`; không tạo hoặc chép marker Tester vào live.

## 4. Chạy chẩn đoán

Trong gói V215, chạy `Diagnose-Execution.cmd`. Dán đường dẫn bản sao vừa tạo. Không cần chạy Train-History hoặc Train-Deep-History.

Đợi báo `REVIEWED` và đường dẫn Output. Gửi file `execution_review_v215.zip` trong Output. Nếu cần kiểm tra sâu hơn, giữ nguyên thư mục nguồn để có thể nén gửi sau. ZIP báo cáo chỉ chứa báo cáo JSON/CSV, không chứa toàn bộ nhật ký.

Nếu BLOCKED, giữ thông báo lỗi. Không xóa hoặc sửa file để vượt kiểm tra. Một lượt không có ứng viên vẫn xuất được báo cáo với số tín hiệu 0.

## 5. Đọc kết quả

| Phân loại | Ý nghĩa |
|---|---|
| FRESH_INCOMING_TICK_AFTER_OBSERVATION_GAP | Tick vừa đến theo đồng hồ quan sát, nhưng khoảng với tick trước vượt guard sau LOCK |
| TIMER_WITHOUT_RECENT_TICK | Timer/replay kiểm tra khi chưa có tick đủ gần |
| STORED_QUOTE_AGE_ONLY | Thiếu observer; chỉ biết tuổi báo giá lưu trong dự báo |
| OBSERVER_PRESENT_REVIEW_REQUIRED | Có observer nhưng cần đối chiếu thêm |

Đây là chẩn đoán quan sát tại terminal. Không tự chứng minh độ trễ mạng hoặc độ chính xác timestamp từ nhà cung cấp. Dữ liệu Tester có tick dựng/spread 0 được gắn cảnh báo riêng. Không cộng ứng viên đã hủy thành lệnh thắng/thua, không dùng vài giờ forward để kết luận win rate hoặc kích hoạt model sâu.
