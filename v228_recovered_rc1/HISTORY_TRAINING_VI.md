# V215: nếu đã có cache V211, chạy thẳng Train-Deep-History.cmd

Không cần chạy lại Train-History/Tester để thử bộ học sửa lỗi. Xem UPGRADE_V215_VI.md. Hướng dẫn bên dưới dành cho tạo dữ liệu và luồng legacy; T+1 mới được chuyển sang hợp đồng V2 trước khi fit.

# V2.15 — học từ lịch sử MT4 rồi áp dụng khi chạy demo

Đọc **UPGRADE_V215_VI.md** để dùng dữ liệu cũ, chẩn đoán nhanh và tạo tập T+1.
V2.15 bổ sung tập 50 đặc trưng T+1 riêng, trong khi các tập cũ vẫn được giữ.

Quy trình: **Strategy Tester tạo dữ liệu → Python tạo các tập độc lập và kiểm
định lịch sử → đánh giá kết quả**. Chỉ nhánh model tín hiệu cũ đã đủ điều kiện
mới được chuyển sang chart live để quan sát; mô hình nghiên cứu hướng giá chưa
được nhập vào EA.
Anh vẫn vào lệnh thủ công trên Olymp Trade demo. Không có kết nối đặt lệnh sàn.

**Đã có nhật ký V2.08:** có thể dùng thẳng Train-History V2.15; xem UPGRADE_V215_VI.md, không cần chạy lại Tester.

## 1. Cài source V2.15

1. Giải nén vào một thư mục riêng, sao chép `MQL4` vào MT4 Data Folder.
2. F4 mở `EURUSD_M5_Intelligence_V215.mq4`, F7 biên dịch. Kiểm tra **0 errors**.
   Source đã được kiểm thử bằng C++ shim; MetaEditor/Tester Windows chưa có
   trong môi trường phát triển này, nên cần kiểm tra thực tế ở terminal của anh.
3. Chạy `Install-Demo-Learning.cmd` một lần trong thư mục gói V2.15.
   Cần Python 3.11+ và Internet để cài thư viện. Các lần chạy sau không cần cài lại.

V2.15 giữ hợp đồng dữ liệu V207 (logic 2026101707), tách lịch sử và live.
Các tên file model/state có hậu tố v207 là chủ ý tương thích. Source độc lập,
không cần cài V2.07. Bộ lịch sử V2.07 đã chạy xong vẫn có thể huấn luyện bằng
Python V2.15 nếu cùng cấu hình/feed. Không nối tiếp lượt Tester cũ; dùng tag
mới cho mỗi lượt. Giữ nguyên dữ liệu V2.06 để dự phòng.

## 2. Chạy Strategy Tester để tạo dữ liệu lịch sử

Trong MT4 nhấn Ctrl+R:

| Mục | Chọn |
|---|---|
| Expert Advisor | EURUSD_M5_Intelligence_V215 |
| Symbol | EURUSD cùng nguồn giá với chart sẽ chạy demo |
| Period | M5 |
| Model | **Every tick** |
| Optimization | **Tắt** |
| Visual mode | Có thể tắt để chạy nhanh hơn |
| Use date | Một đoạn lịch sử có dữ liệu; thử 6–12 tháng trước, mở rộng nếu thiếu mẫu |

Trong Expert properties → Inputs, Load preset
`EURUSD_M5_V215_History_Training.set`:

- InstanceTag: dùng tên riêng cho mỗi lần chạy, ví dụ `v215_hist_2024_2025_a`.
- EnableDemoSignals=true; DemoExpiryMinutes=5; RecordReplayInputs=true.
- CompactTesterLogs=true giúp bỏ nhật ký từng tick, giữ snapshot/khóa/kết quả.
- Giữ các chiến lược và kiểm tra chất lượng giá mặc định. Bộ lọc học được không
  áp dụng trong lượt tạo dữ liệu, tránh làm lệch tập mẫu theo model cũ.

Kiểm tra lịch sử EURUSD M1/M5 đã được MT4 tải. EA cần 64 nến M5 đã đóng hợp lệ;
đoạn thiếu nến/gap hoặc không có quote đúng mốc có thể bị loại. Không đổi sang
Open prices only/Control points: dữ liệu trong nến là cần thiết cho T+1 và mốc khóa.
Every tick của MT4 cũng có thể là tick được dựng, không phải tick thật; báo cáo
sẽ giữ trạng thái chất lượng tick chưa được chứng thực.

Chạy đến hết đoạn đã chọn. Một tag chỉ dành cho một lượt Tester; muốn thử lại,
dùng tag mới. EA từ chối nối tiếp một bộ lịch sử cũ hoặc chạy Optimization.

Dữ liệu nằm trong sandbox Tester, thường là:

`<MT4 Data Folder>\tester\files\BO_V2\v215_hist_2024_2025_a_TESTER_EURUSD`

Thư mục cần có `data_origin.csv`, `demo_policy.csv`, `event_*.bin` và
`tester_complete.csv` sau khi Tester kết thúc. Nếu không thấy đúng đường dẫn,
kiểm tra vị trí sandbox Tester của terminal; chọn thư mục thực sự có các file trên.
Không chọn nhầm `MQL4\Files` của chart live.

EA không gửi lệnh MT4 trong Tester; hãy xem dữ liệu riêng này, không đánh giá
số tín hiệu qua danh sách Orders/Results mặc định của Tester.

## Đọc Dashboard trong Visual Tester

V2.15 hiển thị giờ mô phỏng (Broker), số tick, số lượt phân tích và số mốc giá
tham chiếu đã ghi. Bộ đếm mô phỏng/WIN/LOSS/TIE/thiếu giá được cập nhật trực tiếp
sau khi nhật ký được ghi thành công; không cần chạy Start-Demo-Learning trong
Tester. Chỉ kết quả tại kỳ hạn đã chọn của tín hiệu thực sự đủ điều kiện vào
mô phỏng được tính; các kỳ hạn tham chiếu khác và tín hiệu đã hủy không được
cộng thành WIN/LOSS. Đây là số liệu Tester, không phải kết quả live forward.

THIEU_NEN_TRONG_LICH_SU có nghĩa chưa đủ 64 nến M5 liên tiếp hợp lệ. Sau cuối
tuần/lễ, cần khoảng 5 giờ 20 phút dữ liệu giao dịch liên tục để cửa sổ lịch sử
không còn chứa khoảng trống. Nếu giờ mô phỏng/tick vẫn tăng thì Tester đang
chạy. Nếu đã qua đủ cửa sổ mà vẫn thiếu, kiểm tra lịch sử M1/M5, tab Journal
và file history_*.csv trong thư mục nhật ký; không tự điền nến hoặc nới bộ lọc.
Các dòng M5/64 và M1/320 cho biết số nến đọc được, không tự chứng minh OHLC hợp lệ.

Tester chỉ tạo dữ liệu. Dòng hướng dẫn sẽ là TRAIN-HISTORY.CMD sau khi chạy
xong; mô hình chưa huấn luyện trong lúc Visual Tester đang chạy.

## 3. Huấn luyện và kiểm tra lịch sử

1. Sau khi Tester dừng, chạy `Train-History.cmd`.
2. Dán đường dẫn chính xác của bộ dữ liệu `_TESTER_EURUSD` ở trên.
3. Python hiển thị tám giai đoạn. Giai đoạn đọc file có phần trăm, số file,
   files/s, dung lượng đã đọc và ETA riêng. Các giai đoạn fit/calibration/test
   chưa đo được phần trăm sẽ báo đang xử lý cùng thời gian đã chạy.
4. Nhật ký tiến trình ở history_logs trong thư mục gói V2.15; đường dẫn được
   in đầu cửa sổ. File sự kiện được kiểm tra và SHA256 ngay trong một lượt đọc.
5. Kết thúc FINISHED chỉ nghĩa đã xử lý xong; xem trạng thái model bên dưới.
   FAILED/CANCELED và thông báo lỗi cũng được ghi vào log.

Đầu ra ở `history_models\<tên bộ dữ liệu>_<thời điểm>` trong thư mục gói:

- `history_report.json`: số mẫu, WIN/LOSS/TIE/thiếu giá và lý do đạt/chưa đạt.
- `history_reference.csv`: các mẫu đủ điều kiện tham chiếu, nhãn backtest riêng.
- `history_model_candidate.json`: ứng viên và thông tin nguồn dữ liệu.
- **`history_model.json` chỉ có khi nhánh tín hiệu cũ vượt điều kiện**, đủ để chuyển sang quan sát live.
- `research_report.json`, `research_reference.csv`, `research_predictions.csv`: tập
  nghiên cứu hướng giá mới, giữ độc lập với WIN/LOSS lệnh.
- `research_model_candidate.json`: model/chi tiết chưa đạt hoặc đã fit.
  `research_model.json` chỉ có khi đủ cổng nghiên cứu lịch sử, vẫn không nhập EA.
- `data_funnel.json/.csv`: các bước loại tín hiệu và loại mẫu nghiên cứu.
- `prepared_history_v211.json.gz`: có thể chọn trực tiếp ở Train-History lần sau,
  không phải đọc lại nhật ký BIN. File được lưu trước khi fit.

Mô hình dùng đoạn đầu để học/scaler, đoạn tiếp theo để hiệu chỉnh xác suất, đoạn
cuối để đánh giá. Ba lát thời gian trong đoạn cuối phải giữ chất lượng ổn định.
Không chia ngẫu nhiên, không chọn ngưỡng sau khi nhìn kết quả, không nội suy giá
entry/expiry để tạo WIN. Có thể cần nhiều hơn một năm nếu tín hiệu hợp lệ thưa.

Nếu báo NOT_QUALIFIED, đọc lý do. Thiếu mẫu thì cần thêm lịch sử hợp lệ. Không
đạt chất lượng thì giữ ứng viên làm nghiên cứu; không tự bật hoặc giảm cổng chỉ
để có model. Không có cam kết rằng lịch sử hiện có sẽ tạo được model đạt yêu cầu.

## 4. Chuyển model tín hiệu cũ đã đạt sang chạy demo

Phần này chỉ áp dụng khi có `history_model.json`. **Không nhập
`research_model.json` hoặc `research_model_candidate.json`**; hai hợp đồng
đặc trưng và nhãn khác nhau. Xem UPGRADE_V215_VI.md về kết quả nghiên cứu/cache.

1. Gắn V2.15 trên **chart EURUSD M5 bình thường**, cùng broker/feed và cấu hình
   với lượt huấn luyện. Load preset Demo_Learning, dùng tag riêng `v215_demo`.
2. Dừng cửa sổ Python live nếu đang chạy; giữ chart MT4 mở.
3. Chạy `Import-History-Model.cmd`, dán file **`history_model.json`**.
4. Nếu được hỏi, dán thư mục live:
   `<Data Folder>\MQL4\Files\BO_V2\v215_demo_EURUSD`.
5. Chạy `Start-Demo-Learning.cmd` và theo dõi chart khi có tick mới.

Việc chuyển sẽ giữ hệ số đã học nhưng tạo model ID và thời điểm bắt đầu live
mới. Dataset lịch sử, WIN/LOSS lịch sử và số tuần backtest không được nhập vào
bộ đếm/live forward. Không cần nhập kết quả Olymp thủ công để mô phỏng MT4.

Model bắt đầu ở **OBSERVE_ONLY**: EA dùng kiến thức đã học để chấm điểm các
tín hiệu nằm trong miền dữ liệu đã học. Tín hiệu vẫn chịu toàn bộ kiểm tra cấu
trúc/T+1/giá. Quyền lọc ML chỉ được mở sau khi dự báo thật do EA ghi trước kết
quả vượt cổng forward; nếu chất lượng giảm thì tạm ngưng như cơ chế hiện có.

Nếu thư mục live đã có một model đang học, chương trình sẽ từ chối ghi đè;
dùng InstanceTag live mới để thử model lịch sử và giữ dữ liệu cũ đối chiếu.
Lịch sử phải kết thúc trước thời điểm live, cùng policy/feed/kỳ hạn. Không sao
chép thủ công CSV/model/state giữa hai môi trường để bỏ qua các kiểm tra này.

## Kiểm tra kết quả của anh

Gói source không kèm model đã học trên toàn bộ lịch sử MT4 của anh. Chỉ có
gói chẩn đoán lấy mẫu đã được kiểm tra, không thể dùng làm tập huấn luyện đầy đủ. Sau lượt chạy đầu, anh có thể gửi `history_report.json`
để đánh giá lượng mẫu/chất lượng; nếu cần kiểm tra nguồn, gửi bộ nhật ký Tester
đã nén. Không gửi mật khẩu hoặc thông tin đăng nhập sàn.
