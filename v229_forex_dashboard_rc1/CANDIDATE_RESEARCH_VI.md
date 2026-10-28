# Nghiên cứu chất lượng ứng viên V2.22

Mục tiêu là xác suất giá đi thuận hướng CALL/PUT sau kỳ hạn, dựa trên thông tin đã biết tại LOCK. Tập chính là READY_AT_LOCK. Hủy sau LOCK không làm thay tập đăng ký và không bị tính thành LOSS hướng giá. WIN/LOSS mô phỏng lệnh native vẫn được thống kê riêng.

## Hai tiến trình Python

| Công cụ | Vai trò |
|---|---|
| Start-Demo-Learning | Luồng legacy: kết quả mô phỏng native, Bayesian/Logistic và hợp đồng forward đã có |
| Start-Candidate-Research | Luồng mới: đọc BIN prefix bất biến, lập snapshot và nghiên cứu chất lượng ứng viên |

V216: xem thêm SESSION_NEWS_VI.md. CMD thứ hai tự lấy lịch tin nền và ghi bridge quan sát local; BIN, policy và runtime giao dịch giữ nguyên. Báo cáo hiện tại cập nhật mỗi vòng dù model WAIT_NEW_DATA.

Tiến trình mới không phải huấn luyện học sâu liên tục và không thay action trên Dashboard. Kết quả nghiên cứu được tính sau khi có nhãn, ghi rõ retrospective. Không tính chúng là dự báo EA đã phát trước kết quả. Không bật auto trade.

## Lịch sử: chỉ chạy một lần

1. Chạy Install-Demo-Learning một lần trong gói V222.
2. Chạy `Train-Candidate-History.cmd`.
3. Dán đường dẫn cache V211 hoặc thư mục Tester có `tester_complete.csv`. Giữ nguyên dữ liệu gốc.
4. Công cụ xuất thư mục mới dưới `candidate_research`; xem `latest_status.json` và `r000001_.../candidate_report.json`. Gửi `candidate_review_v224.zip` khi cần phân tích.

Không cần Train-History/Train-Deep-History trước nếu đã có cache hợp lệ. V215 không sửa cache gốc. Không lấy raw Tester chưa hoàn tất để train.

## Forward: nghiên cứu định kỳ

1. Để EA V222 và Start-Demo-Learning chạy.
2. Chạy thêm `Start-Candidate-Research.cmd`, dán đúng journal LIVE đang thu.
3. Mặc định kiểm tra mỗi 300 giây. Lượt đầu tạo snapshot ngay; chỉ thử lại sau ít nhất 7 ngày theo clock broker **và** thêm 50 nhãn READY quyết định có đủ features. Bộ này dùng từng feed/policy/origin riêng, không ghép LIVE với Tester.
4. Ctrl+C để dừng; chạy lại với cùng nguồn thì dùng lại registry. Đổi feed/policy/horizon phải dùng output riêng. Nếu có thư mục lượt ghi dở do ngắt máy, giữ nguyên để chẩn đoán, không ghi đè.

Registry dùng OS lease, checksum, xác minh đặc trưng LOCK/nhãn đã trưởng thành không bị thay, và giữ pointer ứng viên offline cũ khi lượt mới chưa đạt. Output nằm ngoài thư mục MT4. Không có quyền import/activate.

## Điều kiện và kết quả

- Chia theo ngày quan sát: 60% train / 20% calibration / 20% evaluation, embargo một ngày. Chỉ dùng nhãn đã trưởng thành trước mốc tiếp theo; TIE giữ riêng.
- Sàn: 400 train, 100 calibration, 150 evaluation **quyết định** READY có features. Thiếu thì COLLECTING, báo `deficits`; không fit/xuất model.
- Đủ mẫu mới thử Logistic gộp điều chuẩn C=0.1. Chọn 24 biến anchor hoặc 40 biến anchor+T1 trong inner-train; không đủ inner-sample thì dùng cố định 24 biến. Chuẩn hóa train-only, clip ±6, calibration Platt ở tập riêng.
- So với prior train toàn cục và prior setup+hướng co về prior chung. Kiểm tra Brier, log-loss, coverage ≥20%, ít nhất 100 mẫu được chọn/8 tuần, Wilson lower >56,945%, weekly ROI và stress 2 points, paired gain, ba đoạn đánh giá theo thời gian. Đây là cổng nghiên cứu, không phải cam kết tỷ lệ thắng.
- RESEARCH_NOT_QUALIFIED: đã fit nhưng không vượt đủ cổng. FROZEN_CANDIDATE: vượt cổng ngoại tuyến, vẫn không có quyền native filter/OBSERVE. Các đoạn lịch sử đã xem được coi là nghiên cứu thăm dò; cần kiểm chứng mới độc lập.
- Payout dùng giả định 82%; nhãn là Bid MT4 đúng mốc entry/expiry ±2 giây. Missing quote là UNAVAILABLE, TIE không đổi thành thắng/thua. Kết quả không phản ánh khớp lệnh/payout thật Olymp Trade.

Observer ghi `candidate_rules_<session>.csv` và `candidate_contract_<session>.csv`. Báo cáo kiểm tra chúng với BIN và session, hash snapshot anchor nếu có. Đếm từng điều kiện có thể chồng lấp; không cộng như các nguyên nhân loại trừ nhau. Thiếu observer cũ được đánh dấu, không tái tạo tick từ OHLC.

Mô hình sâu TCN và các nghiên cứu UP/DOWN cũ vẫn giữ đủ source. Hướng candidate encoder/head sâu sẽ được thử riêng khi có đủ dữ liệu và đối chứng, chưa nối vào EA trong V216.

V222 bổ sung sổ công bố riêng trong manual_signal_review.json/manual_signals.csv. Xem MANUAL_SIGNALS_VI.md; các nhãn mới chưa tham gia registry/model.


V222 bổ sung `slot_diagnostics_v222.json`, `daily_session_diagnostics` và `session_filter_diagnostics` trong live_session_review.json. Số qua ATR 2/2.5/3 pip chỉ là thống kê điều kiện đơn lẻ, không phải tín hiệu/lệnh/thắng. `news_source_review_v222.json` cùng snapshot và raw body mới (nếu có) giải thích nguồn nhận gì, sự kiện được chọn/loại vì sao. Những báo cáo này làm mới độc lập với mô hình, không được dùng để tự import/kích hoạt native.
