# Nghiên cứu chiến lược và thời gian giữ lệnh — vòng 2

Đây là công cụ ngoại tuyến, không phải EA mới. Không thay V 2.29, preset vận hành, model hoặc quyền giao dịch. Dữ liệu giá và kết quả cá nhân giữ ngoài Git.

Protocol được commit trước kết quả kinh tế của vòng này. Dữ liệu M5 đã được xem ở các vòng trước; các nhóm thời gian đều là hồi cứu, không có holdout mới. Mọi phương án đều được xuất, không chọn tham số hoặc kích hoạt chiến lược theo ô có kết quả đẹp nhất.

## Câu hỏi và đối chứng

- Bộ phân loại hiện tại gán bao nhiêu chu kỳ cho từng chiến lược? Điều kiện trigger nào loại phần lớn mẫu?
- Nếu xét riêng SR1/TP1/BR1, vẫn giữ điều kiện biến động và cấu trúc, kết quả tham chiếu ra sao? TP1/BR1 ngoài regime gốc có quy ước hướng EMA rõ ràng, nên đây không phải phép đo thuần ảnh hưởng routing.
- Sáu phương án bỏ lần lượt một điều kiện TP1 dùng để kiểm tra đóng góp của tổ hợp điều kiện, không phải khuyến nghị nới điều kiện vận hành.
- Cùng điểm vào, giới hạn giữ 30/60/120 phút thay đổi kết quả thế nào? Một lệnh có thể chạm SL/TP trước hạn; không bắt buộc giữ hết thời gian.
- BO được đánh giá theo hướng sau 5 phút với payout 70/82/90%. Forex dùng SL=max(1.5 ATR,6 pip), tối đa 30 pip, TP 2 R và giới hạn thời gian. Đây chưa phải SL cấu trúc/break-even/trailing của EA.

Giữ cả năm hợp đồng cũ qua tên tương ứng, thêm native ATR0 và các đối chứng trigger/routing: tổng 15 mô hình. Forex có 30/60/120 phút, hai thứ tự SL/TP nếu cùng nến chạm cả hai, phí khứ hồi kết hợp commission/trượt giá 0/0.5/1 pip, và hai cách lấy mẫu. Toàn bộ 540 dòng tổng hợp Forex và 45 dòng BO đều là mô tả, không là cuộc thi chọn chiến lược thắng.

## Phí, thời gian và cách lấy mẫu

Spread 0 là giả định phù hợp để nghiên cứu tài khoản Zero đã được xác nhận, không là bằng chứng spread lịch sử luôn 0. Commission thực tế chưa biết; các mức phí là độ nhạy giả định. Swap, broker fills và độ trễ thực không được mô phỏng.

`all_entries_overlapping_diagnostics` xét từng ứng viên độc lập, có thể chồng lấn. Không cộng thành lợi nhuận tài khoản. `one_position_per_model_hold_path` chỉ nhận điểm vào khi vị thế tham chiếu trước đã kết thúc, không vào mới trên nến đang có vị thế tại open. Các giới hạn giữ khác nhau có thể tạo danh sách điểm vào khác nhau; vì vậy xuất thêm `paired_hold_*` trên cùng điểm vào có đủ ba kết quả để tách ảnh hưởng này.

Thoát trong nến chỉ biết mốc M5 chứa sự kiện; `exit` ghi biên trên của nến, `exit_bar` ghi nến chứa sự kiện. Mốc này không phải thời điểm khớp tick chính xác. Hết hạn dùng giá mở nến quan sát được; không dùng high/low của nến sau hạn. Gap thiếu dữ liệu tạo UNAVAILABLE thay vì điền giá hoặc tính lợi nhuận 0. Sau gap, phép lấy mẫu một vị thế giữ vùng loại trừ đến quan sát tiếp theo.

`trajectory_*` mô tả toàn bộ đường giá tới hạn, bỏ qua việc lệnh có thể đã thoát. MFE/MAE của bảng này có thể bao gồm giá SAU khi lệnh mô phỏng đã đóng; không phải lợi nhuận đạt được và không bao giờ là đầu vào dự báo.

ATR tương đối chỉ là phân nhóm mô tả: ATR tại mốc phân tích chia trung vị ATR bình quân cùng giờ broker của 20 ngày quan sát trước, cần tối thiểu 10 ngày. Không dùng số liệu của chính ngày đang xét để xây chuẩn. Session UTC0 vẫn là giả định cho toàn lịch sử; xuất thêm độ nhạy offset±60 phút. Không chọn phiên sau khi xem kết quả.

## Chạy và xác minh

Cần Python 3, g++ C++17 và `tzdata==2026.4` như v1. Giữ hai thư mục `strategy_review_v1` và `strategy_review_v2` cạnh nhau. Scanner mới include bản lõi v1 đóng băng; không sửa native source. Các kiểm thử C++ chỉ là lớp mô phỏng API cần thiết, không phải MetaEditor/MT 4.

```bash
python -m unittest discover -s tests -v
python study.py --source /path/EURUSDz5.csv --baseline-scan /path/v1/native_scan.csv --output /path/new-output
```

Output phải chưa tồn tại. Input bị ràng buộc SHA 256 trong `protocol.json`. Trước khi tính kinh tế, toàn bộ 47.754 mốc baseline/ATR0 phải khớp scanner v1, gồm regime, hướng, lý do và ATR.

Kiểm thử bao gồm causality/prefix, chuẩn ATR chỉ dùng ngày quá khứ, Bid/Ask/phí, timeout tại open, stop-gap, hai thứ tự barrier, thiếu dữ liệu, điều kiện so sánh cặp và một vị thế. Cần đối chiếu thêm các hợp đồng cũ với tín hiệu/kết quả v1 thực tế; test tổng hợp không chứng minh lợi nhuận thị trường.

## Đầu ra

`coverage.csv`, `candidate_scan.csv`, `anchor_context.csv`, `signals.csv` mô tả việc hình thành ứng viên. `binary_*`, `forex_summary.csv`, `bracket_labels.csv`, `trajectory_*`, `paired_hold_*` và `breakdowns.csv` chứa kết quả tham chiếu; `session_offset_sensitivity.csv` kiểm tra cách gắn nhãn phiên. `run.json` lưu hash dữ liệu/code/protocol và phạm vi.

`validate_results.py` đối chiếu từng tín hiệu của năm hợp đồng cũ, các nhãn kết quả 60 phút với đối chứng spread/phí 0, kiểm tra phí và cùng điểm vào. Nó xuất thêm `ablation_incremental_summary.csv`, bảng mô tả sau lượt chạy về riêng mẫu mới khi bỏ một điều kiện; đây không phải lựa chọn mô hình hoặc một phép thử xác nhận đã đăng ký trước. Báo cáo, kết quả và công cụ dựng báo cáo có số liệu của người dùng được giữ ngoài Git. Công cụ kiểm tra không sửa quy tắc hoặc nhãn đã chạy.

Bootstrap 95% theo tuần là mô tả chưa điều chỉnh nhiều phép thử. Kết quả dương cần chi phí xác minh, kiểm định đầy đủ tick/platform và dữ liệu tương lai mới. Kết quả âm của proxy cũng không chứng minh toàn bộ EA native thua lỗ.
