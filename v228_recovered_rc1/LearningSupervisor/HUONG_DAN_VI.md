# Bộ học giám sát Binary V2.24 RC1

Đây là bộ đồng hành độc lập với EA V2.23, dùng để vận hành kiểm thử. Bộ này
không thay EA, không đổi ATR/chiến lược, không đặt lệnh và chưa có quyền điều
khiển CALL/PUT/WAIT. V2.23 đang chạy Strategy Tester cứ tiếp tục đến hết lượt.

## Bộ này học và hiển thị gì?

- Ghi hồ sơ chính thức CALL/PUT từ sổ phát tín hiệu, với 40 đặc trưng tại LOCK.
  Khi đủ lịch sử liên tục, giữ thêm chuỗi 32 nến đã đóng × 29 đặc trưng và
  50 đặc trưng bối cảnh T+1. Thiếu chuỗi thì ghi thiếu, không tự điền giá.
- Đối soát WIN/LOSS/TIE/UNAVAILABLE bằng giá BID MT4 tại mốc vào và hết hạn.
  Tín hiệu đã phát vẫn được tính nếu ENTRY kỹ thuật bị hủy sau đó. Bản ghi bị
  giữ lại, chưa phát ra, không được coi là tín hiệu chính thức.
- Tích lũy thống kê theo chiến lược, bối cảnh, phiên và vùng ATR; ghi số mẫu,
  khoảng bất định và các giả thuyết cần thử tiếp. Không ghi nhận thao tác vào
  lệnh thủ công hoặc kết quả của Olymp Trade/sàn khác.
- Huấn luyện theo đợt: Logistic làm đối chứng và TCN nhân quả làm mô hình sâu.
  Chọn mô hình bằng phần calibration, kiểm tra phần evaluation riêng. Chỉ
  mẫu WIN/LOSS đủ đặc trưng được huấn luyện; TIE/thiếu giá vẫn hiện trên báo cáo.
- Ghi dự báo mới với mã mô hình, mã hồ sơ, giờ thực sự lưu và biên nhận sau
  khi lưu bền vững. Dự báo chỉ được tính là tiến tới khi nguồn LIVE, đồng hồ
  đã xác nhận, mô hình tồn tại trước bối cảnh, toàn bộ dữ liệu đánh giá của
  mô hình đã kết thúc trước bối cảnh và việc lưu hoàn tất trước giờ vào.

"Đã học" có ba nghĩa khác nhau: đã lưu hồ sơ; đã rút thống kê mô tả; hoặc đã
huấn luyện trọng số mô hình. Dashboard phân biệt các trạng thái này. Nhiều
mẫu hơn hoặc chạy lâu hơn chưa chứng minh dự báo tốt hơn. Bộ này không tự
nghĩ như con người và chưa tự sáng tạo/kiểm định chiến lược giao dịch mới.

## Cài lần đầu

1. Giải nén bộ này vào thư mục riêng, ví dụ `D:\EA_Learning_V224`.
   Tránh thư mục Data Folder, nhật ký EA, OneDrive và thư mục đồng bộ mạng.
2. Khuyến nghị Python 3.12, bản 64 bit cho Windows (bộ đã kiểm thử bằng Python
   3.12.14 trên Linux; code yêu cầu 3.11 trở lên). Chạy `INSTALL_LEARNING.cmd`.
   Numpy, PyTorch CPU và tzdata được cài trong `.venv` riêng. Bước này cần
   Internet để tải thư viện; vận hành bộ học không gửi dữ liệu ra mạng.
3. Không chép đè thư mục EA V2.23. Không import lịch sử trong lúc EA thu thập.

## Trong lúc Tester V2.23 đang chạy

Chưa chạy WATCH trỏ vào dữ liệu Tester. Đợi Tester hoàn tất, rồi chạy lệnh
AUDIT bên dưới với thư mục chứa `tester_complete.csv`, `demo_policy.csv`,
`data_origin.csv`, các BIN, `input_*.csv` và `manual_v218_*.csv`.

```bat
.venv\Scripts\python.exe run_supervisor.py cycle --source "D:\Data\v223_sessions_6m_01_TESTER_EURUSD" --output "D:\LearningRuns\V223_6Months" --broker-utc-offset-minutes 0
```

`0` chỉ dùng khi đã xác nhận giờ server của toàn giai đoạn là UTC+0, như lượt
lịch sử đang nghiên cứu. Nếu chưa xác nhận, bỏ tùy chọn này: phiên là UNKNOWN
và chưa tính dự báo tiến tới. Không suy ra giờ live từ việc giờ lịch sử là UTC+0.

Lệnh CYCLE thu nhận → đối soát → thống kê → xem xét huấn luyện, rồi kết thúc.
Lượt đầu dữ liệu lớn có thể lâu do kiểm tra từng BIN/FNV và các tick tham chiếu.
Thời gian này chưa đo trên máy anh. Cần giữ thư mục đầu vào đầy đủ, không đổi
tên/xóa file. Không cần chạy lại Tester chỉ để tạo báo cáo này.

Mở `D:\LearningRuns\V223_6Months\dashboard.html` để xem kết quả. Dữ liệu cũ
luôn là hồi cứu; dù kết quả đẹp cũng chưa phải kiểm thử tiến tới.

## Khi chuyển sang thu thập live

1. Cho EA V2.23 chạy trên chart EURUSD M5 theo cấu hình Binary đã chốt.
   Giữ ghi replay input để có thể đối soát giá/tick. Dùng thư mục live riêng
   có origin `LIVE_MT4`; không đổi origin của dữ liệu Tester.
2. Chạy `START_WATCH.cmd`. Dán đường dẫn **thư mục nhật ký**, không phải ZIP.
3. Nếu muốn panel MT4, nhập đường dẫn thực của `Terminal\Common\Files`.
   Nếu chưa dùng panel, nhấn Enter. Dữ liệu hiển thị chỉ được ghi vào thư mục
   con riêng `V224Supervisor` trong Common Files; nhật ký EA vẫn chỉ được đọc.
4. Nhập độ lệch giờ server live đã xác nhận, tính bằng phút, hoặc Enter để
   để UNKNOWN. Đồng hồ máy Windows cần đồng bộ đúng giờ. Watch phát hiện
   nhảy đồng hồ sẽ ngừng công nhận dự báo tiến tới đến lần khởi động sau.
5. Mở `runtime\live\dashboard.html`. Trang tự tải lại mỗi 10 giây. Watch
   cập nhật mỗi khoảng 2 giây; bảng phải có heartbeat mới. Nếu đứng lâu,
   kiểm tra CMD thay vì coi trang cũ là trạng thái đang hoạt động.

WATCH chạy một tiến trình nền riêng mỗi 15 phút để đối soát, thống kê và xem
xét huấn luyện. Tiến trình nền dùng một luồng tính toán; Watch không chờ nó
huấn luyện xong. Khi đủ điều kiện, trọng số mới chỉ được nạp vào phần **shadow**
để thử dự báo, không được nạp vào EA. Mỗi nguồn/dataset dùng output riêng;
không ghép live và Tester vào cùng một SQLite. Kiểm tra `research/worker.log`
nếu phần nghiên cứu nền báo lỗi.

Bộ WATCH mới không thay hai CMD của V2.23. Nếu đang dùng tiến trình learner
nhẹ và tiến trình cấp tin/nghiên cứu của V2.23, giữ chúng theo cấu hình đã chốt;
đặc biệt cần giữ tiến trình cấp tin để EA tiếp tục nhận lịch kinh tế mới. Không
mở thêm bản trùng ghi cùng bridge tin tức. RC1 chỉ bổ sung bộ học sâu giám sát;
không tự truy xuất nguồn cấp tin hay cập nhật bộ lọc native của EA.

## Panel ngay trên chart MT4

1. Chép `MQL4\Indicators\BinaryLearningMonitor_V224.mq4` vào Data Folder
   `MQL4\Indicators` của MT4 rồi compile bằng MetaEditor.
2. Gắn indicator vào chart có EA. Indicator dùng panel ở góc trên bên phải,
   không thay EA và không đụng vào các đối tượng Dashboard của EA.
3. Nó đọc telemetry từ Common Files, hiển thị số WIN/LOSS đã đối soát, số mô
   hình, số dự báo trước giờ vào, giai đoạn phát triển, một ghi nhận ngắn và
   đề xuất hiện tại.
   Khi heartbeat cũ quá 30 giây sẽ cảnh báo. Chi tiết kiến thức/đề xuất nằm
   trong `dashboard.html`.

Indicator hiện cung cấp source `.mq4`; chưa có `.ex4`. Tôi chưa chạy MetaEditor
hay MT4 Windows trong môi trường phát triển này. Đây là điểm cần kiểm thử
đầu tiên trên máy anh. Nếu indicator compile lỗi, gửi nguyên thông báo; phần
HTML/thu thập Python vẫn hoạt động độc lập.

## Các mốc và tiêu chí

- Chờ dữ liệu → Đang thu thập → Đã huấn luyện/shadow → Đang kiểm thử dự báo.
  Đây là mốc bằng chứng, không phải thang IQ hay phần trăm chắc thắng.
- Tối thiểu 400 mẫu train, 100 calibration, 150 evaluation theo thứ tự ngày;
  có khoảng cách một ngày giữa các phần. Số mẫu thô có thể cần cao hơn vì
  thiếu chuỗi 32 nến, TIE, thiếu giá hoặc embargo. Chưa đủ thì `COLLECTING`,
  không tạo trọng số giả. Không hạ các mốc này chỉ để nhìn thấy mô hình.
- TCN: chuẩn hóa chỉ từ train; chọn số epoch trong phần train bên trong,
  rồi fit lại train với số epoch cố định. Calibration dùng hiệu chỉnh xác suất
  và chọn giữa Logistic/TCN; evaluation không tham gia chọn mô hình.
- Ngưỡng đề xuất shadow cố định 0,60 là **quy ước thử nghiệm**, không phải
  ngưỡng có lợi nhuận đã chứng minh. Ngoài miền dữ liệu thì WAIT. Xác suất
  CALL thấp không được tự chuyển thành PUT.
- Cần sai số Brier và Log loss tốt hơn xác suất cơ sở của train, đủ 8 tuần
  evaluation, ít nhất 100 mẫu được chọn và coverage 20% trước khi báo đạt
  cổng kiểm định hồi cứu. Đạt các cổng này vẫn chỉ được thử shadow.
- Mỗi đợt fit mới phải cách đợt trước ít nhất 7 ngày và có ít nhất 50 mẫu
  quyết định mới. Thí nghiệm cùng dataset được dùng lại, không ghi đè/tối ưu
  lại tập evaluation. Không cập nhật trọng số ngay sau từng lệnh thua.
  Các đợt tiếp theo cần phần evaluation mới nằm sau mốc evaluation trước;
  đủ 7 ngày/50 mẫu chưa tự đảm bảo đủ 150 mẫu đánh giá mới để fit tiếp.
- Quyền điều khiển EA luôn OFF trong RC1. Chưa có adapter phát lệnh vào EA.
  Sau dữ liệu tiến tới độc lập, cần đánh giá sai số, độ ổn định theo phiên,
  coverage, dữ liệu thiếu và quyết định riêng trước khi phát triển adapter đó.

## Nghiên cứu vì sao EA chọn WAIT

WATCH giữ các quyết định LOCK kể cả không có tín hiệu. Để theo dõi đường giá
và kết quả CALL/PUT giả định cố định ở nến M5 kế tiếp, dùng AUDIT với `--paths`:

```bat
.venv\Scripts\python.exe run_supervisor.py audit --source "D:\Data\CompletedJournal" --output "D:\LearningRuns\V223_6Months" --paths --broker-utc-offset-minutes 0
```

Chạy batch này khi không có một lệnh khác ghi vào cùng output. Nó có thể đọc
hết file tick và khá lâu; không chạy trong luồng ra quyết định của EA.
`path_diagnostics.json` chứa đường giá quan sát được, nhịp thuận phút đầu,
khoảng trống tick, kết quả hai hướng giả định. Chỉ nghiên cứu tại những mốc
LOCK EA đã ghi, chưa phủ mọi thời điểm trên thị trường. Giá đẹp sau đó không
tự chứng minh EA bỏ lỡ cơ hội, và không phải đặc trưng đầu vào mô hình.

## Xuất báo cáo, dừng và phục hồi

Ctrl+C dừng WATCH. Tiến trình nền đã khởi động có thể cần chạy nốt trong
`research/worker.log`; đợi nó xong trước khi sao chép toàn bộ thư mục runtime.
EA không bị tắt. Muốn sửa/import lịch sử thì vẫn phải xử lý việc dừng EA/MT4
riêng như đã thống nhất, không thao tác lịch sử qua bộ học.

```bat
.venv\Scripts\python.exe run_supervisor.py export --source "D:\Data\LiveJournal" --output "D:\EA_Learning_V224\runtime\live"
```

Gửi `V224_Supervisor_Review.zip`. Export dùng SQLite backup, không chép thô
database đang mở. Nó chứa hồ sơ, thống kê, mô hình nếu có và biên nhận dự báo;
không chứa toàn bộ tick/BIN gốc. Khi cần điều tra giá phải giữ/gửi thêm nhật ký EA.

Mỗi output có `.writer-lock` chống chạy trùng. Nếu CMD chết đột ngột, trước
hết xác nhận không còn `run_supervisor.py` nào dùng output đó, rồi xóa riêng
thư mục `.writer-lock` và chạy lại. Không xóa SQLite. Nguồn bị đổi/xóa BIN đã
ghi nhận sẽ báo lỗi; không tự bỏ kiểm tra để chạy tiếp.

## Kiểm thử và giới hạn hiện tại

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Fixture nguồn native được tạo từ source V2.23 thật dưới C++ MT4 API shim.
Kiểm thử deep dùng dữ liệu nhân tạo để kiểm tra phần mềm, không phải chứng
minh giao dịch có lời. Bộ giao không kèm mô hình đã huấn luyện từ thị trường.
Chưa có phép đo CPU/RAM/độ trễ MT4 trên máy anh. Khởi động một worker, quan
sát tài nguyên và chất lượng tick; dùng `--no-auto-research` nếu cần tạm hoãn
việc học nền trong khi vẫn thu nhận hồ sơ.
