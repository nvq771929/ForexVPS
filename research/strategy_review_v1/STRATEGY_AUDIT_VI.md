# Rà soát chiến lược và điều kiện vào lệnh

Người dùng yêu cầu xem lại từ gốc cả Binary Option và Forex; chart Forex của phiên Mỹ vừa qua là V2.29 vận hành, giữ nguyên cấu hình. Phạm vi ở đây là nghiên cứu ngoại tuyến, chưa thay EA, preset, model hoặc quyền giao dịch trên chart.

## Những gì source thực sự làm

1. **Hai mảng dùng chung candidate.** `Forecast.mqh` lấy regime để chọn SR1/TP1/BR1, rồi áp min/max ATR, shock, overlap vùng, điều kiện setup và cấu trúc. Forex không có một bộ setup độc lập đã được kiểm định riêng. Dùng chung đặc trưng thị trường có thể hữu ích; dùng cùng điều kiện vào cần bằng chứng cho từng hợp đồng lợi nhuận.
2. **Ngưỡng phần lớn là giả định kế thừa.** ATR3–30pip, shock2.5, các hệ số vùng/động lượng và 3giây sau khóa có trong `Types.mqh`. Không tìm thấy kết quả hiệu chỉnh độc lập chứng minh chúng tối ưu cho Forex hoặc BO. Nhiều kiểm thử source xác nhận thực thi, không xác nhận lợi thế thị trường.
3. **Có một nến chờ trước entry.** `BOStartEpisode`: target=analysisStart+300. Features lấy từ64nến đóng trước analysisStart; sau đó quan sát nến T+1, khóa khoảng32giây trước target và chỉ vào trong2giây sau target. Điều này cần được nghiên cứu như một hợp đồng thời điểm riêng khi chuyển sang Forex, không mặc định phù hợp vì đã dùng cho BO.
4. **Forex bỏ gate xác suất BO, vẫn giữ candidate/validation.** `FXLock` dùng BOLock shadow rồi chuyển hướng được xác nhận thành action rule-based. Forex không chờ model BO đủ mẫu để có lệnh. Entry còn qua lịch, risk, news, exposure EURUSD, quyền terminal, quote, kế hoạch lot/SLTP và margin. Không có lệnh không đồng nghĩa không có candidate.
5. **BO Demo có đường phát thăm dò ở cold start.** `BODemoLock` có thể phát với modelId0 sau native validation; không phải mọi chế độ đều đòi model được promoted. File học hỏng/hết hạn hoặc quyết định từ chối có thể chặn khi bật dùng học. COLLECTING trên dashboard không tự chứng minh đây là nguyên nhân Forex im lặng.
6. **BO có hai sổ kết quả cần tách.** Public manual ledger được chốt ở LOCK và không bị xóa khi native ENTRY hủy sau đó. Native mô phỏng entry/outcome là sổ khác. WIN/LOSS Bid MT4 không chứng minh người dùng đã khớp lệnh hoặc nhận payout trên Olymp Trade. Sau entry native có resume/cooldown, cũng không được đồng nhất với mọi candidate M5.
7. **Guard sau khóa mạnh hơn việc giá tại entry còn mới.** Với V229, một gap>3s sau khóa có thể hủy setup dù tick mới vừa tới đúng target. V231 tách riêng giới hạn này để nghiên cứu, không sửa V229. Các lượt Tester trước chỉ chứng minh ảnh hưởng của policy trên chuỗi tick mô phỏng đó, không chứng minh mức10s tối ưu hay gap live tương tự.
8. **Lịch tin của hai mảng khác vai trò.** Forex dùng news để chặn/đóng vị thế, missing/stale có thể fail-closed; bộ quan sát tin/session của BO không tự quyết định chiến lược. Không thay bằng lịch tin hiện tại khi test quá khứ.

Nguồn chính: `mt4/Include/EURUSD_M5_V224/{Types,Forecast,Regime,Episode,Validation,Decision,DemoLearning,ManualSignals,ForexEngine,ForexRisk,ForexProtection,ForexNews}.mqh` và Expert V229. Các source này giữ nguyên.

## Cách phân loại một phiên không có giao dịch

Đếm theo trình tự: dữ liệu/slot có thể phân tích → candidate theo từng setup → xác nhận/LOCK → hủy theo tick/cấu trúc → entry đủ thời điểm → news/risk/exposure → terminal permission → ORDER_INTENT → broker fill/reject → quản lý/thoát. Ghi tỷ lệ qua từng gate, không cộng các lý do chồng lấp thành tổng loại trừ.

Ba lượt V231 của ngày21/10 trước đó đã đi tới terminal guard ở mức gap5/10, rồi dừng với status tổng hợp. Điều đó không xác định được vì sao phiên Mỹ mới nhất của V229 im lặng. Cần dữ liệu chính phiên đó, không áp kết luận của một ngày/model/phiên bản khác.

## Hai hợp đồng nghiên cứu riêng

**BO:** entry/expiry đúng thời điểm, giá của đúng nền tảng, kỳ hạn và payout thực tại entry, TIE và độ trễ thao tác. Với payout82% và hòa hoàn tiền, tỷ lệ thắng hòa vốn trong các quyết định không hòa là1/1.82≈54.95%; trên50% chưa đủ. Đánh giá expectancy theo stake, calibration và độ ổn định theo thời gian. Model không được học từ nhãn hoặc MFE tương lai như đầu vào.

**Forex:** setup và thời điểm khớp, Bid/Ask/spread, SL cấu trúc/ATR, TP và quản lý vị thế, phí/slippage/swap, lịch tin, sizing/margin/risk. Đánh giá net expectancy theo R, drawdown, độ nhạy chi phí, tần suất và ổn định theo tháng/phiên; tỷ lệ thắng đơn lẻ không đủ.

Tần suất là thước đo coverage và đủ mẫu, không là chỉ tiêu ép hệ thống phải có lệnh mỗi phiên. Thay điều kiện để tăng số lệnh chỉ được chấp nhận khi có bằng chứng kỳ vọng/rủi ro tốt hơn trên dữ liệu phù hợp.

## Vòng1 đã thiết kế

Năm hợp đồng cố định: native candidate ATR3 với lead1nến (proxy), cùng candidate vào ngay (đối chứng thời điểm), trend pullback, range rejection, breakout momentum. Quy tắc và chi phí nằm trong `protocol.json`, đã commit trước khi tính các điểm kinh tế của vòng này. Không tìm tham số theo kết quả và không chọn phiên đẹp sau khi xem toàn bộ dữ liệu.

Vòng này chỉ dùng M5 OHLC: BO là giá tham chiếu Bid mở nến, Forex là bracket ATR cố định với Bid/Ask giả định và hai thứ tự giá khi cùng nến chạm cả SL/TP. **Không phải backtest đầy đủ V229**, không có xác nhận intrabar/native guards cho các proxy, không có trailing/BE/native structural SL/news và không có khớp BO thực. Những khác biệt này được ghi vào protocol trước khi chạy.

Thống kê theo tháng/phiên và bootstrap theo tuần giúp mô tả độ bất định, không làm dữ liệu đã xem thành test ngoài mẫu sạch. File lịch sử đã được xem mô tả từ trước; mọi kết quả vẫn là thăm dò. Vòng1 không có quyền chọn/activate chiến lược, kể cả một bảng có lợi nhuận dương.

## Các bước để đi tới backtest đầy đủ

1. Đối chiếu log phiên Mỹ mới và sổ BO thực để tách vấn đề dữ liệu/quyền/guard khỏi vấn đề kinh tế của setup. Dùng code V229 hiện có làm baseline đóng băng.
2. Chốt rulebook độc lập BO và Forex, nêu điều kiện vào/thoát, thời gian khả dụng của từng biến, các giả định và đối chứng. Chỉ đưa giả thuyết qua vòng1 sang vòng2 nếu còn lý do kinh tế/statistical rõ ràng; không cứu một model bằng tối ưu hàng loạt sau kết quả xấu.
3. BO cần dữ liệu Bid/quote đúng mốc trong sổ đã phát, kỳ hạn/payout và đối chiếu platform. Forex cần lịch sử tick/BidAsk và chi phí; M1 có thể hỗ trợ lịch sử nhưng không tự trở thành real ticks hay chứng minh guard3s.
4. Kiểm định hồi cứu theo thứ tự thời gian, embargo phù hợp với cửa sổ đặc trưng/nhãn/vị thế, chọn tham số chỉ trên quá khứ. Lịch sử đã được xem không gọi là untouched holdout. Xác nhận cuối trên nguồn chưa dùng hoặc giai đoạn forward mới; ghi số phép thử.
5. Sau đó mới chạy sealed Strategy Tester/native contract và forward Demo đối chiếu từng quyết định. Không chuyển lên Real hoặc bật model bằng kết quả OHLC tham chiếu.

## Dữ liệu cần cho phần vận hành mới

Trong MT4 → File → Open Data Folder → MQL4/Files, chọn đúng đường `Nhật ký` trên từng dashboard. Giữ tất cả file của đúng thư mục BO và Forex, gồm journal/BIN, session, events, quote/clock, anchors, policy/risk và restart state. Nén riêng hai thư mục (không cần venv/toàn bộ source); giữ file gốc và lock. Nếu nhiều phần ZIP, giữ đủ các phần.

Gửi thêm Experts/Journal trong khung phiên Mỹ nếu có lỗi. `FX_V222/news_calendar.csv` hiện tại chỉ là bối cảnh, không chứng minh tình trạng news trong cả phiên cũ; nếu có archive theo thời điểm thì giữ kèm. Nêu thời gian bắt đầu/kết thúc theo đồng hồ trên MT4 hoặc ảnh có giờ để xác định phiên, không đoán offset từ TimeGMT của Tester.
