# V2.28 phục hồi từ source V2.26 — Demo và Real

Ngày phục hồi: 28/10/2026. Expert: `EURUSD_M5_Intelligence_V228.mq4`.
Đây là bản xây dựng lại theo bản bàn giao, **không phải ZIP V2.28 cũ** và chưa
được xác nhận giống từng byte với bản đã mất. Không dùng số kiểm thử hoặc mã
băm V2.28 cũ làm bằng chứng cho bản này.

## Nguồn và phạm vi

Ba phần ZIP V2.26 được tải lại, ghép theo thứ tự .001/.002/.003 và kiểm tra CRC.
ZIP ghép có SHA256:
`7e3ffb5d2739a199295613ebc10fbf24c7bc171323175b42387c8c391f6770ce`.
Manifest có 393 mục; 392 khớp. Expert MQL4 khác bản mt4 ở đúng hai điều kiện
khởi tạo: chỉ bắt buộc chart M5 khi chạy Tester. Bản phục hồi áp dụng hai thay
đổi này cho cả hai cây source. Windows virtualenv trong ZIP gốc không được tái
sử dụng hoặc đóng gói; cài lại từ requirements đã ghim.

Các phần được khôi phục:

- ChartFix1: live có thể đổi khung hiển thị; phân tích vẫn lấy M5. Tester vẫn
  phải chạy M5. MT4 vẫn khởi tạo lại EA khi đổi khung, không phải tiếp tục nguyên
  một lượt chuẩn bị cũ.
- Quan sát đồng hồ: hợp đồng `V227_CLOCK_OBSERVATION_V1`, file
  `clock_observation_v227_*.csv`. Ghi mọi tick bị từ chối và tối đa một tick được
  chấp nhận mỗi giây broker. Lưu thời gian quote/server/PC, monotonic và trạng
  thái đồng hồ trước/sau. Không sửa `Clock.mqh`, không nới ngưỡng hai giây, không
  kết luận nguyên nhân TIME_ANOMALY. Tắt ghi bằng `RecordClockObservation=false`.
- Vai trò riêng từng chart: ledger có checksum/chaining trong `EA_MODE_V228`.
  Chart Binary độc lập được khởi tạo khi Forex có vị thế. Chart đã làm Forex
  không được chuyển sang Binary hoặc đổi symbol/magic khi còn vị thế thuộc
  trách nhiệm cũ. Ledger hỏng hoặc thiếu phần cuối chặn khởi tạo. **Không xóa
  state để bỏ qua cảnh báo.** Khóa tài khoản/họ EURUSD của Forex giữ nguyên.
- Bốn preset Demo/Real đầy đủ, tách tag và nhật ký Binary/Forex.

Toàn bộ 37 Include V2.26 được giữ nguyên từng byte. Expert dùng alias tiền xử lý
chỉ quanh include `ForexEngine.mqh` để bọc lời gọi `BOClockTick` thành
`BOObservedClockTick`, rồi bỏ alias ngay sau include. Lớp bọc chỉ quan sát;
`Clock.mqh` và `ForexEngine.mqh` giữ đúng hash trong `baseline_v226_sha256.json`.
Thêm hai header
`ChartRoleV228.mqh` và `ClockObservation.mqh`; không đổi chiến lược, ATR,
POD/feature/model, lock/freshness, rủi ro, tin tức, SL/TP hoặc bình quân giá.

## Cài trên MT4 Windows

1. Giải nén vào một thư mục mới, giữ bản đang chạy và nhật ký để đối chiếu.
2. MT4 → File → Open Data Folder. Chép nội dung thư mục `MQL4` trong gói vào
   Data Folder/MQL4. Namespace `EURUSD_M5_V224` là chủ ý tương thích; không đổi tên.
3. Mở và compile `Experts/EURUSD_M5_Intelligence_V228.mq4` trong MetaEditor.
   Gói cloud này chưa có EX4 và chưa được compile bằng MetaEditor.
4. Dùng hai chart riêng, chuẩn M5. Binary dùng EURUSD nếu broker cung cấp đúng
   symbol đó; Forex theo yêu cầu dùng EURUSDz, viết liền. Chỉ dùng symbol thực
   sự có trên tài khoản; cả hai chart chia sẻ Balance/Equity/margin của MT4.
5. Nạp đúng cặp preset tương ứng:

| Tài khoản | Binary | Forex |
|---|---|---|
| Demo | `EURUSD_M5_V228_Binary_Demo_Observe_UTC0.set` | `EURUSD_M5_V228_Forex_Demo_Execute_UTC0.set` |
| Real | `EURUSD_M5_V228_Binary_Real_Observe_UTC0.set` | `EURUSD_M5_V228_Forex_Real_Execute_UTC0.set` |

Tên UTC0 biểu thị cấu hình giờ/schedule dự kiến, không chứng minh tài khoản mới
đang dùng UTC+0. Đối chiếu giờ server trước; `EmbeddedBrokerClockVerified=false`
trong cả bốn preset. Chỉ xác nhận cờ này và offset sau khi đã đối chiếu thực tế.
Nếu giờ broker khác UTC+0, phải rà cả rollover/Friday schedule theo giờ broker;
đổi riêng offset bộ quan sát không tự chuyển các giờ schedule Forex.

Preset Binary tắt Forex, đối thoại, tác động tư vấn và bộ lọc học đã xác thực;
bộ quan sát nhúng chỉ ghi nhận, không tự sửa CALL/PUT. Preset Forex bật quản lý
lệnh, rủi ro 0,5% × min(Balance, Equity), lỗ Equity ngày 2%, SL 6–30 pip, TP 2R,
spread tối đa 1,5 pip, giữ lệnh tối đa 60 phút, BE/trailing bật, bình quân giá tắt.
Preset Forex Real đặt `ForexAllowRealTrading=true`; mặc định trong mã EA vẫn là
false. Với quyền MT4 bật và mọi điều kiện đạt, preset Real có thể tự mở lệnh,
kể cả sau khi nạp tiền vào tài khoản ban đầu có Balance 0.

Balance 0 chặn mở mới kể cả có credit/Equity dương; không tắt quản lý vị thế còn
tồn tại. Không dùng Binary để quản lý thay Forex. Máy/EA phải hoạt động để chạy
trailing, xử lý tin và giới hạn thời gian giữ; broker SL/TP không thay thế chúng.

## Công cụ ngoài EA

- Cài Python 64-bit và chạy `Install-Demo-Learning.cmd` cho bộ công cụ cơ bản.
  Nghiên cứu deep learning là tùy chọn; không tự huấn luyện hoặc bật model.
- `Start-Candidate-Research.cmd`: nhập chính xác đường dẫn nhật ký **Binary**
  của chart đang dùng, không nhập nhật ký Forex hoặc toàn bộ thư mục nhiều tag.
- `Start-Forex-News.cmd`: nhập MT4 Data Folder; cập nhật bridge riêng
  `MQL4/Files/FX_V222/news_calendar.csv`. Nguồn HTTPS hiện dùng
  `nfs.faireconomy.media/ff_calendar_thisweek.json`. Công cụ không gửi lệnh.
- Tin Forex thiếu/cũ/không xác thực được phải chặn Entry; không tắt lọc để làm
  pilot có giao dịch. Tin/phiên Binary vẫn quan sát độc lập.
- LearningSupervisor và AI cục bộ được giữ nguyên. Không có model thị trường
  mới, API trả phí hoặc quyền mới cho bộ học can thiệp giao dịch.

## Kiểm chứng và các giới hạn

Trong cloud Linux, dùng Python 3.12+, requirements-deep.txt và g++17:

```sh
python -m unittest discover -s tests -v
cd LearningSupervisor
python -m unittest discover -s tests -v
```

Kết quả của **lượt phục hồi này** nằm trong `validation/tests.txt`,
`validation/learning_tests.txt` và `RELEASE_STATUS.json` của ZIP phát hành.
Các tài liệu/receipt mang tên V226 hoặc phiên bản cũ là bằng chứng kế thừa,
không phải kiểm thử vừa chạy lại. Chưa có dữ liệu corpus lịch sử gốc để chạy lại
audit thị trường; không suy diễn từ fixtures sang hiệu quả Exness.

Kiểm thử MQL chạy qua C++ shim và API/file/broker giả lập; chưa phải MetaEditor,
Windows MT4, hiển thị Dashboard thật, live news, hoặc đánh giá lợi nhuận.
TIME_ANOMALY mới có thêm quan sát, chưa được xác định nguyên nhân hoặc sửa chữa.

Sau compile đạt, pilot vận hành hai chart trên Demo trước: thử hai thứ tự gắn,
restart từng chart, đổi khung hiển thị, kiểm tra tách nhật ký và bảo toàn state.
Kiểm tra Forex manager thứ hai bị chặn. Không cần chạy lại 12 tháng để xác nhận
đóng gói/hai chart. Kết quả Binary đọc từ nhật ký tín hiệu; report MT4 Total
trades=0 có thể đúng thiết kế. Tester/forward, Binary/Forex, Demo/Real và các
nguồn lịch sử khác nhau phải tiếp tục được tách riêng.

Đóng gói chỉ sau hai suite đạt, không skip:

```sh
python tools/package_release.py --validation-log /path/root-tests.log \
  --learning-validation-log /path/supervisor-tests.log \
  --output-directory /path/fresh-release-folder
```

Kiểm tra SHA256 ZIP và toàn bộ manifest sau giải nén. Việc tạo ZIP hoặc snapshot
cloud không đồng nghĩa đã push lên GitHub; trạng thái sao lưu remote phải có
commit SHA và kiểm tra remote riêng.
