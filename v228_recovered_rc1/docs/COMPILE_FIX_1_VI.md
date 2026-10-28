# V2.22 compile fix 1 — 21/10/2026

MetaEditor báo lỗi từ dòng 26 của SlotDiagnostics.mqh vì tên tham số `final`
trùng từ khóa MQL4. Các lỗi phía sau trong hàm là lỗi cú pháp phát sinh tiếp theo.
Đổi bốn chỗ sử dụng tham số thành `isFinal`, đồng bộ mt4 và mirror MQL4.
Không đổi chữ `FINAL` trong CSV, schema, phiên bản logic, chiến lược hoặc guard.

Nếu đã cài V2.22, chỉ cần chép đè file đã sửa vào Data Folder đang dùng:
`MQL4\Include\EURUSD_M5_V224\SlotDiagnostics.mqh`.
Mở `EURUSD_M5_Intelligence_V224.mq4` trong MetaEditor rồi nhấn F7.
Nếu còn giữ bộ source riêng, cập nhật cả file tương ứng trong `mt4\Include`.
Không xóa nhật ký hoặc thu thập lại từ đầu để áp dụng sửa lỗi cú pháp này.

Bản source đầy đủ có VERSION.json và RELEASE_STATUS.json mang
`build_revision=compile-fix-1`; manifest và log kiểm thử được tạo lại.
Gói V2.22 đã gửi trước vẫn được lưu riêng để đối chiếu.

Bổ sung kiểm tra khai báo từ khóa `final`/`override` cho các kiểu cơ bản MQL.
Kiểm tra này bắt lại lỗi gốc; không phải trình biên dịch MQL4 hoàn chỉnh.
Bộ mô phỏng C++ trước đây không phát hiện vì C++ cho phép dùng `final` làm
tên tham số. Kiểm thử tự động gồm mô phỏng C++; môi trường hiện tại không có
MetaEditor để xác nhận compile trực tiếp hoặc chạy Windows MT4.
