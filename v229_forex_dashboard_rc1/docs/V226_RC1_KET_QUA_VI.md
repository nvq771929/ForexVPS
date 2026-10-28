# Kết quả V2.26 RC1 và bước vận hành tiếp theo

Ngày hoàn tất: 25/10/2026. Đây là bước chuẩn hóa dữ liệu và trạng thái quan sát
sau hai lượt pilot V2.25, chưa phải bản nâng chất lượng CALL/PUT bằng model mới.

## Đã hoàn thành

- Bộ source đầy đủ V2.26, gồm Binary và Forex kế thừa, preset và công cụ học.
- Lưu nguyên gói nến bộ quan sát thực nhận, metadata khởi tạo, checksum liên
  kết và checkpoint để khôi phục đúng chuỗi đầu vào/cấu hình đã cam kết.
- Tạo tập nghiên cứu mới từ lịch sử 01/10/2025–27/03/2026 đã thu thập: 33.336
  ANCHOR thô, bỏ 500 mẫu giao nhau giữa hai lượt, còn **32.836 mẫu duy nhất**.
  Có cả thị trường EA chọn WAIT; không chỉ dùng những tín hiệu đã công bố.
- Đầu vào là chuỗi hành vi nến M5/M15/H1 và bối cảnh phiên/thời gian, có mask
  cho phần thiếu. Không dùng EMA hoặc tuổi nhãn quan sát làm feature của tập
  mới. Nhãn chính là hướng BID sau Entry 30 phút; 5/15 phút để đối chiếu.

Hướng tăng/giảm trong tập dữ liệu không phải tỷ lệ thắng của một model hoặc
lợi nhuận giao dịch. Chưa có model mới được fit, xuất trọng số hoặc kích hoạt.

## Kiểm chứng đã thực hiện

| Kiểm chứng | Kết quả |
|---|---|
| Kiểm thử source chính | 328 đạt, không bỏ qua |
| Kiểm thử LearningSupervisor | 76 đạt, không bỏ qua |
| Khôi phục trạng thái trên hai bộ nến thật đã lưu | 36.077 + 9.536 nến; trạng thái số giống chạy liên tục |
| Feature cố định giữa hai pilot khác ngày khởi tạo | 806 thời điểm so được, không sai khác; gồm 9 công bố chung |
| Kiểm tra hash feature | Toàn bộ 32.836 mẫu |
| Đối chiếu audit công bố cũ | 237 trường hợp × 3 thời hạn = 711 biên giá |
| Tính lại feature độc lập từ CSV gốc | 133 mẫu, 76.608 giá trị số |
| Mã thực thi kế thừa | 34 Include và 7 hàm native giữ nguyên; MQL4 khớp mt4 |

Trong 824 snapshot chung của hai pilot, 18 thời điểm không có nến ANCHOR cuối
cùng trong nguồn CSV dùng để tái dựng feature. Những thời điểm đó không được
bịa dữ liệu hoặc tính là đã so khớp. Các thử nghiệm hỏng checkpoint, đổi danh
tính nguồn, hỏng/đứt gói đầu vào đều kiểm tra việc từ chối khôi phục.

Thử nghiệm MQL được chạy qua C++ shim. **Chưa compile MetaEditor hoặc kiểm
chứng checkpoint trên MT4 Windows**. Không có kết luận hiệu quả giao dịch.

## Phân chia dữ liệu

| Phần | Số mẫu |
|---|---:|
| TRAIN | 11.322 |
| INNER_VALIDATION | 3.612 |
| CALIBRATION | 3.715 |
| Đánh giá hồi cứu đã từng xem | 13.695 |
| Loại tại ranh giới thời gian | 492 |

Purge/embargo 18 giờ 35 phút tách cửa sổ feature và nhãn giữa các phần. Tất cả
lịch sử này đã được nghiên cứu trước; phần đánh giá không phải holdout mới.
293 mẫu thiếu biên giá 30 phút giữ UNAVAILABLE, không đổi thành LOSS. 296 mẫu
hòa được giữ riêng. Nhãn tương lai chỉ dùng để chấm kết quả, không vào feature.

## Anh cần làm gì với gói source

1. Giải nén vào thư mục riêng, giữ V2.25 để đối chứng. Chép nội dung MQL4 vào
   Data Folder/MQL4 rồi compile `EURUSD_M5_Intelligence_V226.mq4`.
2. Khi compile đạt, dùng preset `EURUSD_M5_V226_Embedded_Pilot_UTC0.set`, tag
   V226 mới và đúng nguồn UTC+0 đã xác nhận. Forex và tác động tư vấn đều tắt.
3. Chạy một pilot ngắn với Every tick, Visual Mode tắt; khoảng 08–17/04/2026
   có thể dùng để đối chiếu pilot02. Mục tiêu là kiểm tra định dạng/lưu dữ liệu,
   không tối ưu hay chứng minh tăng tỷ lệ thắng. Giữ Report, Journal và thư mục
   nhật ký mới sau khi kết thúc.
4. Không chạy lại sáu tháng chỉ để tạo tập học: tập đó đã chuẩn bị xong.

Checkpoint không làm Strategy Tester có chức năng tiếp tục sau Stop. Mỗi lượt
Tester vẫn cần tag mới. Thử gỡ/gắn lại EA live với cùng tag chỉ là bước kiểm
chứng quan sát tiếp theo khi có giá; không thực hiện giao dịch Forex trong
pilot này. Đọc `V226_CONTEXT_DATA_VI.md` trước khi vận hành.

## Nghiên cứu model tiếp theo

Từ tập dữ liệu đã khóa, so sánh mô hình hướng giá 30 phút theo thứ tự:

1. Baseline đơn giản và Logistic/Histogram Gradient Boosting để đo giá trị
   tăng thêm của chuỗi giá so với các quy tắc hiện có.
2. TCN nhỏ dùng chuỗi M5/M15/H1; giữ thời điểm khả dụng, mask và đầu vào nhân
   quả. Chỉ thêm kiến trúc phức tạp nếu kết quả kiểm chứng cho thấy có lợi.
3. Chọn cấu hình trong TRAIN/INNER_VALIDATION, hiệu chỉnh xác suất riêng trên
   CALIBRATION; khóa model/ngưỡng trước khi báo cáo phần hồi cứu. Đánh giá độ
   hiệu chỉnh, độ phủ, sai số theo phiên và tính ổn định theo ngày/tuần.
4. Do các mẫu 30 phút giao nhau, không coi 32.836 mẫu là 32.836 phép thử độc
   lập; dùng thống kê theo khối thời gian. Không chọn ngưỡng theo kết quả hồi
   cứu đã thấy và gọi đó là xác nhận độc lập.
5. Model chỉ quan sát trước. Cần kiểm chứng ngoài mẫu mới và dự báo được ghi
   nhận trước kết quả rồi mới xét quyền tư vấn WAIT cho EA.

TCN legacy trong source dùng hợp đồng khác; không nạp thẳng NPZ mới vào đó.
Huấn luyện/đánh giá vẫn chạy ngoài EA. Bộ quan sát nhúng V2.26 hoạt động không
cần CMD nhưng chưa có khả năng tự huấn luyện hay tự thay chiến lược.
