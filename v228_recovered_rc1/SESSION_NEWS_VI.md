# Phiên và tin tức V2.22

Phiên dùng UTC được hiệu chuẩn từ tick broker và đối chiếu PC, TTL 15 phút monotonic. Mất/không chắc đồng hồ thì UNKNOWN; không dùng giờ máy của Tester để gán phiên lịch sử. Phiên là quy ước nghiên cứu có DST; London 08–17 giờ London, New York 08–17, Tokyo 09–18, Sydney 08–17 giờ địa phương. Bảng ngày/phiên dùng giờ Việt Nam UTC+7.

## Theo dõi tin

Nguồn hiện tại: `https://nfs.faireconomy.media/ff_calendar_thisweek.json`. Không yêu cầu tài khoản/key. Worker riêng tải mỗi 15 phút, timeout 10 giây, cache hợp lệ 1 giờ; bridge xuất mỗi 30 giây, TTL 15 phút. Không gọi mạng trong OnTick/OnTimer hoặc vòng phân tích candidate. Khả năng/độ đầy đủ của nguồn có thể thay đổi; phản hồi HTTP thành công không chứng nhận lịch đủ mọi tin.

Policy mặc định ở `news_policy_v222.json`:

| Đối tượng | Trước tin | Sau tin |
|---|---:|---:|
| High EUR/USD | 15 phút | 15 phút |
| Medium EUR/USD | 10 phút | 15 phút |
| ZEW trong danh mục ưu tiên | 10 phút | 15 phút |

Danh mục ưu tiên gồm đúng tên/currency của German ZEW Economic Sentiment, ZEW Economic Sentiment và German ZEW Current Conditions. Chỉ theo dõi nếu nguồn thực sự có dòng đó. Không tự chế Current Conditions nếu nguồn chỉ có sentiment. Low ZEW giữ nguyên nhãn Low và có lý do `PRIORITY_EVENT`; Low khác ngoài policy được ghi lý do không theo dõi. Không coi High/Medium/Low của nguồn là bản sao số sao Investing.

Có thể chỉnh cửa sổ/danh mục trong JSON rồi khởi động lại CMD nghiên cứu; các giá trị 0–120 phút, tổng trước+sau phải dương, mode phải OBSERVE_ONLY. Policy sai trả lỗi, không lặng lẽ biến thành lịch trống. Policy có SHA256 trong bridge/báo cáo để đối chiếu. Lịch sử trước lúc đổi policy không được sửa lại.

Vùng cảnh báo xét **toàn bộ khoảng vào–hết hạn**, nên có thể cảnh báo sớm hơn mốc “trước tin” nếu một kỳ hạn sắp vào giao với vùng đó. Dashboard ghi tên, mức gốc, giờ/ngày Việt Nam, thời gian còn lại hoặc đã công bố. Popup `LICH TIN QUAN SAT` phát một lần theo sự kiện/giờ/policy khi `EnableNewsAlerts` và `EnableAlerts` bật; không phải CALL/PUT. Sổ `news_alert_v222_*.csv` chỉ ghi ý định thông báo, delivery UNCONFIRMED, không chứng minh người dùng nhận popup. Lỗi sổ cảnh báo được báo trên Dashboard và không đổi quyết định giao dịch.

Tin vẫn **QUAN SÁT / CHƯA LỌC TÍN HIỆU**. Không hủy tín hiệu đã công bố, không tự chặn native, không đặt lệnh theo tin trong bản này.

## Ý nghĩa trạng thái

- NEWS_RISK_WINDOW: kỳ hạn đang xét giao với vùng của sự kiện theo policy.
- NEWS_CLEAR: cache còn hợp lệ/phủ thời gian đang xét và không giao vùng sự kiện đã chọn; không có nghĩa thị trường an toàn hoặc không có tin bất ngờ.
- NEWS_NO_RELEVANT_EVENTS: nguồn trả dữ liệu nhưng không có sự kiện EUR/USD trong scope.
- NEWS_NO_TRACKED_EVENTS: có EUR/USD nhưng không sự kiện nào thuộc policy hiện tại. Tách khỏi CLEAR.
- NEWS_UNKNOWN, NEWS_STALE, NEWS_CLOCK_UNCERTAIN, NEWS_TIME_UNCERTAIN: thiếu/sai/già dữ liệu hoặc giờ không đủ chắc chắn; không được đổi thành CLEAR.

Bridge schema2 thêm ID sự kiện, giờ công bố, currency, mức gốc, lý do theo dõi, provider, policy SHA và số dòng scope/tracked. Giữ đọc schema1 lịch cũ High-only. Không đưa các cột mới vào feature contract hoặc model tự động.

Báo cáo `news_source_review_v222.json` liệt kê từng sự kiện nhận được, reason theo dõi/loại, last fetch status, độ mới, raw SHA, caveat phủ lịch và policy. Snapshot chuẩn hóa cùng raw body mới được đưa vào candidate_review_v222.zip nếu có; cache V218 cũ có thể thiếu raw body. `Check-News.cmd` cũng tạo báo cáo này. Không cần gửi cả môi trường Python/source để kiểm tra tin ở các lần sau.
