# V2.22 Forex — quản lý vị thế, né tin và tùy chọn bình quân

Source RC1 cho EURUSD M5 trên MT4 Exness demo/real. Real vẫn cần Input
ForexAllowRealTrading=true; mặc định false. V2.21/V2.20/V2.19 được giữ nguyên.
Đây là chính sách theo quy tắc, chưa chứng minh lợi nhuận hoặc tối ưu tham số.
Không có phần mềm xử lý được mọi tình huống khi broker/MT4 không thực thi được.

## Những phần kế thừa

TradingMode=BinaryOption|Forex, mặc định BinaryOption. Forex dùng nến đóng,
SR1/TP1/BR1, xác nhận T+1, khóa trước entry, quote guard 3 giây và entry +2 giây.
Giữ ATR 3–30 pip; không thay bằng ATR theo phiên khi nghiên cứu chưa hoàn tất.
Không dùng model/payout Binary để quyết định lợi nhuận Forex.

Risk dự kiến 0,5% × min(Balance,Equity); lot làm tròn xuống theo bước broker,
kiểm tra tick value/tick size/margin/min lot/max lot. SL theo cấu trúc, tối thiểu
1,5 ATR và 6 pip, tối đa 30 pip; TP mặc định 2R. Spread tối đa 1,5 pip.
Nếu broker không nhận SL/TP, không mở lệnh trần để gắn stop sau.

Khi bình quân OFF, chặn mở khi có bất kỳ exposure EURUSD nào, kể cả manual/
pending/EA khác. Khi ON, ngoại lệ duy nhất là một lệnh thêm cùng chiều vào
cụm own đủ điều kiện; [xem cơ chế và ngân sách cụm](AVERAGING_V222_VI.md).
Ngân sách 0,5% là cho cả cụm. Lệnh đầu dùng tối đa 70%; SL/TP gốc giữ nguyên.
Margin dự kiến sau mở phải đạt 500%, free margin/tài sản ít nhất 50%.
Chỉ sửa/đóng lệnh đúng symbol và Magic của EA. Không đổi Magic/Mode khi còn lệnh.
Không chạy đồng thời V220/V222 hoặc nhiều terminal trên cùng tài khoản để né chặn.
Lease trong terminal không phải khóa phân tán giữa nhiều máy/phiên bản.

## Hòa vốn và trailing

| Input | Mặc định | Hành vi |
|---|---:|---|
| ForexBreakEven | true | Bật dời SL về gần hòa vốn |
| ForexBreakEvenAtR | 1,0 | Kích hoạt khi lợi nhuận giá đạt 1R |
| ForexBreakEvenOffsetPips | 0,5 | SL vượt giá vào 0,5 pip theo hướng có lợi |
| ForexTrailingStop | true | Bật trailing theo ATR nến đóng |
| ForexTrailingStartR | 1,5 | Bắt đầu trailing từ 1,5R |
| ForexTrailingATR | 1,5 | Khoảng trailing = max(1,5 ATR14, mức pip tối thiểu) |
| ForexTrailingMinPips | 3,0 | Khoảng trailing tối thiểu |
| ForexTrailingStepPips | 0,5 | Chỉ gửi sửa khi cải thiện đủ bước |

1R là khoảng giá khớp đến SL ban đầu, lưu riêng từng vị thế. Không tính lại R
bằng SL đã dời. BUY xét Bid, SELL xét Ask. SL chỉ siết, không kéo lùi; TP giữ
nguyên. Làm tròn theo tick, kiểm tra StopLevel và FreezeLevel broker. Thử sửa
lại cách ít nhất 5 giây, đọc lại trạng thái thực nếu timeout. Không liên tục
đẩy lại một SL đã được broker áp dụng.

ATR trailing chỉ dùng packet nến đóng hợp lệ của M5 hiện tại. Thiếu packet
thì không bịa ATR; hòa vốn vẫn có thể hoạt động. Offset không bảo đảm hòa vốn
ròng sau phí hoặc gap. Broker giữ mức SL gần nhất khi máy tắt; trailing tiếp
cần EA online, quote mới và quyền giao dịch.

## Giới hạn thời gian — độc lập với SL/TP

ForexMaxHoldMinutes mặc định 60, **chưa được tối ưu bằng kết quả lịch sử**.
Khi đủ 60 phút từ lần khớp mở ban đầu, EA yêu cầu đóng theo giá thị trường,
**dù đang lãi/lỗ và chưa chạm SL/TP**. Đây không phải Binary expiry, không phải
hẹn giờ bảo đảm broker khớp đúng giây. 0 tắt điều kiện thời gian này; SL/TP,
trailing, né tin và các điều kiện rủi ro khác vẫn có thể đóng lệnh.

Có preset tùy chọn Forex_Demo_NoTimeLimit / Forex_Tester_NoTimeLimit đặt 0;
đây là cấu hình để đối chiếu, không phải kết luận tối ưu hoặc tự áp dụng lên MT4.

Đóng một phần không gia hạn 60 phút: ticket còn lại lưu thời điểm mở đầu tiên
và R ban đầu, kể cả broker cấp ticket mới. Mất kết nối/quote cũ/AutoTrading off
thì yêu cầu đóng được giữ để tiếp tục khi điều kiện cho phép. Không tự kéo dài
chỉ vì lệnh lỗ, không nới SL để chờ hồi. Giữ lâu hơn có thể cho cơ hội hồi nhưng
cũng tăng rủi ro; cần so sánh 30/60/120/240/0 trên dữ liệu tách theo thời gian,
có spread/phí/swap, trước khi chọn chính sách theo chiến lược/phiên.

## Giới hạn giao dịch và rủi ro

| Input | Mặc định | Hành vi |
|---|---:|---|
| ForexRiskPercent | 0,5 | Ngân sách một vị thế; khi bình quân ON là ngân sách cả cụm |
| ForexMaxDailyLossPercent | 2,0 | Chặn mở theo equity toàn tài khoản |
| ForexCloseOwnOnDailyLoss | true | Khi chạm ngưỡng ngày, yêu cầu đóng vị thế own |
| ForexMaxDailyEntryAttempts | 6 | Tối đa 6 lượt dành quyền gửi mỗi ngày broker, reject cũng tính |
| ForexMaxConsecutiveLosses | 3 | Dừng mở khi chuỗi kết quả đóng ròng trong ngày đạt ngưỡng |
| ForexCooldownMinutes | 15 | Nghỉ mở sau lần đóng gần nhất |
| ForexEmergencyCloseOwnPositions | false | Bật để yêu cầu đóng lệnh own và chặn mở mới |

Mốc equity là quote đầu tiên EA ghi trong ngày broker, không tự tái dựng equity
nửa đêm nếu gắn giữa ngày. Nạp/rút/lệnh khác cũng tác động equity. Halt ngày,
số lượt gửi, kết quả đóng, R và yêu cầu đóng được lưu; restart không xóa chúng.
Chuỗi thua xét profit+swap+commission của ticket đóng đã quan sát, gồm phần
đóng trước tin; kết quả bằng/thuận 0 ngắt chuỗi. Không phải xác nhận tất cả lịch
sử broker đều đã tải: chọn All History và đối chiếu kết quả. Không xóa nhật ký
để bỏ chặn. Số lần thử được dành trước API nên có thể tính cả lượt bị bỏ do I/O.

Risk 0,5% và ngưỡng ngày 2% không phải bảo đảm lỗ thực tối đa; slippage/gap/phí
có thể vượt giả định. Fill thiếu SL/TP, vượt budget, metadata vị thế lỗi hoặc
không đối chiếu được phần đóng: yêu cầu đóng own thay vì mở lệnh thay thế.
Close lỗi được thử lại với giãn cách 1,2,4,8,16,tối đa 30 giây; yêu cầu tồn tại
sau restart. Không có chuỗi tăng lot không giới hạn. Bình quân tùy chọn chỉ
thêm một lệnh nhỏ hơn, dùng chung ngân sách và không nới SL; xem hướng dẫn riêng.

## Lịch broker và cuối tuần

ForexUseTradingSchedule=true. Các Input là **phút sau nửa đêm giờ broker**,
không phải giờ Việt Nam. Mặc định cho feed UTC+0 đã được anh xác nhận:

- Rollover không mở 21:00–22:15 (1260–1335), khoảng rộng bao cả mùa hè/mùa đông NY.
- Thứ Sáu không mở từ 20:00 (1200), yêu cầu đóng own từ 20:30 (1230).
- Thứ Bảy/Chủ nhật không mở; nếu còn own, tiếp tục yêu cầu đóng khi broker cho phép.

Đây là lịch thận trọng có thể chỉnh, không phải tự khám phá giờ nghỉ của mọi
broker. Nếu server đổi múi giờ cần đối chiếu lại Input. Cửa sổ rollover hỗ trợ
qua nửa đêm; start=end nghĩa tắt riêng cửa sổ, không tắt chặn cuối tuần.

## Tin tức Forex — bộ lọc thực thi riêng

ForexNewsFilter=true trên live/demo. Chạy **Start-Forex-News.cmd** từ source
V222 và nhập MT4 Data Folder. Không cần hai CMD học Binary. Một worker riêng
đọc lịch Fair Economy, cập nhật cache mỗi 15 phút, thử lại sau lỗi mỗi 60 giây,
và xuất FX_V222/news_calendar.csv. Không gọi mạng trong OnTick/OnTimer.

Theo dõi EUR/USD, mức Medium/High theo chính nguồn cấp và các sự kiện ưu tiên
ZEW đã cấu hình. Mức tác động không nhất thiết trùng số sao Investing; không
khẳng định nguồn chứa đủ mọi sự kiện hoặc tin đột xuất. Lịch chỉ là lịch công
bố, không phải dự báo nội dung/kết quả hay hướng biến động.

| Input | Mặc định |
|---|---:|
| ForexNewsMaxAgeSeconds | 1800 |
| ForexNewsHighBeforeMinutes / HighAfterMinutes | 30 / 15 |
| ForexNewsMediumBeforeMinutes / MediumAfterMinutes | 15 / 10 |
| ForexNewsEntryLookaheadMinutes | 5 |
| ForexNewsPositionExitMinutes | 5 |
| ForexNewsHighPositionAction | 1: đóng toàn bộ |
| ForexNewsMediumPositionAction | 2: đánh giá vị thế |
| ForexNewsReducePercent | 50 |

Chặn lệnh mới nếu khoảng từ hiện tại đến +5 phút giao với cửa sổ tránh tin.
Nhiều tin lấy hợp các cửa sổ, không chỉ sự kiện gần nhất. Trong khoảng 5 phút
trước đến hết vùng sau tin, quản lý own như sau:

Các bước cắt một phần dưới đây áp dụng khi bình quân OFF. Khi bình quân ON
hoặc đang quản lý cụm đã mở, action 1 hoặc 2 yêu cầu đóng toàn bộ cụm,
kể cả cụm mới có lệnh đầu. Không cắt một phần từng chân của cụm bình quân.

- Tin High: mặc định yêu cầu đóng toàn bộ, kể cả đang lỗ.
- Tin Medium/Low ưu tiên: nếu P/L ròng <=0 thì đóng toàn bộ. Nếu đang lãi và
  SL đã vượt entry đủ offset thì giữ và tiếp tục trailing. Nếu đang lãi nhưng
  chưa được bảo vệ, giảm 50% theo bước lot. Có thể giữ mức SL hiện tại và vẫn
  chịu gap; không gọi đây là bảo đảm đã hết rủi ro.
- Không chia được lot hợp lệ: đóng toàn bộ. Partial không xác nhận/không khớp
  metadata: chuyển sang yêu cầu đóng toàn bộ phần own còn lại. Không gửi partial
  lần nữa cùng sự kiện sau restart. Tin High ưu tiên khi nhiều tin sát nhau.

Action 0=giữ SL/TP, 1=đóng toàn bộ, 2=đánh giá như trên; điều chỉnh riêng High
và Medium. Chặn entry vẫn độc lập với action quản lý vị thế.

Đồng hồ live đối chiếu UTC PC/server qua cơ chế hiệu chuẩn, cần Windows clock
đúng và vài tick đầu. Bridge có checksum, số dòng, phạm vi tuần, snapshot ID,
received/expires. Cũ, thiếu, sai hash/phạm vi, giờ chưa rõ hoặc sự kiện tracked
có thời gian chưa chắc chắn => **chặn mở mới**, không gán NEWS_CLEAR. Tin chưa
rõ giờ hiện chặn toàn snapshot, thận trọng hơn chỉ chặn một ngày. Không bịa tin
để đóng hoảng loạn: vị thế đang có tiếp tục SL/TP/trailing/time/risk guard.

Worker giữ raw body/vintage có hash trong news_cache; thất bại không gia hạn
received/expires. Snapshot cũ còn hợp lệ có thể tiếp tục dùng, hết tuổi thì
chặn. Khi dừng CMD, lọc tin không tự tắt; EA dừng mở khi cache hết hạn. Dữ liệu
này không cho phép biết trước tin bất ngờ hoặc kiểm chứng tính đầy đủ của nguồn.

**Strategy Tester:** preset Forex_Tester chủ động đặt ForexNewsFilter=false
vì chưa có lịch lịch sử theo đúng thời điểm nhận. Dashboard ghi DISABLED. Nếu
bật true trong Tester, EA chặn mở với NEWS_TESTER_NO_HISTORICAL_CALENDAR; tuyệt
đối không dùng lịch tuần hiện tại cho quá khứ. Kết quả Tester đó chưa kiểm định
chính sách né tin. Cần demo forward với worker để đánh giá nhánh tin thực tế.

## Phục hồi và nhật ký

Magic mặc định 2220520. intent_<target> ghi trước OrderSend: mỗi target một lần
thử. Timeout/mất kết nối gây kết quả mở không rõ tạo execution_review_required
và chặn mở mới; trường hợp này **còn cần người đối chiếu với broker**, không
thể suy từ “chưa thấy ticket” thành “broker chưa khớp”. Không hứa hoàn toàn
không cần giám sát. Không can thiệp login/tài khoản hoặc EA giao dịch khác.

Root live: MQL4/Files/FX_V222/LIVE_<account>_<feed_key>.
Root Tester: tester/files/FX_V222/<tag>_TESTER_<symbol>.

- forex_session.csv: nguồn, chiến lược và toàn bộ cấu hình Forex/né tin.
- forex_quotes_*.csv, forex_anchor_*.csv: quote nhận, packet nến đóng.
- forex_events.csv: fill, lỗi, STOP_MOVED, quyết định NEWS_DECISION và snapshot ID.
- position_<ticket>.csv: danh tính, R, thời điểm mở ban đầu, checksum.
- risk_day/attempts/halt/risk_exits và close_required: trạng thái quản lý bền vững.
- news_reduce/news_reduce_done: dành quyền và xác nhận partial một lần mỗi sự kiện.
- forex_closed_<ticket>.csv: giá trị ròng của ticket trong MT4 History đã tải.
- forex_tester_complete.csv: mốc kết thúc Forex, không phải seal Binary/training.

Không trộn FX_V222 với BIN Binary hoặc dữ liệu live với Tester. Chỉ có source,
không EX4/model huấn luyện. Kiểm thử C++/Python mô phỏng broker không thay thế
MetaEditor compile, Windows MT4/demo, kiểm định khớp lệnh hoặc hiệu quả thị trường.
