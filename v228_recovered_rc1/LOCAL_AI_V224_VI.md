> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# V2.24 Full RC3 — Trợ lý AI chạy cục bộ

Đây là bộ source đầy đủ dựa trên V2.24 Full RC2, bổ sung trợ lý quan sát và kết nối tùy chọn tới mô hình ngôn ngữ trên máy. Theo yêu cầu ngày 24/10/2026, vẫn giữ tên EA V2.24 vì anh chưa compile/pilot V2.24. Các gói RC2 và V2.23 đang chạy được giữ riêng.

**Không thay lượt Tester V2.23 đang chạy 01/04–16/05/2026.** Hoàn tất lượt đó và lưu dữ liệu trước khi compile/pilot bộ này. Không cần chạy lại sáu tháng chỉ để đọc dữ liệu cũ.

## Phần mới đã có và phần chưa có

| Thành phần | Trạng thái |
|---|---|
| EA, Include, Presets, Indicators và các bộ học V2.24 | Có trong bộ đầy đủ; không cần cài source V2.23 trước |
| Trợ lý đọc BIN có FNV/sequence và anchor CSV của nguồn | Đã triển khai; chỉ đọc nguồn, ghi báo cáo riêng |
| Bối cảnh đa khung, độ biến động, tuổi từ lúc xác nhận | Tích hợp nguyên engine RC1 đã đóng băng; là quy tắc nghiên cứu |
| Giải thích theo dữ kiện, đề xuất câu hỏi nghiên cứu, tiến triển số nến theo ngày | Đã triển khai; không biến thống kê thành điều kiện vào lệnh |
| Kết nối Ollama cục bộ | Có adapter và cấu hình tùy chọn; mặc định OFF, chỉ địa chỉ IP loopback |
| Mô hình ngôn ngữ/weights Ollama | Chưa kèm; cần mô hình đã cài trên máy để bật phần lựa chọn của LLM |
| Mô hình dự báo WIN/LOSS 30 phút đủ kiểm định | Chưa có; không cấp xác suất giả hoặc kích hoạt model cũ 5 phút |
| LLM ra lệnh cho EA hoặc ghi reply tư vấn | Không có đường ghi đó trong trợ lý mới |
| MetaEditor/Windows MT4 và mô hình Ollama thật | Chưa kiểm chứng trong môi trường phát triển; cần pilot trên máy vận hành |

Logistic/TCN của các nhánh bộ học kế thừa vẫn là học máy. Trợ lý mới không tự huấn luyện sau từng WIN/LOSS, không thay trọng số đang dùng, không dùng model Binary cho Forex. Chất lượng thị trường chưa được cải thiện hoặc chứng minh chỉ nhờ tích hợp này.

## Cách hoạt động

1. Trợ lý đọc `demo_policy.csv`, `data_origin.csv`, từng BIN theo đúng sequence và các anchor tương ứng. Đối chiếu magic/schema/POD/FNV, cấu hình, OHLC, nến đã đóng và timestamp trước khi dùng.
2. Từ các nến có trong ảnh chụp, phát lại engine RC1 cố định. Nến trùng phải khớp; nến đến muộn không được chèn để viết lại bối cảnh đã ghi. Không nội suy khoảng trống.
3. Engine phân biệt hướng với volatility; cần **150 H1 hoàn chỉnh thực tế** và đủ M15/M5 để sẵn sàng. Một anchor 64 nến không đủ khởi tạo H1. UNKNOWN trong những ngày đầu có thể là đúng; báo cáo ghi rõ đếm nến còn thiếu.
4. Trợ lý tạo danh sách dữ kiện có bằng chứng: bối cảnh, tuổi đã xác nhận, cờ suy yếu, biến động, ứng viên/LOCK native và trạng thái năng lực. Không đọc kết quả tương lai để giải thích snapshot đó.
5. Khi không bật Ollama, báo cáo dùng các câu mô tả dữ kiện cố định và ghi `LOCAL_MODEL_NOT_CONFIGURED`. Đây không phải một LLM đã hoạt động.
6. Nếu bật một mô hình cục bộ, mô hình chỉ chọn **mã dữ kiện** và **mã câu hỏi nghiên cứu**. Bộ hiển thị diễn đạt lại bằng câu đã gắn với dữ kiện, không sử dụng câu văn, xác suất hoặc lệnh tự sinh. Mã bịa, trùng hoặc trường CALL/PUT/probability ngoài hợp đồng bị từ chối.
7. Tối đa một lượt lựa chọn cho dữ kiện mới sau khoảng chờ cấu hình, mặc định 300 giây; không gọi theo từng tick, không gọi khi đang đọc bù nhật ký. Trợ lý ở tiến trình riêng nên EA không phải đợi LLM tại mốc khóa.

`observed_age_minutes` là tuổi kể từ xác nhận của công cụ trên chuỗi nến đã đóng, không phải biết thời điểm bắt đầu thật hoặc phần trăm chu kỳ. Các nến lookback được nhận ở anchor hiện tại có thời điểm khả dụng riêng; phát lại lịch sử không được tính là dự báo live đã ghi trước đó. Các view của trợ lý được đánh dấu không đủ điều kiện làm đặc trưng model tư vấn hiện tại.

Engine có hợp đồng nội bộ `V225_MTF_CONTEXT_OBSERVER_RESEARCH_V1` được giữ nguyên để bảo toàn nhận dạng RC1; đây không phải đổi tên bản EA thành V2.25. Giao thức tư vấn V2.24 kế thừa và feature contract vẫn tách riêng.

## Cài và xem trước sau khi V2.23 chạy xong

1. Giải nén bộ RC3 vào thư mục mới, giữ bản cũ và dữ liệu nghiên cứu.
2. Chép `MQL4/Experts`, `Include`, `Presets`, `Indicators` vào đúng Data Folder. Compile `EURUSD_M5_Intelligence_V224.mq4` và `BinaryLearningMonitor_V224.mq4` trong MetaEditor. Không có EX4 biên dịch sẵn trong gói.
3. Dùng preset Binary fresh để pilot; giữ `EnableBinaryLearningDialogue=false` và `BinaryLearningAdviceAffectsSignals=false` ở lượt thử trợ lý. Trợ lý không cần bật hai cờ này để đọc dữ kiện.
4. Chạy `Install-Local-AI-Assistant.cmd` để tạo môi trường `.venv-ai` riêng bằng Python 3.11+. Trợ lý mới chỉ dùng thư viện chuẩn Python. Bộ học Logistic/TCN kế thừa có installer `Install-Learning-Supervisor.cmd` riêng khi cần dùng. Ollama/model được cài riêng ở bước tùy chọn; script trợ lý không tự tải chúng.
5. Chạy `Start-Local-AI-Assistant.cmd`: nhập thư mục nhật ký **LIVE Binary**, UTC offset live đã xác minh, channel riêng và tùy chọn đường dẫn Common Files/config local. Với tài khoản/symbol `EURUSDz`, dùng đúng thư mục và chart có hậu tố đó; không trộn với nguồn `EURUSD`.
6. Nếu chỉ muốn giải thích dữ kiện, Enter ở config. Nếu chưa xác minh offset live, Enter ở offset: chỉ thu thập và báo chưa có bối cảnh; không suy giờ live từ xác nhận UTC+0 của một giai đoạn lịch sử.
7. Mở `LearningSupervisor/runtime/assistant/<channel>/assistant_dashboard.html`. Nếu muốn xem vài dòng trên MT4, gắn indicator `BinaryLearningMonitor_V224`, bật `ShowLocalAIAssistant=true` và đặt `AIAssistantChannel` giống CMD.

Thư mục **Common Files** là `.../MetaQuotes/Terminal/Common/Files`, khác `MQL4/Files` của từng terminal. Trợ lý chỉ ghi `V224Assistant/<channel>/status.csv` và tệp xác nhận chủ sở hữu trong Common Files, không ghi vào nhật ký EA. Mỗi nguồn/output dùng channel riêng; không tái sử dụng channel đã gắn với nguồn khác. Indicator kiểm tra symbol/channel/nguồn/khung M5 và tuổi heartbeat; dữ liệu cũ hoặc sai nguồn được cảnh báo.

Dashboard chung, phần Binary, Forex và News của EA vẫn giữ chức năng kế thừa. Khối AI chỉ hiển thị trạng thái mô hình, bối cảnh/tuổi và đề xuất ngắn; chi tiết và bằng chứng nằm trong HTML. Việc đếm thêm nến là tiến triển dữ liệu, không phải điểm thông minh hoặc bằng chứng thắng nhiều hơn.

## Bật mô hình Ollama tùy chọn

Cài Ollama và một model phù hợp RAM/CPU của máy ở bước pilot sau; không cần GPU mặc định, nhưng tốc độ và bộ nhớ phải đo thực tế. Mô hình chạy hoàn toàn trên máy phải có weights đã cài, không dùng các model có tên cloud hoặc dịch vụ trung gian.

Sao chép `LearningSupervisor/local_ai.example.json` ra một file config riêng, đặt:

```json
{
  "enabled": true,
  "endpoint": "http://127.0.0.1:11434/api/chat",
  "model": "TEN_MODEL_CUC_BO_CHINH_XAC_DA_CAI",
  "timeout_seconds": 8,
  "minimum_interval_seconds": 300
}
```

Nhập đường dẫn config ở launcher. Tên model phải khớp tên tag mà dịch vụ phản hồi. Gói không khuyến nghị một kích thước/model cụ thể đã được benchmark; chưa đo phần cứng máy anh. Phải dùng dịch vụ Ollama tin cậy ở IP loopback; adapter không thể xác minh cách một tiến trình giả mạo ở cùng cổng thực hiện suy luận phía sau.

Adapter không nhận API key và không có endpoint trả phí. Nó chỉ gọi HTTP `/api/chat` trên IP loopback, tắt proxy, chặn redirect và giới hạn kích thước/thời gian phản hồi. Không kết nối cloud. Nếu model chậm, lỗi hoặc JSON không hợp lệ, hiển thị `LOCAL_MODEL_UNAVAILABLE` và giữ báo cáo dữ kiện; EA không đổi quyết định. Các kiểm thử adapter sử dụng phản hồi giả lập, chưa phải chứng nhận tương thích mọi bản Ollama/model.

## Đọc dữ liệu Tester V2.23 đã hoàn tất

Không trỏ vào lượt đang chạy để coi như dữ liệu đã hoàn tất. Sau khi nhận bản chụp ổn định/đã kết thúc, có thể đọc tương thích qua CLI, không cần đổi tên dữ liệu V2.23:

```bat
cd /d "D:\V224_RC3\LearningSupervisor"
.venv-ai\Scripts\python.exe run_ai_assistant.py collect --source "D:\Data\JOURNAL_TESTER_EURUSD" --output "D:\Research\Assistant_Test01" --broker-utc-offset-minutes 0 --channel test01
```

`collect` đọc hết prefix hiện có; nó không tự chứng nhận Tester đã chạy xong hoặc không lỗi. `watch` chỉ chấp nhận nguồn LIVE_MT4. Cả hai không thay nguồn. Báo cáo Tester luôn ghi hồi cứu, không tính là dự báo live hay tư vấn trước khóa. Công cụ này không thay quy trình kiểm định RC1 hoặc tính WIN/LOSS 30 phút đã chốt cho lượt 01/04–16/05.

## Tách biệt với bộ tư vấn và bộ học cũ

- `Start-Local-AI-Assistant.cmd`: giải thích RC1/LLM, output riêng, không ghi reply.
- `Start-Learning-Dialogue.cmd`: bộ tư vấn pre-lock kế thừa, contract/model riêng; cờ trao đổi và tác động vẫn OFF mặc định. Thiếu/trễ/sai tư vấn thì EA tự quyết.
- `LearningSupervisor/START_WATCH.cmd`: supervisor tín hiệu chính thức và mô hình thống kê đã đóng băng, output riêng.
- Các CMD legacy/session/news/Forex giữ vai trò riêng. Không bắt buộc mở mọi CMD chỉ để xem trợ lý; không chạy hai writer vào cùng output.

Tắt CMD trợ lý bằng Ctrl+C chỉ dừng báo cáo AI. Không cần tắt EA. Nếu tiến trình bị tắt đột ngột, xem PID trong `.writer-lock/owner.json`, xác nhận tiến trình đó đã ngừng rồi mới xóa khóa treo; không xóa database hoặc nguồn để vượt lỗi integrity.

Sau pilot có thể Ctrl+C, rồi zip thư mục output trợ lý đã đóng cùng dữ liệu EA riêng để đánh giá. Không zip/copy thô database đang ghi. Không gửi model/API key; trợ lý này không lưu API key.

## Điều kiện trước các bước nâng cấp tiếp

Hoàn tất đánh giá bối cảnh/tuổi trên dữ liệu mới. Sau đó mới kiểm kê đúng cohort và phát triển model 30 phút có feature contract mới, chia train/calibration/test theo thời gian, embargo, calibration và shadow live có biên nhận. Một lọc giảm LOSS nhưng bỏ nhiều WIN có thể làm hệ thống kém hơn. Chưa thay ATR, chiến lược, thời gian giữ, vị thế Forex hay guard vì lời giải thích của LLM.

Gói RC3 chưa tích hợp AI đọc tin văn bản hoặc quản lý lệnh Forex. Các bộ lọc tin có cấu trúc của EA kế thừa vẫn làm việc theo hợp đồng cũ. Giải thích dữ kiện, kết nối AI và lợi thế dự báo là ba mức khác nhau; không đánh đồng chúng.
