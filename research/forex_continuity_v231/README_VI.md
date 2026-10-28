# Forex V2.31 — nghiên cứu gián đoạn tick sau khóa

Bộ source này chỉ chạy trong **Strategy Tester**, gồm Expert `EURUSD_M5_Intelligence_V231_ContinuityResearch.mq4`, một adapter mới và 5 preset. Cần biên dịch bằng MetaEditor; chưa có EX4 hoặc kết quả MT4 đặt lệnh của phiên bản mới. Hai chart vận hành và các bộ V2.29/V2.30 giữ nguyên.

## Phạm vi thử nghiệm

ATR tối thiểu cố định **3 pip**. Chỉ thay `ForexResearchPostLockGapSeconds`: mức gián đoạn quote được chấp nhận sau khóa. Preset dùng 3 / 5 / 10 / 15 / 30 giây. Đây là thay đổi chính sách nghiên cứu, không phải cách nâng modeling quality hoặc sửa tick bị thiếu.

| Điều kiện | Giữ nguyên |
| --- | --- |
| Giá tại lúc khóa và lúc vào lệnh | Độ mới tối đa 3 giây |
| Cửa sổ entry | Tối đa 2 giây sau mục tiêu |
| Gián đoạn trước khóa | Tối đa 30 giây |
| Thời điểm khóa | Lead 30 giây + guard gốc 2 giây |
| ATR min/max, shock | 3 / 30 pip, 2,5 ATR |
| Vi phạm cấu trúc | Vẫn kiểm tra độ sâu/thời gian; reset bộ đếm breach sau gap >3 giây, không tính khoảng chưa quan sát thành thời gian vi phạm |
| Setup/xác nhận | Giữ SR1/TP1/BR1, bối cảnh và xác nhận gốc |
| Risk | 0,5%/lệnh, giới hạn equity ngày 2%, các giới hạn entry/loss/cooldown và margin gốc |
| Bảo vệ lệnh | SL 6–30 pip, TP 2R, giữ tối đa 60 phút, BE/trailing ON, averaging OFF |

Toàn bộ 40 file trong `EURUSD_M5_V224` giống từng byte V2.29. Adapter mới chỉ đổi hai biểu thức giới hạn continuity từ `Validation.mqh`, được áp dụng riêng cho ForexEngine của Expert mới. Không đổi `quoteFreshSeconds` trong cấu hình dùng chung. Native config hash giữ 2669644079; **policy_hash riêng** phân biệt các mức gap trong `research_config_v231.csv`.

Expert từ chối chart Demo/Real, Binary, Optimization, Real opt-in, news/model/adviser/embedded effects, ATR khác 3, gap ngoài 3–30 giây hoặc cấu hình native khác baseline. Cần bật cả quote/clock logging và dùng tag bắt đầu `v231_`. Không tắt logging để vượt kiểm tra. Tham số rủi ro của preset giữ nguyên; nếu tự thay trên máy thì phải báo rõ khi gửi kết quả.

## Cài đặt — không chép đè Include V224 hiện có

1. Giải nén ra thư mục riêng. Trong MT4 chọn File → Open Data Folder.
2. Chép `MQL4/Experts/EURUSD_M5_Intelligence_V231_ContinuityResearch.mq4` vào `MQL4/Experts`.
3. **Thêm thư mục mới** `MQL4/Include/EURUSD_M5_V231_Research` với file `Continuity.mqh`. Giữ nguyên thư mục `EURUSD_M5_V224` của V2.29/V2.30. ZIP có kèm 40 header V224 cho máy cài mới; máy đang dùng đúng bộ đã giao không cần chép đè chúng.
4. Chép 5 file `.set` trong `MQL4/Presets` vào Presets của MT4.
5. Mở MQ4 mới bằng MetaEditor → F7 → kiểm tra kết quả. Chỉ chọn Expert mới trong Strategy Tester; không gắn vào chart vận hành. Không cần CMD mới.

Nếu MetaEditor báo thiếu `EURUSD_M5_V231_Research/Continuity.mqh`, kiểm tra bước 3 và đúng Data Folder. Đây là thư viện bổ sung cần thiết, không đổi tên V224 thành V231.

## Ba lượt kiểm tra đầu tiên

Dùng cùng thiết lập ngoài `.set` cho cả ba lượt:

- Expert: `EURUSD_M5_Intelligence_V231_ContinuityResearch`.
- EURUSDz / M5 / Every tick; Optimization OFF; Visual OFF.
- Use date: From **2026.10.21**, To **2026.10.22**.
- Initial deposit **10.000 USD**, Long & Short; spread cố định **10 points** trên EURUSDz 5 digits (1 pip, giả định tham chiếu của lượt mốc).

Chọn Expert properties → Inputs → Load và chạy tuần tự:

| Thứ tự | File preset | Gap sau khóa | Tag lần đầu |
| --- | --- | ---: | --- |
| 1 — đối chứng | EURUSD_M5_V231_Research_Gap_03s.set | 3 giây | v231_gap03_run001 |
| 2 | EURUSD_M5_V231_Research_Gap_05s.set | 5 giây | v231_gap05_run001 |
| 3 | EURUSD_M5_V231_Research_Gap_10s.set | 10 giây | v231_gap10_run001 |
| Sau kiểm tra trên | EURUSD_M5_V231_Research_Gap_15s.set | 15 giây | v231_gap15_run001 |
| Sau kiểm tra trên | EURUSD_M5_V231_Research_Gap_30s.set | 30 giây | v231_gap30_run001 |

Với mức 3 giây và cùng dữ liệu, lượt đối chứng cần khớp hành vi V2.30; chưa coi số lệnh của các mức khác là kết quả đã biết. Những kiểm tra broker/risk khác vẫn có thể chặn entry. Nếu baseline khác, giữ nguyên dữ liệu và gửi log trước khi mở rộng thử nghiệm.

Mỗi lượt chạy lại, đổi tag thành `..._run002`, `..._run003`, kể cả sau lỗi hoặc khi đổi ngày/spread. Giữ các thư mục cũ. Engine từ chối dùng lại một tag đã có session; không xóa lock hoặc log để chạy đè.

Ngày, model, spread, deposit, Optimization và quyền giao dịch không được lưu đầy đủ bằng `.set`, phải kiểm tra ở Tester. Đừng thay `MaximumObservationGapSeconds` hoặc ATR trong giai đoạn này; giữ một yếu tố nghiên cứu duy nhất. Expert kiểm tra native config hash để phát hiện thay đổi ngoài phạm vi.

## Kết quả cần gửi

Mỗi lượt lưu **Report HTML**, Journal nếu có lỗi, và ZIP thư mục tương ứng dưới Data Folder:

`tester/files/FX_V222/<InstanceTag>_TESTER_EURUSDz`

Ví dụ lượt đầu: `v231_gap03_run001_TESTER_EURUSDz`; hai lượt sau có `gap05` và `gap10`. Trong thư mục cần có `research_config_v231.csv`, `forex_session.csv`, quote/clock, events, anchors/risk và `forex_tester_complete.csv` nếu engine kết thúc khỏe. Metadata ghi ngưỡng yêu cầu/đã áp dụng, native hash, policy hash và checksum. Các policy khác nhau có cùng native hash, vì vậy cần gửi cả metadata V231 để xác định đúng thử nghiệm.

Chạy cả khi kết quả 0 lệnh; không tăng risk/lot hoặc tắt các guard để ép có lệnh. Sau khi ba lượt kiểm tra hợp lệ mới hoàn thành lưới còn lại và mở rộng qua nhiều giai đoạn/phiên. Giữ cùng dữ liệu, vốn và chi phí giữa các lượt; chốt cách chọn tham số/kiểm tra kỳ tiếp theo trước khi đánh giá tối ưu.

## Giới hạn của nghiên cứu

News OFF chỉ trong bộ **TESTER_PRICE_ONLY_NO_NEWS** vì chưa có lịch tin theo từng thời điểm trong quá khứ. Không dùng lịch tin hiện tại để lấp quá khứ. Không đổi lọc tin hoặc EA trên chart Demo/Real.

Every tick của MT4 với modeling quality 90% vẫn là tick mô phỏng. Cho phép gap lớn hơn không tạo lại được đường giá trong đoạn không quan sát, không chứng minh an toàn hơn và không xác nhận dữ liệu live cũng có gap tương tự. Không chọn 5 hay 10 giây chỉ vì giải phóng được hai setup đã thấy. Cần số mẫu đủ lớn, kiểm tra chi phí thực trong Report và độ ổn định ngoài giai đoạn chọn tham số. ATR theo phiên sẽ nghiên cứu sau khi tách được ảnh hưởng của continuity.

## Kiểm tra đã hoàn thành trên Linux

20 kiểm thử của gói mới đạt: baseline adapter khớp native trên 10.000 trạng thái, biên gap, reset breach, lock/entry freshness 3 giây, deadline 2 giây, giới hạn cấu trúc/risk/quyền, đường gọi broker qua Expert với API giả lập, guard Tester-only, metadata/policy hash, mirrors và 40 header nguyên bản. Các API giả lập không kết nối broker thật.

Phát lại private tick đã cung cấp với adapter thật xác nhận mức gap 3 giống từng byte kết quả lifecycle V2.30 đã đối chiếu MT4. Phát lại tín hiệu không mô phỏng sizing/SL/TP/execution/P&L. Các kiểm tra hồi quy V2.30: 8; V2.29 root: 375; LearningSupervisor: 76 đều đạt, không skip.

Lệnh phát triển: `python -m unittest discover -s tests -v` trong gói này, cần Python3 và g++ C++17. Đóng gói: `python package_release.py --output /duong-dan-moi/research.zip`. C++ shim không thay thế MetaEditor/MT4 validation trên Windows. Dữ liệu riêng và các báo cáo tick vẫn ngoài Git.
