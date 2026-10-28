> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# Trao đổi EA – bộ học trước khóa: V2.24 Full RC2

Đã triển khai cho **Binary Option**. Forex giữ nguyên bộ xử lý của V2.23 và
chưa dùng mô hình Binary để quyết định giao dịch.

## Quy tắc chốt

EA tạo ứng viên theo chiến lược và điều kiện gốc, gửi ảnh chụp dữ liệu trong
nến T+1. Bộ học trả KEEP (giữ hướng EA), WAIT hoặc ABSTAIN (chưa tư vấn).
EA kiểm tra lại điều kiện bắt buộc rồi chốt một lần tại thời điểm khóa.

**Thiếu phản hồi, quá hạn, sai lượt, quá cũ, không đủ kiểm định, lệch đồng hồ,
lỗi giao tiếp hoặc bối cảnh đã thay đổi đáng kể: EA giữ quyết định riêng.**
Quy tắc này thay cho đề xuất cũ coi mọi lỗi tư vấn là WAIT.

- Bộ học chỉ có thể đề nghị giữ hướng hoặc chặn thành WAIT. Không đảo CALL
  thành PUT, không tạo CALL/PUT từ WAIT của EA, không vượt qua guard dữ liệu,
  cấu trúc, xác nhận, quote, tạm dừng hay các bộ lọc native hiện có.
- Sau khóa, phản hồi đến muộn không được đọc để đổi tín hiệu. Điều kiện dữ
  liệu và kiểm tra ENTRY gốc vẫn chạy; sổ tín hiệu đã phát vẫn được giữ như
  V2.23, kể cả khi ENTRY kỹ thuật bị hủy. Tư vấn không rút lại tín hiệu đã phát.
- Không chờ Python trong OnTick/OnTimer. Chốt khóa chỉ dùng bộ nhớ đệm;
  không đọc file, gọi mạng, huấn luyện hay Sleep tại bước chốt.
- Mỗi yêu cầu gắn session/lượt, cấu hình, feed, policy, hướng, chiến lược,
  thời hạn, horizon và checksum snapshot. Phản hồi phải khớp đúng yêu cầu mới
  nhất; phản hồi cho yêu cầu cũ không thay thế yêu cầu mới đang chờ.
- Nếu giá đã lệch hơn 0,25 ATR so với snapshot, hoặc hướng/chiến lược/bối
  cảnh/trạng thái xác nhận đổi, tư vấn bị bỏ qua. Đây là guard thử nghiệm đã
  định trước, chưa phải ngưỡng tối ưu đã chứng minh.

## Input mới

| Input | Mặc định | Ý nghĩa |
|---|---:|---|
| `EnableBinaryLearningDialogue` | false | Bật/tắt gửi yêu cầu và nhận tư vấn |
| `BinaryLearningAdviceAffectsSignals` | false | Cho phép WAIT hợp lệ của mô hình đủ kiểm định chặn ứng viên |
| `BinaryLearningRequestIntervalSeconds` | 30 | Khoảng cách các lần cập nhật yêu cầu |
| `BinaryLearningReplyMaxAgeSeconds` | 30 | Tuổi tối đa của snapshot khi dùng tư vấn |
| `BinaryLearningReserveBeforeLockSeconds` | 5 | Ngừng trao đổi trước khóa để EA tự kiểm tra và chốt |

Hai cờ mặc định OFF. Bật trao đổi nhưng để tác động OFF thì chỉ quan sát.
Bật tác động cũng không đủ để can thiệp nếu thiếu mô hình/biên nhận kiểm định.
Đổi các Input khi hết lượt đang theo dõi; việc đổi Input khiến MT4 khởi tạo lại
EA và vẫn chịu quy tắc phục hồi của EA gốc.

## Ví dụ thời gian với cấu hình mặc định

Với nến T+1 từ **09:00 đến 09:05, giờ server**:

- Sau khi có snapshot và qua 15 giây đầu, EA có thể bắt đầu gửi yêu cầu.
- Các yêu cầu cập nhật theo chu kỳ, chỉ khi có ứng viên và quote còn đủ mới.
- Việc nhận tư vấn dừng **trước 09:04:23**.
- EA chốt theo lịch gốc khoảng **09:04:28**, tức trước mốc vào 32 giây.
- Mốc tham chiếu vào là **09:05**, hết hạn **09:10** nếu horizon 5 phút.

Đây là ví dụ mốc kế hoạch, không bảo đảm phản hồi luôn kịp. Mỗi yêu cầu còn có
hạn riêng, có thể sớm hơn; mọi phản hồi phải được nhận thực tế trước hạn đó.
Phản hồi đến sau thời hạn không làm EA chờ thêm. Clock/quote guard gốc vẫn
có quyền khiến quyết định riêng của EA là WAIT.

## Đường giao tiếp

Chạy `Install-Learning-Supervisor.cmd` một lần, rồi `Start-Learning-Dialogue.cmd`.
Nhập thư mục nhật ký LIVE của EA V2.24, độ lệch UTC đã xác nhận và, nếu có,
file mô hình **pre-lock** cùng biên nhận kiểm định. Chưa có mô hình thì Enter:
worker thu dữ liệu và trả ABSTAIN khi đồng hồ hợp lệ; EA tự quyết định.

Worker đọc snapshot native có FNV và ghi duy nhất phản hồi riêng tương ứng
trong `advisory_v224/<session>/reply_*.csv`. Nó không sửa BIN chính, file input,
cấu hình hay model import của EA. EA ghi `final_*.csv` sau khi đã chốt để bộ
học biết quyết định gốc và quyết định cuối. Worker lưu biên nhận đó để đối soát.
Giữ một worker tư vấn cho mỗi nguồn. Không cần mở cửa sổ chat hay gọi dịch vụ AI.

Đồng hồ chưa xác nhận thì chỉ thu thập. Không dùng việc UTC+0 đã xác nhận cho
lịch sử để tự suy ra UTC offset live. Đồng hồ máy Windows cần đồng bộ đúng giờ.

## Dữ liệu/mô hình trước khóa là nhánh riêng

`V224_PRELOCK_DIALOGUE_FEATURES_V1` dùng 40 đặc trưng tại lúc hỏi, 50 đặc trưng
bối cảnh và, khi đủ, chuỗi 32×29 nến đóng đã quan sát. Không giả lập cờ LOCK
để gọi decoder LOCK cũ, không dùng giá tương lai hay kết quả để tạo đặc trưng.

Mô hình RC1 học tại LOCK không được dùng cho tư vấn trước khóa. Dữ liệu V2.23
hiện tại vẫn dùng để nghiên cứu/đánh giá tín hiệu theo kế hoạch; nó chưa có
snapshot yêu cầu pre-lock nên không được đổi nhãn thành dữ liệu tư vấn mới.

Lượt Tester V2.24 với preset `EURUSD_M5_V224_Binary_Dialogue_Tester.set` ghi
các snapshot này. Tester **không dùng phản hồi worker để thay đổi quyết định**,
kể cả khi cờ tác động ON, nhằm giữ khả năng kiểm tra lịch sử nhất quán.
Không cần ngừng lượt V2.23 đang chạy; có thể chạy một lượt pilot V2.24 sau đó.
Every Tick trong MT4 Tester vẫn là tick do Tester mô hình hóa từ lịch sử;
không coi nó là bằng chứng dự báo live trên tick thực.

```bat
cd /d "D:\EA_V224_Full\LearningSupervisor"
.venv\Scripts\python.exe run_dialogue.py prepare --source "D:\Data\v224_prelock_test01_TESTER_EURUSD" --output "D:\Research\PrelockPilot" --broker-utc-offset-minutes 0
.venv\Scripts\python.exe run_dialogue.py train --source "D:\Data\v224_prelock_test01_TESTER_EURUSD" --output "D:\Research\PrelockPilot" --broker-utc-offset-minutes 0
```

Lệnh train chỉ dùng một snapshot hợp lệ cuối cùng trước hạn cho mỗi lượt,
chọn theo thời gian trước khi nhìn kết quả; không đếm chín yêu cầu cùng một
nến thành chín mẫu độc lập. Nhãn là kết quả BID ở mốc vào/hết hạn cố định của
hướng yêu cầu, gồm cả ứng viên không thành tín hiệu chính thức. Đây là nhánh
nghiên cứu ứng viên riêng, không trộn với sổ tín hiệu chính thức của supervisor.
Thiếu tick trong cửa sổ hai giây thì UNAVAILABLE; không nội suy nến hay điền
giá bằng snapshot. Cần đủ train/calibration/evaluation 400/100/150 lượt có đủ
đặc trưng, chia theo thời gian và embargo; thiếu thì COLLECTING, không tạo model.

Mô hình thử Logistic và TCN, chọn bằng calibration sau chọn epoch trong train.
Evaluation chỉ đánh giá sau khi đã chọn. Thí nghiệm được đóng băng; đợt mới
cần thêm dữ liệu, khoảng cách thời gian và phần evaluation mới. Ngưỡng 0,60
là quy ước nghiên cứu, chưa phải ngưỡng lợi nhuận được chứng minh.

## Kiểm định trước khi bật tác động

Trước hết chạy mô hình cố định trong chế độ quan sát live. Đánh giá cần dự báo
được ghi bền vững trước hạn, **EA thực sự nhận trước hạn**, chốt native khớp
biên nhận, và kết quả tick chỉ xuất hiện sau hết hạn. Giữ cùng output của
worker để lưu đầy đủ sổ bằng chứng; mỗi nguồn dùng output riêng.

```bat
.venv\Scripts\python.exe run_dialogue.py validate --source "D:\Data\LiveJournal" --output "D:\Research\LiveDialogue" --broker-utc-offset-minutes 0 --model "D:\Research\Models\prelock_model_HASH.json"
```

Lệnh này tạo `forward_validation.json` và báo cáo tiêu chí. Cần ít nhất 150
lượt độc lập quyết định được, 8 tuần, 100 lượt được chọn, coverage 20%, Brier
và Log loss tốt hơn xác suất cơ sở train. Đó là điều kiện cần để xét cho tư vấn;
không phải xác nhận lợi nhuận hoặc cam kết thắng. Dữ liệu này không xét thao
tác thủ công hay kết quả Olymp Trade.

Worker không tin một cờ `validated=true`: nó tính lại tiêu chí và đối chiếu
từng dòng với sổ dự báo của chính worker, biên nhận EA/BIN LOCK và tick đã
đối soát. Chỉ có JSON ghi số liệu đẹp mà thiếu bằng chứng thì bị từ chối.
Khi đủ bằng chứng và đã đánh giá, khởi động lại worker với `--forward-receipt`
và mới bật cờ tác động. Chưa kịp bất cứ bước nào, EA vẫn dùng quyết định riêng.

## Dashboard và kiểm thử

EA hiển thị gọn hai dòng: chế độ trao đổi và kết luận hiện tại. Các mã yêu cầu,
timestamp, checksum, model ID, nội dung hỏi/đáp và biên nhận nằm trong nhật ký
và `dialogue_status.json`, không dàn hết lên chart. Panel indicator của nhánh
supervisor đánh giá tín hiệu chính thức hiển thị trạng thái của chính nhánh đó;
quyền tư vấn pre-lock xem trên EA và trạng thái worker tư vấn.

Gói không kèm model thị trường hay biên nhận đủ kiểm định. Đã kiểm thử source
dưới C++ MT4 API shim và Python, chưa compile MetaEditor hay chạy Windows MT4.
Cần pilot trên máy anh để kiểm tra compile, độ trễ IO và clock trước khi dùng
tác động. Không có phép đo tài nguyên/độ trễ MT4 trên máy anh trong gói này.
