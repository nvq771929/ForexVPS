# Quy ước Dashboard đã chốt

Màn hình vận hành chỉ giữ thông tin cần quyết định. Phân tích dài, nhật ký kỹ
thuật và từng tiêu chí kiểm định nằm trong trang chi tiết/báo cáo.

| Nhóm | Nội dung cần thấy |
|---|---|
| Thông tin chung | Cặp tiền, khung nến, chế độ Binary/Forex, giờ và phiên; trạng thái dữ liệu/kết nối; tin liên quan kế tiếp và cảnh báo né tin |
| Binary Option | CALL/PUT/WAIT chính thức; chuẩn bị/đã phát/đang theo dõi; giờ vào, hết hạn, thời gian giữ và bộ đếm; kết quả MT4 gần nhất |
| Forex | Vị thế đang quản lý và lời/lỗ; lot/rủi ro; SL/TP và trailing/breakeven; margin còn lại/cảnh báo; trạng thái được giao dịch hay đang chặn |
| Bộ học | Mốc năng lực có bằng chứng; kết luận ngắn đã ghi nhận; đề xuất tiếp theo; chế độ quan sát hay đã được phép can thiệp |

Thông tin chung chỉ xuất hiện một lần. Chỉ mở rộng phần Binary hoặc Forex
đang dùng, phần không hoạt động thu gọn. Các mức rủi ro/margin cảnh báo hiện
rõ khi cần; không trải mọi tham số cấu hình lên chart. Lý do chặn, model ID,
toàn bộ chỉ số và diễn giải kỹ thuật đưa vào chi tiết.

RC1 cung cấp panel bộ học riêng ở góc phải chart, tối đa sáu dòng. Các nhóm
thông tin chung/Binary/Forex vẫn do EA V2.23 hiện tại hiển thị; chưa sửa hay
gộp lại Dashboard source của EA đó. Đây là quy ước cho lần tích hợp Dashboard
EA tiếp theo, không phải tuyên bố rằng giao diện EA V2.23 đã được thay thế.

Panel học chỉ nói về bộ học Binary của RC1. Bộ học Forex chưa có dữ liệu đánh
giá riêng, nên không được gắn năng lực Binary sang Forex. Không dùng điểm IQ,
phần trăm tiến hóa hoặc lời hứa thắng làm chỉ báo tiến bộ.
