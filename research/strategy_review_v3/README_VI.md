# Vòng 3: cấu trúc SL, bảo vệ lệnh và độ ổn định

Công cụ nghiên cứu ngoại tuyến, không phải bản EA mới. Giữ nguyên V2.29, v1, v2 và các preset. Không train hoặc kích hoạt model; không gửi lệnh. Giá, nhãn kết quả, báo cáo và mã dựng báo cáo có số liệu cá nhân giữ ngoài Git.

## Hợp đồng kiểm định

Protocol được commit trước kết quả kinh tế của vòng này. Giữ cả 15 phương án v2, không chọn riêng nhóm đã dương. Toàn bộ lịch sử đã được xem; các giai đoạn thời gian chỉ là phân nhóm hồi cứu, không phải holdout mới.

Forex có bốn chính sách: đối chứng ATR cố định như v2; SL có xét điểm vô hiệu cấu trúc; cùng SL đó thêm hòa vốn; cùng SL đó thêm hòa vốn và trailing. Giữ giới hạn 30/60/120 phút, cả hai thứ tự SL/TP khi cùng nến chạm hai mốc và phí khứ hồi giả định 0,01/0,31/0,51 pip. Mốc 0,01 pip là phép quy đổi từ mức commission khởi điểm trong ảnh, chưa xác minh phí EURUSDz; hai mốc sau cộng trượt giá giả định 0,3/0,5 pip. Spread giả định 0, chưa tính swap.

Điểm vô hiệu lấy từ Forecast đóng băng cho các nhánh native. Sáu phép bỏ điều kiện TP dùng công thức invalidation TP gốc; ba giả thuyết v1 dùng cực trị nến trigger cộng đệm 0,10 ATR như một proxy cấu trúc đã khai báo. Không mô tả chúng như stop native hoàn chỉnh.

SL cấu trúc kiểm tra đúng phía giá vào; khoảng SL tối thiểu là max(khoảng cấu trúc, 1,5 ATR, 6 pip), làm tròn giá ra ngoài theo tick 0,00001, loại nếu vượt 30 pip. TP 2R. Hàm giá đặt lệnh được đối chiếu với `FXBuildPlan` của mã gốc, dùng broker stop level 0 và spread 0 giả định; không xác nhận lịch sử điều kiện broker hoặc lot sizing.

Hòa vốn: giá quan sát tại open đạt 1R, offset 0,5 pip. Trailing: đạt 1,5R, khoảng max(1,5 ATR đóng, 3 pip), cải thiện ít nhất 0,5 pip. Chỉ cập nhật tại open đã quan sát, trước khi đọc high/low của nến hiện tại; không nới SL, thay TP hoặc đặt lại thời gian/rủi ro ban đầu. SL hòa vốn theo giá vẫn có thể cho kết quả ròng âm sau chi phí.

**Quản lý ở open M5 không tương đương EA quản lý theo tick.** Chưa có toàn bộ guard, lịch tin, lịch giao dịch, giới hạn rủi ro, sizing/margin hoặc broker fills. Không suy từ proxy dương/âm thành kết luận toàn bộ EA lãi/lỗ.

BO dùng cùng entry nhưng so sánh kỳ hạn 5/10/15 phút với payout 70/82/90%. Giá là Bid mở nến MT4; toàn bộ đường M5 đến hạn phải tồn tại. Kỳ hạn dài có các nhãn chồng lấn, không phải danh mục stake đã thực hiện. Không áp commission Forex vào BO. Thiếu quote, payout và khớp lệnh của nền tảng BO thực.

## Chạy lại

Giữ ba thư mục nghiên cứu v1/v2/v3 cạnh nhau. Cần Python 3, g++ C++17 và tzdata 2026.4. Dữ liệu/ứng viên bị ràng buộc bằng SHA256 trong protocol. Output phải chưa tồn tại.

```bash
python -m unittest discover -s tests -v
python evaluate.py --source /path/EURUSDz5.csv --signals /path/v2/signals.csv --prior-scan /path/v2/candidate_scan.csv --prior-labels /path/v2/bracket_labels.csv --output /path/new-output
```

`structural_scan.cpp` include lõi v1/v2 đóng băng; không sửa nguồn cũ. `frozen/ForexRisk.mqh` là bản sao byte-identical của header native để kiểm thử lập kế hoạch giá, không phải module giao dịch chạy trên terminal.

Trước khi tính kinh tế, scanner phải khớp 47.754 mốc v2 về ATR và các hướng ứng viên. Đối chứng ATR phải khớp từng nhãn v2. Các kiểm thử kiểm tra cập nhật không nhìn trước, hai hướng BUY/SELL, stop-gap, timeout, nội suy bị cấm, BO kỳ hạn dài và parity với kế hoạch giá native.

## Đầu ra và diễn giải

Xuất toàn bộ 1.080 bảng Forex và 135 bảng BO, từng nhãn, số mẫu bị loại/không rõ kết quả, phân nhóm tháng/giai đoạn/phiên, và chênh lệch theo cùng điểm vào. Các chính sách bảo vệ có thể làm thay danh sách lệnh một vị thế; so sánh cặp riêng dùng cùng entry/SL nhưng có thể chồng lấn, không cộng thành lợi nhuận tài khoản.

Ngưỡng phí hòa vốn mô tả là pip gộp bình quân của tập resolved với giả định chi phí pip cố định và quyết định không đổi; không là phí broker đã xác minh hoặc bảo đảm lợi nhuận. Bootstrap theo tuần 2.000 lần cho khoảng mô tả 95%, chưa điều chỉnh nhiều phép thử. Không chọn ô tốt nhất, không tự thay preset, không promote chiến lược từ lịch sử này.

`audit.py` kiểm tra từng nhãn, phí, các so sánh cùng entry và đối chứng đã giao. Công cụ này không sửa kết quả. Mã dựng báo cáo và bảng bổ sung có số liệu người dùng được giữ ngoài Git.
