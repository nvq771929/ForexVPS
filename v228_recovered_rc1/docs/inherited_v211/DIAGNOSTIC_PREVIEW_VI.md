# Kiểm tra gói chẩn đoán lấy mẫu bằng V2.11

Nguồn: `training-diagnostics_20261018_140844_890639.zip`, SHA256:
`595835c86485cc61c85a2c6d8b987bfc1006f2406bd6d8ff68f4c960c09b4471`.
Manifest SHA256 và 2.174 file sự kiện trong gói đã được kiểm tra riêng lẻ bằng
bộ giải mã native. Gói chỉ chứa các cửa sổ lấy mẫu, có khoảng trống sequence;
không được coi là bộ Tester đầy đủ, không chạy huấn luyện hay chuyển model từ gói này.

V2.11 ghép được 322 hàng nghiên cứu: **275 nhãn đã đóng** (128 UP, 137 DOWN,
10 TIE), 46 thiếu dữ liệu, một OPEN. Có 42 nhóm thiếu entry và 206 nhóm thiếu
LOCK trong phần được lấy mẫu nên không tạo hàng. Các số thiếu có thể do rìa
cửa sổ lấy mẫu; không suy ra tỷ lệ thiếu của toàn bộ lịch sử.

Không có lệnh mô phỏng được thực hiện trong mẫu này. 275 nhãn hướng giá không
phải 275 lệnh, không có tỷ lệ thắng hoặc mô hình thị trường đạt kiểm định.
Chi tiết dữ liệu riêng nằm ở `diagnostic-preview-v211.json`.

Thử nghiệm xác nhận có thể lấy dữ liệu nghiên cứu có giá hợp lệ từ nhật ký cũ
ngay cả khi tập tín hiệu đủ điều kiện rỗng. Toàn bộ 331.741 sự kiện gốc vẫn ở
máy của anh: cần chạy Train-History V2.11 với thư mục hoàn tất đó để biết số
mẫu và chất lượng mô hình trên toàn bộ dữ liệu.
