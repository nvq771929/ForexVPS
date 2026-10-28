# V2.28 phục hồi từ V2.26 — Demo và Real

Gói source, preset, công cụ và tài liệu; không có EX4. Đây là bản phục hồi, không phải ZIP V2.28 cũ.

350 kiểm thử source và 76 LearningSupervisor đạt, không skip. Kiểm thử MQL chạy qua C++/API giả lập; chưa compile MetaEditor, pilot MT4 Windows, xác minh lịch tin live hoặc kiểm chứng lợi nhuận.

Kiểm tra file .sha256 và RELEASE_RECEIPT.json, giải nén rồi đọc RECOVERY_V228_VI.md. Preset Forex Real có thể mở lệnh thật nếu quyền MT4 bật và mọi điều kiện đạt. Đối chiếu giờ broker trước; không coi tên UTC0 là xác nhận giờ tài khoản mới.

Source ở ../../v228_recovered_rc1. Bản sao Git dùng nhánh recovery/v228-from-v226-20261028; main được giữ nguyên. Trạng thái remote_backup_verified=false trong ZIP là trạng thái tại thời điểm đóng gói trước khi push; xác nhận commit trên remote được ghi riêng sau đó.
