# V2.22 — Tín hiệu đã phát và thời gian giữ lệnh

V2.22 dành cho EURUSD M5, Olymp Trade demo vào tay. Bộ đếm mới đánh giá tín hiệu bằng Bid MT4; EA không biết anh có đặt lệnh trên Olymp hay không.

## Đọc cảnh báo

Ví dụ với kỳ hạn mặc định:

```
EURUSD PUT | GIU 5 PHUT (1 M5)
Vao 06:50:00 | Het han 06:55:00 | Broker
Cho dung moc vao | ID ... | MT4 mo phong
```

PUT là hướng giảm, CALL là hướng tăng. Popup xuất hiện trước giờ vào để chuẩn bị. Thời gian còn 28 giây là thời gian chờ, **không phải thời gian giữ lệnh**. Chờ đúng giờ vào đã ghi; thời điểm hết hạn cũng phải khớp. Giờ Broker không mặc nhiên là giờ Việt Nam hoặc giờ hiển thị trên Olymp. Nếu không đối chiếu được hai mốc, bỏ qua tín hiệu demo đó; không vào bù trễ.

| DemoExpiryMinutes | Thời gian giữ | Số nến M5 |
|---|---|---|
| 5 — mặc định | 5 phút | 1 |
| 10 | 10 phút | 2 |
| 15 | 15 phút | 3 |

Kỳ hạn lấy cố định từ Inputs, được chốt cùng hướng và lịch. V2.22 chưa tự chọn kỳ hạn tối ưu. Một tín hiệu chỉ có một kỳ hạn. Muốn đổi kỳ hạn, dừng bộ cũ và dùng InstanceTag mới vì policy đã đổi.

## Sau khi tín hiệu chính thức xuất hiện

Dashboard giữ hướng, ID, kỳ hạn, giờ vào và hết hạn của tín hiệu đã chốt. Native vẫn kiểm tra quote/T+1/LOCK như cũ. Nếu native hủy ENTRY sau khi đã công bố, Dashboard và cảnh báo ghi riêng “TIN DA PHAT DUOC GIU | CANH BAO NATIVE”; sổ tín hiệu không xóa hoặc đổi hướng đã công bố.

Giữ bản ghi không có nghĩa tín hiệu vẫn an toàn trước mọi diễn biến thị trường. Nó bảo đảm kết quả được theo dõi trung thực kể cả khi anh đã chuyển sang màn hình Olymp. Cảnh báo dữ liệu vẫn có hiệu lực, không bảo đảm tránh LOSS. Sau mốc vào, dòng chính chuyển sang “TIN DA PHAT … CHO KET QUA”, rồi “GAN NHAT … WIN/LOSS/TIE/UNAVAILABLE”; không tiếp tục mời vào lệnh muộn. Trước khi tín hiệu mới được công bố, các giờ đang chuẩn bị có nhãn “CHUA PHAT”.

Dòng **MT4 tin hieu** thống kê tín hiệu chính thức đã công bố. Dòng **ENTRY** thống kê mô phỏng native vượt qua toàn bộ guard đến ENTRY. Hai bộ đếm có thể khác nhau. Ví dụ một PUT đã phát, sau đó native hủy vì gap 4 giây: ENTRY có thể bằng 0 nhưng tín hiệu đã phát vẫn nhận LOSS nếu đủ hai giá và giá hết hạn cao hơn giá vào.

## Cách tính kết quả

Sổ mới có hợp đồng `V218_MANUAL_PUBLICATION_V1`, tách khỏi POD/BIN và tập nhãn học cũ.

- Giá vào: tick EURUSD hợp lệ đầu tiên từ giờ vào đến **+2 giây**, gồm cả hai đầu mốc.
- Giá hết hạn: tick hợp lệ đầu tiên từ giờ hết hạn đến **+2 giây**, gồm cả hai đầu mốc.
- Tick hợp lệ: Bid/Ask hữu hạn, Bid > 0, Ask ≥ Bid và spread không vượt giới hạn cấu hình. Cần tick thật tại thời điểm ghi; Timer không tạo giá.
- CALL: giá hết hạn cao hơn giá vào là WIN; PUT: giá hết hạn thấp hơn là WIN. Giá bằng nhau là TIE. So sánh tại độ chính xác lưu sổ 10 chữ số thập phân.
- Không có giá hợp lệ trong một trong hai cửa sổ: **UNAVAILABLE / Thieu gia**. Không lấy giá LOCK, quote cũ, nến OHLC hoặc giá sau cửa sổ để bù. EA phải đang chạy và ghi dữ liệu thành công ở các mốc đó.

Đây là kết quả MT4 mô phỏng, không phải kết quả Olymp: nguồn giá, thời điểm thao tác và quy tắc hết hạn có thể khác. Số WIN/LOSS mới không tự kích hoạt model hoặc tham gia bộ học native hiện tại.

## Lưu trữ, khởi động lại và báo cáo

Mỗi ID có các CSV bất biến trong cùng journal: `manual_v218_1_<ID>.csv` là công bố, `2` giá vào, `3` giá hết hạn, `4` kết quả. `5` đánh dấu bị giữ lại nếu ghi sổ xong đã quá thời hạn công bố; trường hợp này không phát popup, không tính là tín hiệu chính thức. File tạm kết thúc bằng `.tmp` chỉ dành cho ghi nguyên tử.

Sổ được ghi trước khi gọi popup; ghi quá hạn hoặc lỗi lưu trữ sẽ chặn phát mới. Khởi động lại phục hồi các bản ghi hợp lệ, đối chiếu LOCK native và không phát lại ID cũ. Nếu máy tắt qua mốc giá, kết quả thiếu giá; không tái tạo từ lịch sử để gán thắng/thua. Nút Pause dừng tín hiệu mới nhưng vẫn theo dõi kết quả của tín hiệu đã công bố khi EA còn chạy.

`alerts_enabled` chỉ lưu cấu hình popup lúc công bố. `receipt=UNCONFIRMED` luôn thể hiện chưa xác nhận anh nhận thông báo; không có xác nhận khớp lệnh thủ công. Mất điện giữa ghi sổ và popup có thể để lại bản ghi mà người dùng chưa thấy. Không coi tổng công bố là tổng giao dịch thực tế.

`Start-Candidate-Research.cmd` bổ sung `manual_signal_review.json` và `manual_signals.csv` trong `candidate_review_v222.zip`. Báo cáo đối chiếu checksum, LOCK native và các dòng replay được tham chiếu; replay dùng độ phân giải EURUSD 1e-5 của hợp đồng cũ. EA vẫn yêu cầu RecordReplayInputs=true. Khi dùng Tester compact, sequence 0 chỉ có bản ghi quote native của sổ mới, không có đối chiếu replay độc lập. Đây vẫn là chứng cứ local, không phải xác thực từ broker.

Không xóa/sửa `.tmp`, checksum hay sequence để ép bộ đếm chạy. Nếu báo lỗi sổ, giữ nguyên thư mục để chẩn đoán, dừng các tiến trình rồi sao lưu. Không trộn thủ công journal/tag khác nhau. Source V217 không có sổ công bố này nên **không hồi tố tín hiệu V217 từ LOCK**: popup V217 có thể chưa được phát do kiểm tra muộn.
