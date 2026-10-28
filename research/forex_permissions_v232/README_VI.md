# V2.32 — chẩn đoán quyền giao dịch trong Strategy Tester

Bộ này bổ sung **log quan sát**, không đổi chính sách giao dịch của V2.31. Dùng khi tín hiệu đã qua điều kiện native nhưng `ENTRY_RESULT` báo `TERMINAL_TRADING_UNAVAILABLE` và chưa có ORDER_INTENT.

Status đó gộp bốn điều kiện: `IsConnected()==false`, `IsTradeAllowed()==false`, `IsTradeContextBusy()==true`, hoặc `MarketInfo(Symbol(),MODE_TRADEALLOWED)==0`. Chỉ status tổng hợp không đủ xác định điều kiện nào sai. Không tự kết luận AutoTrading OFF, thiếu margin, SL/TP sai hoặc broker từ chối lệnh khi chưa có bằng chứng.

## Thay đổi duy nhất

Expert mới `EURUSD_M5_Intelligence_V232_PermissionResearch.mq4` quan sát bốn API khi chúng trả giá trị làm chặn một entry đang được engine kiểm tra. Wrapper **trả nguyên giá trị API gốc**, giữ short-circuit và toàn bộ guard. Khi chặn, Journal có dòng `V232 PERMISSION BLOCK` và thư mục run có `research_permissions_v232.csv`. Không có cơ chế bật quyền, bỏ guard hay gửi lệnh thay thế. Nếu ghi chẩn đoán thất bại, guard gốc vẫn chặn.

CSV ghi:

| Trường | Ý nghĩa |
| --- | --- |
| trigger / observed_value | Tên predicate và đúng giá trị API gây short-circuit |
| connected / trade_allowed / context_busy / symbol_trade_allowed | Ảnh chụp trạng thái đồng thời; trường ứng với trigger được giữ bằng giá trị đã làm chặn |
| terminal_autotrading | IsExpertEnabled tại lúc chẩn đoán |
| ea_trade_allowed | MQLInfoInteger(MQL_TRADE_ALLOWED) tại lúc chẩn đoán |
| entry_target_seconds, tag, native_config_hash, post_lock_gap_s | Đối chiếu đúng entry và cấu hình |

`IsTradeAllowed` có thể liên quan cả quyền EA và trạng thái trade context. Hai cột AutoTrading/per-EA giúp phân biệt, nhưng không thay cho trigger thực tế. Một trạng thái ở lượt mới không tự chứng minh trạng thái của lượt cũ nếu các thiết lập đã đổi.

Giữ ATR3, gap sau khóa10 giây ở preset kèm theo; giá tại khóa/entry vẫn mới tối đa3 giây, entry lag2 giây, gap trước khóa30 giây, cấu trúc/risk/lịch/SL/TP giữ nguyên. **40 header V229 và adapter Continuity V231 giữ từng byte**. Policy hash vẫn là hợp đồng V231_POSTLOCK_CONTINUITY_V1 vì chính sách không đổi. Metadata run mới nằm ở `research_config_v232.csv`.

## Chỉ chạy một lượt chẩn đoán

1. Chép Expert MQ4 mới vào `MQL4/Experts`, chép preset `EURUSD_M5_V232_Permission_Gap_10s.set` vào `MQL4/Presets`.
2. Nếu đang dùng V2.31 đúng bộ đã giao, **giữ nguyên** hai thư mục Include `EURUSD_M5_V224` và `EURUSD_M5_V231_Research`; không cần thư viện mới. ZIP có đủ chúng cho máy cài mới.
3. Mở MQ4 mới trong MetaEditor, F7 để biên dịch. Chưa có EX4 trong bộ tải.
4. Trong Strategy Tester chọn Expert V232, EURUSDz / M5 / Every tick. Optimization OFF, Visual OFF. From **2026.10.21**, To **2026.10.22**; vốn **10.000 USD**, spread **10 points** trên symbol5digits, Long & Short.
5. Inputs → Load preset trên; giữ tag mới `v232_gap10_diag001`. Giữ nguyên các quyền/kết nối hiện tại và ghi chú trạng thái AutoTrading để đo điều kiện đang chặn; chưa tự bỏ guard hoặc thay ATR/gap.
6. Chạy xong gửi Report HTML và ZIP:

`<MT4 Data Folder>\tester\files\FX_V222\v232_gap10_diag001_TESTER_EURUSDz`

Cần cả metadata, events, quote/clock, anchors/risk, marker kết thúc; nếu có entry bị terminal guard chặn, thêm `research_permissions_v232.csv` hoặc dòng `V232 PERMISSION BLOCK` trong Journal. Nếu không có file permissions, không tự suy ra mọi quyền đều đúng: có thể chưa đến bước đó hoặc ghi file lỗi; gửi toàn bộ log/Journal để kiểm tra.

Không cần chạy lại gap3/5 hay thử gap15/30 lúc này. Không cần CMD mới. Hai chart Demo/Real giữ nguyên EA đang vận hành. Expert chẩn đoán từ chối chart ngoài Tester, Optimization, Binary/Real/news/model effects như V231. Quote/clock logging phải ON; native hash cố định và tag phải bắt đầu `v232_`. Mỗi lượt chạy lại cần tag mới `...diag002`, giữ nguyên thư mục cũ.

## Cách đọc nguyên nhân

- `IS_CONNECTED=0`: quote chẩn đoán cho thấy trạng thái kết nối làm chặn tại entry; cần đối chiếu terminal/Tester, không tự kết luận lỗi mạng chỉ từ tên status.
- `IS_TRADE_ALLOWED=0`: đối chiếu AutoTrading, per-EA quyền và context_busy. Preset không thiết lập được tất cả quyền của terminal/tab Common.
- `IS_TRADE_CONTEXT_BUSY=1`: API báo context bận tại thời điểm kiểm tra.
- `MODE_TRADEALLOWED=0`: API MarketInfo của symbol trả không cho giao dịch; cần kiểm tra symbol/account/Tester và ý nghĩa giá trị API, không bỏ kiểm tra này chỉ để có lệnh.

Sau khi xác định và xử lý đúng điều kiện môi trường hoặc API đang chặn, mới chạy lại so sánh V231 theo cùng vốn/spread và đánh giá SL/TP, chi phí, lợi nhuận. Chưa có bằng chứng chọn một ngưỡng gap tối ưu. News vẫn OFF, nhãn TESTER_PRICE_ONLY_NO_NEWS; không dùng lịch tin hiện tại thay quá khứ. Không đưa bản nghiên cứu lên chart vận hành.

## Kiểm tra và giới hạn

25 kiểm thử gói đạt, bao gồm bốn predicate bị chặn, giá trị quan sát, không gửi lệnh khi chặn, không bypass khi ghi log lỗi, đường hợp lệ vẫn đi tới broker giả lập, giữ native timing/structure/risk, Tester-only, metadata, mirrors và 41 header/adapter nguyên bản. Kiểm tra lại V23120, V229 root375 và LearningSupervisor76 đều đạt, không skip. Các test dùng Linux C++17/API giả lập, không kết nối broker.

Chưa biên dịch MetaEditor hoặc chạy MT4 đặt lệnh cho V232 trong cloud; cần xác minh trên máy Windows. Đây là chẩn đoán trạng thái, không phải khuyến nghị đổi quyền để giao dịch tài khoản thật và không phải kết quả lợi nhuận backtest.

Phát triển: `python -m unittest discover -s tests -v`, cần Python3 và g++ C++17. Đóng gói: `python package_release.py --output /thu-muc-moi/research.zip`. Dữ liệu riêng của người dùng giữ ngoài Git.
