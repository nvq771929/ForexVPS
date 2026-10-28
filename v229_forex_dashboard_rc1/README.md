# ForexVPS V2.29 — Dashboard Forex, đầy đủ Demo và Real

V2.29 thêm bảng Forex dễ đọc, tập trung tài khoản/rủi ro/vị thế/điều kiện vận hành;
giữ nguyên logic giao dịch và giao diện Binary của V2.28 phục hồi.
Đọc [hướng dẫn Dashboard/cài V2.29](FOREX_DASHBOARD_V229_VI.md) trước khi dùng.
Compile `MQL4/Experts/EURUSD_M5_Intelligence_V229.mq4`. Gói có đủ bốn preset
Binary/Forex × Demo/Real; preset Forex Real có quyền mở lệnh thật khi MT4 cho phép.

Nền kế thừa: [hướng dẫn V2.26](V226_CONTEXT_DATA_VI.md), lưu chính xác đầu vào observer,
metadata bootstrap và checkpoint kiểm tra nguồn/cấu hình/chuỗi khi gắn lại EA.
Phần mới chỉ quan sát; logic CALL/PUT, guard, ATR và Forex giữ nguyên.
Không có trọng số mô hình mới hoặc bằng chứng cải thiện giao dịch.

Công cụ `tools/prepare_price_behavior.py` tạo tập nghiên cứu giá đa khung có
mask và biên giá TICK đúng hạn từ lịch sử đã có, không huấn luyện/kích hoạt model.
Mô hình legacy và hợp đồng dữ liệu mới được tách riêng.

`mt4` là source chuẩn; `MQL4` là bản cài giống hệt. Include V224 và một số tên
file/contract cũ là chủ ý tương thích. Không cần source phiên bản cũ.
Gói là source; chưa compile MetaEditor hoặc kiểm chứng checkpoint MT4 Windows.
