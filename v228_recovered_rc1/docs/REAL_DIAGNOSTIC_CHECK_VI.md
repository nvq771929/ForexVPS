# Kiểm tra chức năng V214 trên dữ liệu người dùng

Đã chạy công cụ công khai tools/diagnose_execution.py V214 trực tiếp trên bản giải nén journal V213 Windows, không sửa file nguồn và không huấn luyện.

- 3.041 bản ghi BIN qua FNV/sequence/schema/identity và marker hoàn tất.
- 9 dòng observer qua kiểm tra sequence, sự kiện, nguồn và thời điểm đối chiếu BIN; ngày giờ Windows cũ đọc thành công.
- 118.296 dòng input, gồm 118.127 TICK và 169 TIMER. Cả hai tick hủy khớp giá và khoảng cách với tick trước trong input.
- 2 ứng viên đã công bố: cả hai FRESH_INCOMING_TICK_AFTER_OBSERVATION_GAP, khoảng 12 và 4 giây, tuổi tick mới 0 theo đồng hồ Tester; ENTRY hợp lệ 0.
- Dataset SHA256: 5d48d20158a6eb28fb44564dc48cba124b342af17df41a0de935fdfd580d15c6, khớp kiểm toán độc lập trước.
- Toàn bộ tick ghi spread 0, có cảnh báo. Không xác nhận tick thật hoặc độ trễ mạng.

Đã chạy CLI V214 với cache V211 thực trước đây: 319 lượt vẫn STORED_QUOTE_AGE_ONLY, giữ guard3, không tự tạo observer hoặc suy ra trigger. Cache và nhật ký gốc không thay đổi.

Đây là kiểm tra chức năng phần mềm với dữ liệu Tester đã có; không phải lượt V214 chạy thực tế trên Windows, không phải xác nhận lợi thế thị trường hoặc tỷ lệ thắng. MetaEditor/EX4 vẫn cần kiểm tra trên terminal người dùng.
