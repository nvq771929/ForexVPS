> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# V2.24 Binary research RC1 — cài đặt tùy mục đích

**Để phân tích bộ V219 hiện có, không cần thay EA trên MT4.** Giải nén gói
riêng, cài dependencies nếu cần và chạy `Review-Binary-Losses.cmd` theo tài
liệu nghiên cứu. Giữ dữ liệu/source gốc; không ghi đè journal.

Nếu cần kiểm tra source V224 trên MT4: sao lưu Data Folder, để lượt Tester
hiện tại kết thúc, chép `MQL4/Experts`, `MQL4/Include` và `MQL4/Presets` vào
đúng Data Folder. Compile `EURUSD_M5_Intelligence_V224.mq4` trong MetaEditor.
Dùng `TradingMode=BinaryOption`, chart EURUSD M5, InstanceTag mới cho mỗi
lượt Tester. Không gọi đây là bản nâng chất lượng tín hiệu đã kiểm định.

Forex là component V222 giữ nguyên; các đường dẫn `FX_V222`, contract và
state quản lý lệnh được giữ để không làm mất guard/rủi ro của vị thế cũ.
Không chạy đồng thời hai EA Forex cùng tài khoản/cặp. Lượt nghiên cứu này
không yêu cầu bật giao dịch Forex hoặc chuyển sang tài khoản thật.

Đây là source RC: chưa compile MetaEditor/chạy Windows MT4 trong môi trường
phát triển. Kiểm thử logic bằng C++/Python không thay thế hai bước đó.
