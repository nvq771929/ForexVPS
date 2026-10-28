# V2.29 — Dashboard dành riêng cho EA Forex

V2.29 kế thừa source V2.28 phục hồi. Thay đổi lần này là giao diện Forex;
chiến lược, lệnh, rủi ro, SL/TP, tin tức, clock/lock/freshness và bộ học giữ nguyên.
Không có model hoặc dữ liệu huấn luyện mới. Bản V2.28 và ZIP đã giao được giữ lại.

## Vì sao preset cũ không làm chữ Forex lớn lên?

Forex cũ dùng `Comment()` của MT4 để viết một khối chữ nhỏ trên chart. Các input
PanelFontSize/PanelLeft chỉ được áp dụng cho bảng Binary. V2.29 dùng label và
bảng nền riêng cho Forex, nối vào lớp hiển thị của Expert. Tất cả 39 header đã
giao cùng V2.28, gồm ForexEngine, UI Binary, clock và quản lý rủi ro, vẫn nguyên
từng byte. Thêm duy nhất `ForexDashboard.mqh`; không thay logic giao dịch.

## Thông tin trên bảng

| Nhóm | Nội dung |
|---|---|
| Trạng thái | Phiên bản Expert, DEMO/REAL/TESTER, server, tài khoản, Magic; trạng thái nổi bật và mã native để chẩn đoán |
| Tài khoản/rủi ro | Balance, Equity, free margin, margin level, ngưỡng dự trữ; trần rủi ro theo 0,5% × min(Balance, Equity) |
| Giới hạn ngày | Giảm Equity từ mốc EA đã lưu, mức giới hạn và trạng thái khóa; lượt vào, chuỗi thua, cooldown còn lại |
| Vị thế của EA | Số lệnh, BUY/SELL, ticket, lot, giá vào, SL/TP, P/L gồm swap/commission, tổng P/L thả nổi của đúng EA |
| Thời gian giữ | Thời gian đã giữ/còn lại theo birth gốc đã lưu, kể cả residual sau partial close; MM:SS và hạn giờ broker |
| Điều kiện vận hành | Spread hiện tại/giới hạn, kết nối, quyền giao dịch MT4, quyền Real, trạng thái lịch tin, giờ broker, tuổi quote |
| Bảo vệ | Break-even, trailing, thời gian giữ tối đa, bình quân giá, lịch broker, emergency-close theo cấu hình |
| Kết quả/nhật ký | Số lệnh đóng và net trong lịch sử MT4 đang tải; đường dẫn nhật ký Forex |

Lệnh thủ công/EA khác trong họ EURUSD được cảnh báo riêng, không cộng vào P/L
của EA này. Balance/Equity/margin vẫn thuộc tài khoản MT4 dùng chung, không tách
thành vốn riêng cho chart. Trần rủi ro theo vốn là giới hạn cấu hình, không phải
cam kết EA được phép mở lệnh: các guard ngày, lot, margin, tin và quote vẫn áp dụng.

Không có mốc Equity hoặc state thời gian hợp lệ thì hiện CHUA CO MOC/CHUA XAC
THUC, không bịa số. Margin=0 hiện N/A, không hiện tỷ lệ giả. Net lịch sử có nhãn
"lich su MT4 dang tai", không giả định toàn bộ lịch sử tài khoản đã được tải.
Preset không giới hạn thời gian hiện KHONG GIOI HAN; các preset vận hành vẫn 60 phút.

Màu xanh dương phân nhóm; đỏ cho lỗi/ngắt kết nối/giới hạn ngày và P/L âm; vàng
cho trạng thái chờ, thiếu quyền hoặc dữ liệu tin chưa sẵn sàng. Bảng không tự
bật AutoTrading, cho phép Real, sửa lỗi tin hoặc mở/đóng lệnh. Không có nút giao
dịch thủ công mới. Payout, CALL/PUT, kết quả Binary và thông tin học không nằm
trong Dashboard Forex. Giao diện Binary được giữ nguyên.

## Cài và dùng

1. Giải nén gói V2.29 vào thư mục mới. Giữ source, EX4 và nhật ký V2.28 để đối chiếu.
2. MT4 → File → Open Data Folder. Chép nội dung `MQL4` trong gói vào Data Folder/MQL4.
3. Compile `Experts/EURUSD_M5_Intelligence_V229.mq4` trong MetaEditor. Cloud chưa
   có compiler MetaEditor và không cung cấp EX4 đã kiểm chứng.
4. Dùng Expert V229 và preset V229 tương ứng. Bốn preset chính vẫn đủ Binary/
   Forex × Demo/Real; `ForexUseDashboard=true` trong các preset. Forex dự kiến
   EURUSDz, phân tích M5. Đối chiếu symbol và giờ broker thực tế trước khi dùng.
5. Điều chỉnh bảng bằng các input có sẵn:

| Input | Tác dụng với Forex |
|---|---|
| `PanelFontName` | Font, mặc định Arial |
| `PanelFontSize` | Chữ nội dung, preset chính 14 |
| `ActionFontSize` | Chữ trạng thái nổi bật; Forex giới hạn 24 để giữ bố cục |
| `PanelLeft`, `PanelTop` | Vị trí góc trên trái |
| `ForexUseDashboard` | true dùng bảng mới; false chỉ dùng hiển thị Comment cũ |

Khi đổi Expert trên chart Forex còn vị thế, giữ nguyên tài khoản, symbol và
Magic để tiếp tục quản lý. Không xóa `EA_MODE_V228` hoặc nhật ký/risk state để
bỏ qua cảnh báo. Hợp đồng vai trò V228 và clock observation V227 giữ nguyên.
Không có bước cài đặt nào tự bật quyền giao dịch của MT4.

Các `.cmd`, Python tools, LearningSupervisor và bốn preset vẫn nằm trong gói
full. `Start-Forex-News.cmd` nhận MT4 Data Folder hoặc thư mục Forex như phần dưới; `Start-Candidate-Research.cmd`
nhận đúng nhật ký Binary. Cài Python bằng script đi kèm nếu cần; không đóng gói
virtualenv hoặc model mới. Preset Forex Real vẫn cho phép mở lệnh thật khi quyền
MT4 bật và mọi điều kiện đạt; thay giao diện không tạo quyền mới.

## Chọn thư mục cho Start-Forex-News

V2.28 yêu cầu MT4 Data Folder, nên nhập thư mục con
`MQL4/Files/FX_V222/LIVE_...` gây lỗi "Expected an existing MT4 Data Folder with
MQL4/Files". Đó là lỗi chọn cấp thư mục, chưa phải lỗi tải lịch tin.

V2.29 nhận cả năm cấp đường dẫn dưới đây, gồm đường dẫn có dấu cách hoặc được
đặt trong dấu ngoặc kép:

- MT4 Data Folder: thư mục mở bằng File → Open Data Folder.
- `Data Folder/MQL4`.
- `Data Folder/MQL4/Files`.
- `Data Folder/MQL4/Files/FX_V222`.
- `Data Folder/MQL4/Files/FX_V222/LIVE_...` có file `forex_session.csv`.

Công cụ in rõ Data Folder đã xác định và nơi ghi bridge chung:
`MQL4/Files/FX_V222/news_calendar.csv`. Không ghi lịch vào từng thư mục LIVE,
không sửa các file `forex_events`, `forex_quotes`, risk state hoặc thư mục Binary.
Thư mục không hợp lệ, thư mục Binary và thư mục Tester bị từ chối trước khi gọi
mạng. Dạng dòng lệnh `--data-folder` cũ vẫn dùng được.

Hai chart Binary/Forex trên cùng tài khoản Demo dùng chung Data Folder.
`Start-Candidate-Research.cmd` vẫn nhận chính xác nhật ký **Binary**; worker tin
Forex dùng bridge **Forex** riêng. Binary NEWS_CLEAR không thay thế việc cập nhật
bridge Forex. Bộ lọc Forex tiếp tục chặn Entry nếu lịch thiếu/cũ/không xác thực.
Việc nhận diện đường dẫn không bỏ qua các kiểm tra checksum/freshness hoặc tin.

## Kiểm chứng

Kiểm thử kiểm tra label/font/nền, dữ liệu tài khoản/vị thế, cảnh báo, birth gốc,
state hỏng, dọn đối tượng khi tháo EA và tách Binary/Forex. Bật/tắt Dashboard được
so kết quả lệnh và file nhật ký từng byte trên các kịch bản native giả lập.
Hash toàn bộ header V2.28 được đối chiếu; UI không gọi hàm giao dịch hoặc guard
có tác dụng thay đổi trạng thái. Log cuối nằm trong `validation/tests.txt` và
`validation/learning_tests.txt`, số lượng tại `RELEASE_STATUS.json`.

Đây là kiểm thử source qua C++/API shim. Chưa xác nhận compile MetaEditor, kích
thước chữ/DPI thực tế trên Windows hoặc pilot giao dịch Exness. Sau compile,
kiểm tra hiển thị trên Demo với preset/font hiện tại. Không dùng thử nghiệm giao
diện để kết luận lợi nhuận, sửa TIME_ANOMALY hoặc nới điều kiện vào lệnh.
