# Bộ ghi dữ liệu nghiên cứu độc lập — bản 1

Mục đích: thu Bid/Ask tại callback OnTick, thời gian gốc, trạng thái kết nối, M5 đã đóng và commission ghi nhận trên các lệnh demo đã đóng. Đây là bộ quan sát riêng, không phải bản nâng cấp EA giao dịch.

## Cài lên chart thứ ba

1. Trong MT4 chọn **File → Open Data Folder**. Chép `mt4/EURUSD_Research_Recorder_V1.mq4` vào `MQL4/Experts`.
2. Mở file bằng MetaEditor, nhấn **F7** để biên dịch. Công cụ đã được kiểm thử qua lớp mô phỏng API C++ và Python; môi trường nghiên cứu chưa có MetaEditor/MT4 Windows để biên dịch native.
3. Mở **chart EURUSDz M5 thứ ba** trên tài khoản demo đang dùng. Hai chart BO và Forex hiện tại giữ nguyên.
4. Gắn `EURUSD_Research_Recorder_V1` vào chart thứ ba. Có thể nạp `mt4/Research_Recorder_V1.set`, hoặc dùng mặc định. Bộ ghi chỉ nhận tài khoản demo, EURUSD có hậu tố broker và chart M5; từ chối Strategy Tester.
5. Khi chart hiển thị **RECORDING**, để MT4 tiếp tục chạy. Bộ ghi có thể thu callback khi AutoTrading tắt; nó không yêu cầu đổi quyền giao dịch của hai EA đang vận hành. Nó không có hàm gửi, sửa, đóng hoặc xóa lệnh.

Thư mục hiển thị trên chart nằm tại:

```text
MQL4/Files/EA_RESEARCH_CAPTURE/research_001_.../
```

Ghi liên tục qua những phiên cần đánh giá. Một phiên là mẫu khởi đầu; chưa có số giờ cố định bảo đảm đủ mẫu hoặc xác nhận lợi nhuận. Các mốc giờ broker, PC UTC và giờ địa phương được giữ riêng.

## Chốt và gửi một lượt dữ liệu

1. **Tháo riêng bộ ghi khỏi chart thứ ba** để ghi dòng END và chốt số lượng bản ghi. Các chart giao dịch vẫn chạy như trước.
2. Chạy `windows/Pack-Research-Capture.cmd` và chọn đúng **thư mục con chứa metadata.csv**. Không chọn toàn bộ MT4 Data Folder.
3. Công cụ tạo `Research_Capture_....zip` ở thư mục cha và mở vị trí file. Gửi ZIP đó để kiểm tra dữ liệu. Nếu bộ ghi báo WRITE ERROR, giữ nguyên thư mục để đối chiếu; lỗi ghi không được xem là một lượt dữ liệu hoàn chỉnh.

CMD chỉ gọi script PowerShell cục bộ để chọn thư mục và nén CSV. Nó không chạy EA, bật AutoTrading, đăng nhập broker hoặc gửi dữ liệu qua mạng. Instance lock bị loại khỏi ZIP. Đường dẫn có khoảng trắng được xử lý bằng đối số và LiteralPath.

## Dữ liệu được ghi

- `metadata.csv`: demo/account/server/symbol/currency, kích thước hợp đồng, giá trị tick, giới hạn lot/stop tại thời điểm bắt đầu. Đây không phải lịch sử metadata đã xác minh cho mọi thời điểm.
- `ticks.csv`: **callback OnTick được MT4 chuyển tới bộ ghi**, gồm Bid/Ask, thời gian quote broker theo giây, PC UTC/local và bộ đếm thời gian đến tương đối. Giữ các callback có cùng thời gian/giá; không gộp thành một tick.
- `heartbeats.csv`: trạng thái bộ ghi/kết nối mỗi lần timer chạy. Heartbeat không là quote mới, không dùng để điền những tick thiếu.
- `bars_m5.csv`: tối đa 2.048 nến đóng lúc khởi động, rồi bổ sung khi có nến mới. Có thời điểm quan sát; lịch sử này không phải nến dựng từ tick của bộ ghi và không chứng minh đã sẵn có trước những quyết định cũ.
- `closed_orders.csv`: các market order EURUSDz đã đóng trong phần lịch sử MT4 đang tải, nhìn lại tối đa 30 ngày mặc định. Xuất lúc bắt đầu và cập nhật khi chốt. Không mở giao dịch mới để lấy commission. Không có dòng lệnh nghĩa là **chưa biết commission**, không phải phí bằng 0.
- `session.csv`: BEGIN/END và số dòng, số callback, trạng thái ghi. Bộ ghi phát hiện đổi tài khoản/server/symbol và đánh dấu lượt dữ liệu cần xem lại.

Nếu đã có lệnh EURUSDz demo đóng trước đây, có thể chọn **Account History → All History** trong MT4 để tải lịch sử trước khi bắt đầu/chốt bộ ghi. File xuất vẫn chỉ phản ánh phần lịch sử terminal thực sự cung cấp, không tự xem mẫu trống là phí 0.

File cá nhân nằm trên máy người dùng hoặc thư mục recovery ngoài Git. Gói mã nguồn không chứa lịch sử tài khoản hay giá của người dùng.

## Giới hạn quan trọng

MT4 chỉ cung cấp thời gian quote broker theo giây trong hợp đồng này. Bộ ghi **không bịa timestamp mili giây của server**; thời gian đến tương đối chỉ dùng sắp thứ tự callback. File có sequence liên tục và END đúng chứng minh tính nhất quán cục bộ, không chứng minh thu đủ mọi tick của broker. MT4 có thể gộp callback khi xử lý chậm; khoảng lặng giá hoặc kết nối không tự chứng minh mất gói.

Commission xuất ra là giá trị có dấu trên các ticket demo đã đóng đang hiện trong lịch sử MT4. Không được suy thành biểu phí tài khoản real hoặc phí của những giao dịch không được xuất. Validator chỉ quy đổi pip khi tài khoản USD, symbol EURUSD và kích thước hợp đồng hợp lệ; không nhân hai lần nếu commission trên ticket đã là giá trị được ghi nhận cho cả giao dịch. Rủi ro về cách broker hạch toán phí riêng vẫn cần đối chiếu statement nếu có.

## Phần BO

BO không có dữ liệu nền tảng trong các file đã gửi. Bộ ghi MT4 này không thu được giá Olymp Trade hoặc payout của Olymp Trade.

Hai mẫu CSV trong `templates` dành cho dữ liệu demo **đã có** từ nền tảng:

- `BO_Platform_Quotes.csv`: giá và payout tại thời điểm quan sát, nếu có nguồn xuất/ảnh đối chiếu.
- `BO_Platform_Trades.csv`: các giao dịch demo đã thực hiện, với giá vào/hết hạn, payout, stake, kết quả và nguồn đối chiếu.

Để trống mẫu nếu chưa có dữ liệu; không tính mẫu trống thành kết quả thắng/thua. Không cần điền thủ công liên tục như một tick feed. Có thể gửi file xuất hoặc ảnh gốc từ nền tảng để ánh xạ sang mẫu sau, giữ nguyên nguồn và giờ hiển thị.

Timestamp phải có múi giờ, ví dụ `2026-10-29T10:00:00+07:00`; payout 82% ghi `0.82`. `source_reference` chỉ tới file xuất/ảnh gốc để đối chiếu. Giá Bid MT4 không được thay vào cột giá nền tảng BO. Validator kiểm tra cấu trúc, không xác thực độc lập nội dung screenshot/statement hoặc tự kết luận lợi nhuận.

## Kiểm tra dữ liệu ở môi trường nghiên cứu

```bash
python -m unittest discover -s tests -v
python validate.py --capture /path/session-folder --output /path/new-quality-output
python validate.py --bo-quotes templates/BO_Platform_Quotes.csv --bo-trades templates/BO_Platform_Trades.csv --output /path/new-bo-output
```

`audit_legacy.py` kiểm tra các file Bid/Ask được V2.29 chấp nhận trước đây. Chúng có thời gian ước lượng và không bao gồm callback bị clock guard loại; không được gọi là full tick backtest. Kết quả của các công cụ ở giai đoạn này là chất lượng dữ liệu, không phải chiến lược được xác nhận hoặc lợi nhuận của EA.
