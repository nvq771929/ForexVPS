# Kết quả nghiên cứu kế thừa từ V213

Tài liệu dưới đây lưu lượt nghiên cứu V213, không phải lượt huấn luyện mới của V214. Kết quả kiểm tra V214 nằm trong REAL_DIAGNOSTIC_CHECK_VI.md.

# Kết quả kiểm tra V2.13 trên cache anh đã gửi

Đã chạy `Train-Deep-History` V213 trên cache V211 thực của anh, giữ nguyên file đầu vào; không cần anh lặp lại ngay. Đây là kiểm tra phần mềm và nghiên cứu lịch sử, chưa phải xác nhận lợi nhuận.

## Sửa dữ liệu và dừng học

- 54.334 dòng T+1 được chuyển sang hợp đồng V2 50 đặc trưng; sửa 234 trường hợp thiếu vùng mục tiêu, không xóa dòng.
- Vẫn 42.127 mẫu đủ chuỗi, test 7.046 mẫu (6.862 UP/DOWN, 184 TIE). ID các tập giữ nguyên so với lượt V212 để đối chiếu.
- TCN inner chạy 4 epoch, chọn epoch1 vì validation log loss lần lượt 0,693822 / 0,694283 / 0,695260 / 0,696163. Patience3 dừng quá trình và khôi phục checkpoint epoch1.
- Outer refit chạy đúng 1 epoch trên toàn outer train. Không dùng calibration/test để chọn epoch.
- Đã lưu model/checkpoint của từng thuật toán, đường học, fingerprint và audit chuyển đổi.

## Dự báo context

| Mô hình | Brier test, thấp hơn tốt hơn | Mẫu được chọn | Thuận / ngược hướng dự báo | Trạng thái |
|---|---:|---:|---|---|
| Logistic | 0,25000856 | 9 | 5 / 4 | Chưa đạt |
| HGB | 0,24983473 | 1 | 0 / 1 | Chưa đạt |
| TCN | 0,24988875 | 0 | Chưa có mẫu chọn | Chưa đạt |
| Mốc tần suất tăng từ train | **0,24981328** | — | — | Đối chứng |

Logistic vẫn được chọn bằng vòng nội bộ trước test, với Brier nội bộ 0,25032850; TCN 0,25033644; HGB 0,25171516. Không chọn lại HGB chỉ vì Brier test tốt hơn hai model còn lại.

TCN có chất lượng xác suất tốt hơn kết quả V212 từng báo cáo, nhưng vẫn kém baseline toàn cục và không chọn mẫu đủ tin cậy. Các thay đổi gồm đặc trưng, chuẩn hóa, seed, early stopping và runtime; không quy cải thiện này riêng cho một yếu tố hoặc coi là bằng chứng độc lập mới.

Logistic có ROI giả định 82% khoảng +1,11% trên 9 đơn vị cược (lãi giả định 0,10 đơn vị). Chỉ 9 mẫu, cận dưới ROI âm và Brier vẫn kém baseline, nên không đạt kiểm định. Không được diễn giải thành EA đã có lợi nhuận thực.

## Candidate quality riêng

Mô hình thống kê ứng viên dùng cùng cửa sổ ngày nhưng không đòi đủ32 anchor, vì vậy có 504 mẫu train (493 quyết định), 115 calibration (113 quyết định), 86 test. Nó chấm chuyển động Bid theo hướng ứng viên đã biết tại LOCK, gồm cả lượt bị hủy/chưa công bố.

Model không chọn ứng viên nào đạt ngưỡng độ tin cậy từ train. Test chưa đạt yêu cầu tối thiểu100 quyết định; các kiểm tra chất lượng xác suất và mẫu được chọn cũng chưa đạt. Trạng thái `CANDIDATE_RESEARCH_NOT_QUALIFIED`.

Trong toàn bộ 86 ứng viên test có 52 hướng đi thuận, 34 ngược; tỷ lệ thô60,47%, Wilson95% khoảng49,90%–70,14%. Đây không phải 86 lệnh thực thi, không phải tỷ lệ thắng của các tín hiệu được model chọn, không đủ để kích hoạt giao dịch. Calibration có56 thuận/57 ngược và train244 thuận/249 ngược, nên không có cơ sở suy ra tỷ lệ thô tốt ở test là lợi thế bền vững.

## ENTRY

319 lượt công bố native vẫn bị hủy QUOTE_GAP; 284 đúng mốc ENTRY, 35 trước mốc; entry hợp lệ0. Report V213 thể hiện rõ các con số và ví dụ. Không có observer gốc nên trigger và độ trễ mạng vẫn chưa được xác minh. Guard3giây được giữ nguyên.

## Hành động hiện tại

Giữ cache và các kết quả. Không import model nghiên cứu. Nếu muốn thử lại trên Windows, dùng gói V213 và chạy thẳng Train-Deep-History với cache V211, không cần Train-History/Tester lại. Muốn tiếp tục thu dữ liệu trên chart, compile EA V213 và dùng InstanceTag mới theo UPGRADE_V213_VI.md.

Các mô hình sâu/candidate chưa được nối vào bộ lọc live. Cần dữ liệu ứng viên và xác nhận mới/forward để đánh giá bước nâng cấp tiếp theo.
