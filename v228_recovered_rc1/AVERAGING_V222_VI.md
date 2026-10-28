# V2.22 — bình quân giá cùng chiều có giới hạn

V2.22 RC1 bổ sung lựa chọn anh đã xác nhận: thêm lệnh cùng chiều khi có giá
tốt hơn. Source V2.21 được giữ nguyên để đối chứng. Đây là cơ chế theo quy
tắc, chưa có kết quả thị trường chứng minh rằng bình quân giá tốt hơn một lệnh.

## Cách hoạt động

Khi `ForexEnableAveraging=true`, EA chia trước ngân sách rủi ro của một cụm:
70% dành cho lệnh đầu, phần còn lại dự phòng. Tổng rủi ro dự kiến tới SL của
hai lệnh, cộng đệm chi phí/trượt giá, phải nằm trong ngân sách ban đầu.
`ForexRiskPercent=0.5` là **0,5% cho cả cụm**, không phải 0,5% mỗi lệnh.
Giá trị này là dự toán; gap, phí thực tế và thực thi broker có thể làm lỗ vượt
dự toán. Không có bảo đảm lỗ tối đa đúng một số tiền trong mọi điều kiện.

EA chỉ xem xét thêm **một lệnh**, lot tối đa bằng 50% lot đầu, làm tròn xuống
theo broker. Cần đồng thời đáp ứng:

- Giá bất lợi trong khoảng 0,5–0,8R so với giá vào đầu tiên; BUY dùng Bid,
  SELL dùng Ask. R là khoảng giá khớp đầu đến SL gốc.
- Có setup M5 mới cùng chiến lược SR1/TP1/BR1 và cùng chiều, hoàn tất T+1,
  LOCK và các guard giá hiện có. Một nến sau thời điểm vào phải đóng trước
  khi phân tích setup mới; sớm nhất khoảng 10 phút sau entry đầu.
- Giá khớp dự kiến tốt hơn; điểm vô hiệu của setup mới không vượt SL gốc.
  ATR, SL tối thiểu 6 pip, spread và khoảng cách stop broker đều còn hợp lệ.
- Trong 30 phút đầu, chưa tới thời hạn giữ tối đa và SL đầu chưa được dời.
- Còn ngân sách chung, dư địa giới hạn lỗ ngày, số lượt gửi ngày, margin,
  quyền giao dịch, lịch hoạt động và lịch tin hợp lệ.

Không đủ lot tối thiểu hoặc thiếu điều kiện thì giữ lệnh đầu với SL/TP đã có.
Không hạ tiêu chuẩn để bắt buộc phải thêm lệnh. Với SL 6 pip và điều kiện
giá đã đi ngược 0,5R, khoảng SL còn lại thường không đủ 6 pip: EA sẽ từ chối.
Vì vậy số cụm có lệnh thêm có thể ít, cần đo bằng Tester thay vì giả định.

## SL, TP và thoát cụm

SL chung giữ tại SL đầu, không nới ra để cứu lệnh. TP chung giữ tại TP đầu.
Giá vốn cụm = tổng(lot × giá khớp)/tổng lot. Hòa vốn/trailing xét giá vốn này
và R gốc, chỉ siết SL. Hòa vốn giá không đảm bảo hòa vốn ròng sau phí.

Thời hạn 60 phút vẫn tính từ lệnh đầu. Ví dụ mở 10:00, thêm 10:10 thì hạn
vẫn 11:00, dù lãi/lỗ và chưa chạm SL. `ForexMaxHoldMinutes=0` chỉ tắt thoát
theo thời gian, không tắt SL/TP hoặc các điều kiện rủi ro khác.

Nếu một chân cụm đã được broker xác nhận đóng, EA yêu cầu đóng chân còn lại
để tránh để lại cụm thiếu. Khi quy tắc né tin yêu cầu giảm/thoát rủi ro,
**chế độ bình quân đóng toàn bộ cụm** thay vì cắt một phần từng chân. Chính
sách này áp dụng cả khi mới có lệnh đầu và không tự tính thêm một nhánh hedge.
Các điều kiện thoát khẩn cấp, lỗ ngày và cuối tuần tiếp tục áp dụng cho cụm.
MT4 không đóng đồng thời hai ticket một cách nguyên tử; EA ghi yêu cầu cho
cả hai trước khi gửi và thử lại các lần đóng chưa thành công.

## Ví dụ với 1.000 USD

Giả sử BUY đầu tại 1,10010, SL 1,09910 (10 pip), spread 1 pip, tick value
1 USD/point/lot trên feed 5 digits; đệm rủi ro tổng 0,8 pip. Ngân sách cụm 5 USD:

| Bước | Lot | Rủi ro tới SL có đệm |
|---|---:|---:|
| Lệnh đầu (phân bổ 3,50 USD) | 0,03 | 3,24 USD |
| Lệnh thêm tại Ask 1,09970, nếu setup đủ điều kiện | 0,01 | 0,68 USD |
| Cả cụm | 0,04 | 3,92 USD |

Giá vốn mới 1,10000, cải thiện 1 pip. Đây là ví dụ tính toán và kiểm thử
broker giả lập, không phải kết quả giao dịch thị trường hay lot cố định.
Nếu chỉ mở lệnh đầu rồi thắng/thua, lợi nhuận/rủi ro cũng nhỏ hơn cấu hình
một lệnh dùng trọn 0,5%; phải tính cả sự đánh đổi này khi so sánh.

## Inputs và preset

| Input | Mặc định | Ý nghĩa |
|---|---:|---|
| ForexEnableAveraging | false | Tắt mặc định; bật có chủ đích để nghiên cứu |
| ForexInitialRiskFraction | 0,7 | Phần ngân sách cho lệnh đầu |
| ForexAverageTriggerR | 0,5 | Mức bất lợi bắt đầu xem xét |
| ForexAverageMaxAdverseR | 0,8 | Không thêm quá gần SL |
| ForexAverageMaxLotRatio | 0,5 | Lot thêm/lệnh đầu tối đa |
| ForexAverageWindowMinutes | 30 | Thời gian được xem xét thêm |
| ForexMinMarginLevelPercent | 500 | Margin level dự kiến tối thiểu sau mở |
| ForexMinFreeEquityPercent | 50 | Free margin dự kiến tối thiểu/tài sản |

Hai kiểm tra margin áp dụng cả lệnh mở thông thường; đây là mức cấu hình
ban đầu, chưa tối ưu. Dùng dữ liệu margin do broker trả về và đệm chi phí,
không suy ra rủi ro giá từ đòn bẩy. Nếu metadata không hợp lệ thì không mở.

Đối chứng: `EURUSD_M5_V224_Forex_Tester.set` (bình quân OFF).
Thử bình quân: `EURUSD_M5_V224_Forex_Averaging_Tester.set` (ON).
Cả hai mặc định 0,5%, 60 phút, không dùng lịch tin hiện tại trong Tester.
Chạy cùng nguồn giá/Every tick/spread cố định/vốn 1.000 USD/đòn bẩy 1:500;
mỗi lượt dùng tag mới. Lưu Report, Journal và toàn bộ root Forex của từng lượt.
So sánh net sau phí, equity drawdown, chuỗi thua theo cụm, margin và số lần
thêm/từ chối; không chọn tham số bằng kết quả tập kiểm định cuối.

## Khôi phục và nhật ký

`basket_<id>.csv` lưu ngân sách/SL/TP/R gốc và setup; `basket_link_<ticket>.csv`
liên kết hai ticket. State có kiểm tra FNV và định dạng chuẩn, tách khỏi Binary.
`average_reserved/filled/failed_<id>.csv` chống gửi lại khi restart. Nếu API
trả kết quả không rõ, EA không đoán rằng chưa khớp rồi gửi thêm: chặn lệnh mới,
yêu cầu đóng vị thế own đã thấy và lưu `execution_review_required.csv` để
đối chiếu broker. Không tự xóa cờ này hoặc hứa xử lý mọi lỗi kết nối.

Tắt Input bình quân ngăn lệnh thêm, vẫn quản lý cụm đang tồn tại theo state.
Tăng RiskPercent không tăng ngân sách đã chốt; hạ RiskPercent có thể làm lệnh
thêm không còn đủ ngân sách. Không đổi Magic/mode/phiên bản khi còn vị thế.
Nếu gắn ON khi một lệnh cũ không có state cụm, EA không tự nhận lệnh đó làm
cụm mới; không nâng cấp hoặc bật cơ chế giữa một vị thế đang chạy.

`forex_average_policy.csv` ghi cấu hình mỗi lần khởi động. `forex_events.csv`
ghi AVERAGE_INTENT/FILLED và basket ID; state/CSV đóng từng ticket cho phép
đối chiếu Report. Lượt thêm cũng tính vào giới hạn 6 lần gửi/ngày; chuỗi thua
an toàn hiện đếm **ticket đã đóng**, nên hai chân thua có thể tính hai lần.
Bộ postmortem V221 cũ không tự gộp đúng hai giá vào khác nhau của V222;
khi đánh giá phải dùng liên kết basket cùng Report, không coi mỗi child là
một cơ hội độc lập. Chưa có bộ học Forex hoặc bằng chứng lợi nhuận đi kèm.
