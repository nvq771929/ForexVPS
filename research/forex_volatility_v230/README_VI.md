# Bộ nghiên cứu ATR Forex V2.30 — chỉ Strategy Tester

Bộ này gồm một Expert nghiên cứu và 8 file `.set`. Expert chỉ khởi tạo trong Strategy Tester, chế độ Forex, Optimization OFF. V2.29 đang chạy trên hai chart giữ nguyên. Không có EX4: cần biên dịch MQ4 bằng MetaEditor trên Windows trước khi chạy.

V2.29 cố định ngưỡng ATR tối thiểu trong code nên nạp một `.set` mới vào V2.29 sẽ không thay đổi được ngưỡng. Expert `EURUSD_M5_Intelligence_V230_Research` bổ sung input thật `ForexResearchMinAtrPips`, đưa trực tiếp vào cấu hình native và ghi ngưỡng đã áp dụng vào journal. Toàn bộ 40 header giao dịch/giao diện giữ nguyên byte so với V2.29.

## Cài vào MT4

1. MT4 → File → Open Data Folder. Giải nén bộ nghiên cứu ra một thư mục riêng.
2. Chép `MQL4/Experts/EURUSD_M5_Intelligence_V230_Research.mq4` vào `MQL4/Experts` của MT4; chép 8 file trong `MQL4/Presets` vào thư mục Presets. Nếu MT4 đang dùng đúng bộ V2.29, các header đã có sẵn, không cần chép đè. Bộ ZIP có đủ `MQL4/Include/EURUSD_M5_V224` cho một cài đặt mới; giữ bản sao các include hiện có trước khi hợp nhất nếu chúng đã được sửa trên máy.
3. Mở MQ4 mới bằng MetaEditor, nhấn F7 và kiểm tra kết quả biên dịch. Sau đó Refresh mục Expert Advisors.
4. Chọn Expert mới trong **Strategy Tester**. Không thay Expert trên chart Forex/Binary đang chạy. Không cần chạy thêm CMD cho bộ Tester này.

## Lần chạy kiểm tra đầu tiên

Nhấn Ctrl+R và đặt:

| Mục | Giá trị |
| --- | --- |
| Expert | EURUSD_M5_Intelligence_V230_Research |
| Symbol / Period | EURUSDz / M5 |
| Model | Every tick |
| Use date | Bật; From 2026.10.19, To 2026.10.24 |
| Optimization | OFF |
| Visual mode | OFF để kiểm tra trước |
| Spread | 10 points nếu symbol có 5 digits: kịch bản tham chiếu 1 pip |
| Expert properties → Testing | Initial deposit 1000 USD; Long & Short |
| Expert properties → Inputs → Load | EURUSD_M5_V230_Research_ATR_Min_300.set |

Spread trên là giả định nghiên cứu, không phải xác nhận chi phí thực tế của Exness. Không dùng Current để so sánh các lần chạy. Nếu symbol có 4 digits, 1 pip là 1 point. Các thiết lập Model/Date/Spread/Deposit/Optimization nằm ngoài `.set`, cần đặt tại cửa sổ Tester. Kiểm tra quyền giao dịch của Tester nếu Journal báo chặn quyền; preset không thiết lập được tab Common.

**Every tick của MT4 là tick mô phỏng.** File M5 người dùng gửi đủ cho thống kê biến động nhưng không đủ tái dựng diễn biến trong nến hoặc cửa sổ vào lệnh 3 giây. Kiểm tra phạm vi M1, chất lượng mô hình và lỗi unmatched data trong Report/Journal trước khi kết luận. Không gọi kết quả chỉ từ M5 là backtest tick chính xác; không tự lấy dữ liệu nguồn khác ghép vào lịch sử broker.

Sau khi một lượt chạy hoàn tất, lưu Report HTML và Journal, rồi chạy cùng khoảng ngày/chi phí với các preset còn lại:

| Hậu tố file `.set` | ForexResearchMinAtrPips | InstanceTag lần đầu |
| --- | ---: | --- |
| ATR_Min_300 | 3.00 | v230_atr300_run001 |
| ATR_Min_250 | 2.50 | v230_atr250_run001 |
| ATR_Min_200 | 2.00 | v230_atr200_run001 |
| ATR_Min_150 | 1.50 | v230_atr150_run001 |
| ATR_Min_125 | 1.25 | v230_atr125_run001 |
| ATR_Min_100 | 1.00 | v230_atr100_run001 |
| ATR_Min_075 | 0.75 | v230_atr075_run001 |
| ATR_Min_000 | 0.00 | v230_atr000_run001 |

Tên đầy đủ: `EURUSD_M5_V230_Research_` + hậu tố + `.set`.

Mỗi lần chạy lại một preset, đổi `InstanceTag` sang `..._run002`, `..._run003`, v.v.; dùng tag mới cả khi đổi ngày, spread hoặc chạy dở. Giữ các thư mục cũ. Engine từ chối ghi đè một lượt Tester đã có `forex_session.csv`. Không xóa lock/journal để vượt kiểm tra này.

## Phạm vi đo và các tham số giữ nguyên

Giá trị 0 chỉ bỏ ngưỡng ATR thấp. Giới hạn ATR cao 30 pip, shock 2.5 ATR, điều kiện bối cảnh/setup, xác nhận T+1, thời điểm khóa/vào lệnh và kiểm soát rủi ro vẫn hoạt động. ATR vẫn dùng trong SL/trailing/cấu trúc; bộ này chưa thay ATR bằng một chỉ báo khác.

Risk 0.5%/lệnh, giới hạn giảm equity ngày 2%, SL 6–30 pip, TP 2R, giữ tối đa 60 phút, BE/trailing ON, averaging OFF, lịch broker ON giữ theo V2.29. Không chọn ngưỡng chỉ vì có nhiều giao dịch hơn.

`ForexNewsFilter=false` là điều kiện bắt buộc của Expert nghiên cứu này: dữ liệu tin tức lịch sử theo từng thời điểm chưa có. Kết quả mang nhãn **TESTER_PRICE_ONLY_NO_NEWS**, không đại diện đầy đủ cho EA vận hành có lọc tin. Không dùng lịch tin hiện tại để lấp vào quá khứ. Real opt-in, model/adviser/embedded context đều OFF; Expert từ chối khởi tạo nếu bật các chế độ đó hoặc chạy Optimization. Hai CMD đang chạy trên máy phục vụ chart vận hành, không cung cấp lịch tin lịch sử cho Tester.

Dashboard, quote recording và clock observation mặc định OFF để giảm file/tải cho nghiên cứu dài. Anchor, event, risk và session journal của engine vẫn được ghi. Có thể bật `RecordReplayInputs` và `RecordClockObservation` cho một lượt ngắn với tag mới nếu cần điều tra tick; chưa dùng cho mọi lượt tám tháng vì lượng file lớn.

## Gửi lại kết quả

Mỗi lượt lưu Report HTML, Journal và toàn bộ thư mục sau (thường nằm dưới Data Folder):

`tester/files/FX_V222/<InstanceTag>_TESTER_EURUSDz`

Trong đó cần có `research_config_v230.csv` (ngưỡng yêu cầu/đã áp dụng, hash cấu hình), `forex_session.csv`, `forex_events.csv`, các `forex_anchor_*.csv`, risk state và `forex_tester_complete.csv` nếu engine kết thúc khỏe. Thiếu marker hoặc 0 lệnh thì gửi cả Journal để phân biệt lỗi khởi tạo/dữ liệu/guard với không có setup. Không suy ra tỷ lệ thắng hay lợi nhuận từ số anchor/setup.

Đo theo phiên cần gom **giờ vào lệnh**, không chỉ giờ thoát; đối chiếu broker offset/DST của giai đoạn đó. Chưa có bộ lọc chỉ giao dịch từng phiên trong preset. Cùng kỳ, model, spread, vốn và các input còn lại phải giống nhau giữa 8 lượt. Khi đánh giá chi phí, kiểm tra commission/swap thực sự có trong Report; chưa có thì chưa kết luận lợi nhuận ròng thực tế.

Sau lượt kiểm tra ngắn, mới mở rộng sang các giai đoạn nhiều tháng và lập quy trình chọn tham số trên quá khứ rồi kiểm tra giai đoạn tiếp theo. Thống kê toàn bộ file hiện tại là thăm dò; không phải kiểm định ngoài mẫu. Chưa chọn ngưỡng mới để đưa lên chart Demo/Real.

## Xác minh trên cloud

8 kiểm thử của gói nghiên cứu đã qua: chặn chart thật/Demo, Optimization và cấu hình sai; kiểm tra cả 8 input đi vào cấu hình native; kiểm tra metadata/checksum; giữ journal khi trùng tag; 40 header và hai cây `mt4`/`MQL4` đồng nhất. V2.29 chạy lại 375 kiểm thử root và 76 LearningSupervisor, không skip. Kiểm thử C++/API shim trên Linux không thay cho MetaEditor hoặc Strategy Tester MT4. Chưa thực hiện backtest lệnh và chưa xác nhận lợi nhuận.

Chạy lại kiểm thử: `python -m unittest discover -s tests -v` tại thư mục gói này; cần Python 3 và g++ hỗ trợ C++17. Không cần Python để chạy Expert đã biên dịch trong MT4.
