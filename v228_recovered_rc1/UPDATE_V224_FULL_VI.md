> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# V2.24 Full RC2

Gói này có đủ EA và bộ học, độc lập với V2.23. Đây là gói mới thay cho việc chỉ
phát hành companion RC1. Xem INSTALL_V224_FULL_VI.md để cài đúng bản.

Cấu trúc thực tế ở ngay gốc ZIP:

- MQL4/Experts/EURUSD_M5_Intelligence_V224.mq4
- MQL4/Include/EURUSD_M5_V224/
- MQL4/Presets/ và MQL4/Indicators/
- mt4/: source chuẩn, trùng khớp MQL4.
- LearningSupervisor/: bộ học giám sát, worker đối thoại và tests.
- intelligence/, tools/, tests/: công cụ/kiểm thử đầy đủ kế thừa.
- validation/: log kiểm thử và audit bảo toàn source.
- MANIFEST_SHA256.json và RELEASE_STATUS.json.

Hai cờ trao đổi/tác động mặc định OFF. Phần ảnh hưởng tín hiệu chỉ là WAIT veto
có điều kiện trước khóa, không có quyền đổi quyết định Forex hoặc bỏ guard.
Không có trọng số thị trường kèm theo, không có biên nhận kiểm định sẵn.
Chưa có EX4; cần compile và pilot trên MT4 Windows của anh.

Lượt V2.23 hiện tại cứ hoàn tất. Giữ bản V2.23 và dữ liệu như mốc đối chứng.
Đừng xóa/sửa journal cũ khi chuyển source. Các tài liệu INSTALL_V222_VI.md và
INSTALL_V224_VI.md là hướng dẫn kế thừa; dùng INSTALL_V224_FULL_VI.md cho RC2.

## Bổ sung RC3

Trợ lý cục bộ dùng `Install-Local-AI-Assistant.cmd` và `Start-Local-AI-Assistant.cmd`; xem [LOCAL_AI_V224_VI.md](LOCAL_AI_V224_VI.md). Giữ V2.23 hoàn tất lượt Tester 01/04–16/05/2026 trước khi pilot. Không có weights LLM/model 30 phút hoặc quyền can thiệp mới trong gói.
