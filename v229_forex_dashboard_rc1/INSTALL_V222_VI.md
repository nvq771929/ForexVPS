# Cài V2.22 Forex trên MT4 Exness

1. **Chờ lượt Tester V2.19 hoàn tất.** Lưu thư mục Tester, Report và Journal
   ra ngoài Data Folder. Giữ source V2.19 và bản sao lưu để nghiên cứu Binary.
2. Chỉ nâng cấp khi không còn vị thế Forex của bản cũ. Không để hai phiên bản
   cùng quản lý tài khoản. Giải nén vào thư mục riêng, ví dụ `C:\ForexVPS_V222`. MT4 → File → Open Data
   Folder; chép `MQL4` của gói vào đó. Không xóa V219 hoặc dữ liệu cũ.
3. F4 → mở `Experts\EURUSD_M5_Intelligence_V224.mq4` → F7. Cần **0 errors**.
   Source này chưa được compile bằng MetaEditor Windows tại môi trường phát
   triển; nếu lỗi, giữ nguyên danh sách lỗi và build MetaEditor để sửa.
4. Kiểm tra Forex bằng Strategy Tester trước: EURUSD/M5/Every tick,
   Optimization off, Visual tùy chọn, load `EURUSD_M5_V224_Forex_Tester.set`.
   Có thể chọn pilot **05/01/2026 → 10/01/2026**, thuộc nguồn giá đã đối chiếu.
   Dùng spread cố định và ghi rõ, ví dụ **10 points = 1 pip với 5 digits**;
   với 4 digits, 1 point = 1 pip. Không coi zero spread là chi phí thực tế.
   Nếu tag đã có kết quả thì đổi sang tag mới, không nối tiếp dữ liệu.
   Forex_Tester đặt ForexNewsFilter=false: lượt này KHÔNG kiểm định né tin lịch sử.
   Để đối chiếu bình quân, chạy thêm cùng giai đoạn với
   `EURUSD_M5_V224_Forex_Averaging_Tester.set` (ON), vốn 1.000 USD, đòn bẩy
   1:500 và cùng spread. Hai lượt dùng tag riêng; đọc AVERAGING_V222_VI.md.
5. Trên demo Exness, chart EURUSDz M5 (hoặc symbol EURUSD thực tế của tài khoản),
   load `EURUSD_M5_V224_Forex_Demo.set`. Bình quân vẫn OFF mặc định;
   sau khi kiểm tra Tester, muốn thử demo thì bật ForexEnableAveraging=true
   trước khi EA mở lệnh đầu. Không bật giữa một vị thế đang chạy.
   Kiểm tra TradingMode=Forex, ForexRiskPercent=0.5,
   ForexAllowRealTrading=false; cho phép live trading trong Expert properties
   và bật AutoTrading. Chạy Install-Demo-Learning.cmd một lần để tạo môi trường Python V222, sau đó
   chạy **Start-Forex-News.cmd** và nhập MT4 Data Folder. Giữ CMD này mở để lịch
   tin còn mới. Không cần hai CMD học Binary. Chờ Dashboard hết NEWS_UNKNOWN/
   NEWS_CLOCK_UNCERTAIN trước khi đánh giá giao dịch.
6. EA bỏ nến đang dở khi mới gắn, chờ M5 mới để phân tích, xác nhận T+1 và
   entry đúng mốc. Gắn lên chart không đồng nghĩa sẽ có lệnh ngay.
7. Sau khi kiểm tra compile/Tester/demo, nếu chọn dùng tài khoản real Exness,
   kiểm tra tài khoản và rủi ro rồi tự bật `ForexAllowRealTrading=true`.
   Input mặc định false để việc cài đặt không vô tình mở lệnh thật.

## Kết quả cần gửi để đối chiếu

Report, Journal/Experts và journal Forex của đúng lượt. Forex Tester thường ở:

`tester\files\FX_V222\v222_fx_pilot_a_TESTER_EURUSD`

Nếu symbol có hậu tố, tên thư mục theo symbol thực. Live ở
`MQL4\Files\FX_V222\LIVE_<account>_<feed_key>`; Dashboard hiển thị root thực.
Không cần gửi toàn bộ Data Folder.

Report Forex sẽ đếm broker trades của Tester. Đối chiếu ticket, giá, SL/TP,
profit/swap/commission với CSV Forex. Nếu ít hoặc không có lệnh, xem lý do
ATR/structure/T+1/quote/margin trong forex_events.csv, không nới guard để ép lệnh.
Kiểm thử phần mềm không xác nhận lợi nhuận hoặc khả năng khớp lệnh live.
