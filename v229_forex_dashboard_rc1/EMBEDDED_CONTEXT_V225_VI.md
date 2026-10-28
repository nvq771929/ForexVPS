# V2.25 RC1 — phân tích bối cảnh nằm trong EA

Đây là bộ source đầy đủ, phát triển từ V2.24 RC3. **Bối cảnh đa khung và tuổi
xu hướng được tính bằng MQL4 bên trong EA**, không cần CMD, Python, DLL, Ollama
hay API để chạy phần này. EA chưa có mô hình giao dịch được huấn luyện đủ điều
kiện; chưa tự huấn luyện deep learning hoặc tự sửa chiến lược trong EX4.

Tên mới V2.25 giúp giữ nguyên gói V2.24 RC3 đã giao. Thư mục Include
`EURUSD_M5_V224`, indicator V224 và các hợp đồng nhật ký/model cũ được giữ tên
để tương thích; đây không phải yêu cầu cài thêm bản cũ.

## Cài và pilot ngắn

1. Giữ bản cũ và dữ liệu riêng. Dừng Tester trước khi cập nhật source.
2. Giải nén gói vào thư mục mới. Chép nội dung `MQL4` vào Data Folder/MQL4.
3. Compile `Experts/EURUSD_M5_Intelligence_V225.mq4` bằng MetaEditor. Môi trường
   phát triển chưa có MetaEditor; gói chỉ chứa source, chưa có EX4 đã kiểm tra.
4. Strategy Tester: EURUSD hoặc EURUSDz của nguồn lịch sử đang dùng, M5,
   Every tick, Optimization OFF, Visual Mode OFF khi chạy đo kết quả.
5. Lượt pilot đề nghị: **13/04/2026–16/04/2026**, To là ngày kết thúc loại trừ.
   Load `EURUSD_M5_V225_Embedded_Pilot_UTC0.set`. UTC+0 đã được anh xác nhận
   cho lịch sử này. Dùng InstanceTag mới mỗi lượt, ví dụ `v225_embedded_pilot_01`.
   Preset tắt Forex và tư vấn tác động tín hiệu, hạn Binary vẫn 5 phút.
6. Không cần mở CMD learner/AI cho pilot phần nhúng. Nếu cần xem panel trong
   Tester, chạy thêm lượt Visual Mode ngắn với tag khác; đổi tag mỗi lượt.
7. Sau khi hoàn tất, lưu report HTM, Journal và nén nguyên thư mục
   `tester/files/BO_V2/v225_embedded_pilot_01_TESTER_<symbol>` để đối chiếu.
   Có thêm `embedded_context_v225_<session>.csv` bên cạnh nhật ký gốc.

Preset `EURUSD_M5_V225_Binary_Fresh.set` giữ phần nhúng OFF để đối chứng. Muốn
so sánh ON/OFF trên MT4 cần hai lượt cùng ngày, feed, spread và Inputs chiến lược,
tag khác nhau. So sánh hướng, setup, LOCK, công bố, hủy và outcome theo mốc thị
trường; tên session và tag tự nhiên khác nhau. Pilot này kiểm chứng cài đặt,
thời gian và tính độc lập, chưa chứng minh lợi thế giao dịch.

## Inputs

| Input | Mặc định | Ý nghĩa |
|---|---:|---|
| EnableEmbeddedContext | false | Bật bộ phân tích nhúng; chỉ quan sát |
| EmbeddedBrokerClockVerified | false | Người dùng xác nhận múi giờ của đúng nguồn/giai đoạn |
| EmbeddedBrokerUTCOffsetMinutes | 0 | UTC+0 là 0; UTC+2 là 120, UTC+3 là 180 |
| EmbeddedBootstrapM5Bars | 4800 | Tối đa 4800 vị trí nến M5 trước lúc gắn; 0 là không bootstrap |
| EmbeddedPanelLeft / Top | 570 / 260 | Vị trí panel 4 dòng, tránh che panel tín hiệu |

Không dùng giờ máy/TimeGMT để đoán múi giờ Tester. Nếu lịch sử chuyển offset
giữa kỳ, chia lượt ở ranh giới offset; bản RC1 chưa nhận lịch DST theo ngày.
Xác nhận UTC+0 trong lịch sử không tự xác nhận offset cho live ngày khác.

## EA phân tích gì?

- M5 đã đóng, gom đúng đủ 3/12 nến thành M15/H1 theo đồng hồ UTC đã xác minh.
- EMA20/EMA50, độ dốc, ATR hiện tại/trước đó, độ hiệu quả chuyển động và vùng
  hỗ trợ/kháng cự từ pivot đã xác nhận. Không dùng nến tương lai.
- UP/DOWN cần M15 và H1 đồng thuận qua hai lần đóng M15; RANGE cần thêm hai
  biên giá hợp lệ. Chưa rõ trả UNCERTAIN, thiếu dữ liệu trả UNKNOWN/COLLECTING.
- FORMING/CONTINUING/EXTENDED/WEAKENING mô tả cấu trúc đang quan sát. Cờ suy yếu
  gồm xung đột khung, mất động lượng, giảm độ dốc và gần vùng cản đối diện.

**Tuổi** là số phút từ lúc quy tắc xác nhận xu hướng, có thể hình thành trong
bootstrap lịch sử. Đây không phải thời điểm khởi đầu thật của xu hướng, phần
trăm vòng đời, thời gian còn lại hoặc xác suất CALL/PUT thắng. Bản này không
nhúng bảng xác suất tuổi, trọng số model hay bộ lọc veto 30 phút. Bối cảnh
nghiên cứu trước đây chưa đủ bằng chứng để đổi tín hiệu.

## Dữ liệu, khởi động lại và nhật ký

Khi gắn EA, một lần CopyRates có giới hạn lấy nến M5 đã đóng để làm ấm. Cửa sổ
4800 vị trí M5 chỉ khoảng 16,7 ngày lịch, có thể thiếu nến do cuối tuần hoặc nguồn
history chưa tải. Cần ít nhất 150 nến M15 và 150 nến H1 hoàn chỉnh. Thiếu thì
tiếp tục COLLECTING, không tạo tuổi giả. Nến đang chạy bị loại.

Sau khởi tạo, bộ nhúng chỉ đọc cache M5 mà EA đã có; không tự gọi thêm CopyRates
trong OnTick/OnTimer. Xử lý LOCK/ENTRY/OUTCOME gốc trước, hoãn tính/ghi observer
ở vùng sát các mốc. Không có tải mô hình, API hay huấn luyện trong phần này.
Nhật ký lưu `asof_utc_ms` và `available_broker_ms` riêng: lịch sử replay không
được coi là dự báo live tại thời điểm quá khứ. Bootstrap chỉ tạo snapshot hiện
tại, không ghi hàng nghìn dự báo lịch sử giả.

Gắn lại EA sẽ tái khởi tạo từ cửa sổ lịch sử mới; EMA có thể khác một ít vì điểm
seed khác, tuổi có thể được xác nhận lại. Đây chưa phải checkpoint giữ nguyên
trạng thái qua restart. Seed và số nến bootstrap có trong từng dòng nhật ký.
Không ghép hai phiên chạy như một chuỗi dự báo liên tục.

STALE nghĩa là dữ liệu của observer đã chậm ít nhất một M5 hoặc đồng hồ đi lùi;
CLOCK_UNVERIFIED nghĩa là chưa xác minh offset. Nếu broker sửa nến đã tiêu thụ
trong phần lịch sử còn đối chiếu được, HISTORY_CHANGED_REATTACH dừng riêng
observer đến khi gắn lại. OBSERVER_IO_ERROR là lỗi ghi nhật ký mới; không xóa
nhật ký giao dịch gốc hay thay quyết định của EA. Không có cơ chế bảo đảm phát
hiện sửa lịch sử nằm ngoài cửa sổ lưu trong bộ nhớ.

## Phần nào vẫn cần tiến trình ngoài?

| Khả năng | Bên trong EX4 bản này |
|---|---|
| Bối cảnh M5/M15/H1, cờ suy yếu, tuổi từ xác nhận, panel | Có |
| Thay tín hiệu bởi bộ phân tích mới | Không, chỉ quan sát |
| Deep learning: huấn luyện, kiểm định, chọn và phát hành model mới | Vẫn bên ngoài |
| Tổng hợp kinh nghiệm/nguyên nhân thua, dashboard học mỗi ngày | Supervisor bên ngoài |
| Giải thích ngôn ngữ/Ollama tùy chọn | Trợ lý bên ngoài |
| Cấp lịch tin kinh tế | Worker tin tức bên ngoài như trước |

Các công cụ và chức năng Forex kế thừa vẫn có đầy đủ. Phần nhúng mới chỉ nằm
trên nhánh Binary; không thay quản trị lệnh Forex. File indicator V224 là màn
hình supervisor bên ngoài, không bắt buộc cho panel nhúng. Không cần bật nó
chỉ để xem bối cảnh/tuổi.

## Kiểm tra đã có trong gói

`validation/embedded_parity.json` đối chiếu trực tiếp code MQL4 với engine
Python RC1 đóng băng trên hai chuỗi 36.077 và 9.536 nến. Các trường rời rạc
phải giống tuyệt đối; số thực có sai số 1e-10 tương đối / 1e-12 tuyệt đối.
Đây là kiểm thử C++ shim của source MQL4, không phải compile MetaEditor hoặc
chạy MT4 Windows. Các kiểm thử tích hợp bật/tắt còn so sánh byte nhật ký gốc,
input và công bố, kiểm tra clock UNKNOWN và nguồn BACKTEST riêng.

Bước kế tiếp sau pilot là xem độ trễ, độ ổn định qua restart và đối chiếu bối
cảnh với chart. Việc cho model can thiệp cần quy trình kiểm định riêng; gói
này không tự kích hoạt lại một model/bộ lọc chưa đạt nghiên cứu.
