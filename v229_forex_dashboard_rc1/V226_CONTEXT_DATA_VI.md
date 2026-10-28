# V2.26 RC1 — dữ liệu có nguồn gốc và trạng thái khôi phục được

Đây là **bộ source đầy đủ**, gồm Binary và Forex kế thừa. Compile
`MQL4/Experts/EURUSD_M5_Intelligence_V226.mq4`. Thư mục Include V224 và các
hợp đồng nhật ký/model cũ giữ tên để tương thích. Bản này phát triển từ V2.25
kèm bản vá khởi tạo mảng; giữ bản V2.25 đã giao làm đối chứng.

## Những gì đã bổ sung

- Mỗi gói nến thực nhận bởi bộ quan sát được lưu nguyên giá/tick volume, thời
  điểm khả dụng, nguồn, offset, cấu hình và liên kết checksum với gói trước.
- Bootstrap ghi số vị trí yêu cầu, số nến thực nhận, lỗi CopyRates và seed.
  Không còn phải đoán 1.000 nến đến từ đâu khi đề nghị tối đa 4.800.
- Checkpoint giữ đầy đủ trạng thái số của engine: EMA, TR, các khung nến,
  trạng thái xác nhận và tuổi nhãn. Giữ hai checkpoint mới nhất; giữ toàn bộ
  gói nến đầu vào. Khôi phục kiểm tra danh tính và checksum, rồi replay phần
  đầu vào đã cam kết sau checkpoint, không đổi sang seed mới trong im lặng.
- Hợp đồng dữ liệu học giá riêng: chuỗi M5/M15/H1, đặc điểm thân/râu nến,
  chuyển động giá, tick volume và mặt nạ phần thiếu; **không dùng tuổi nhãn
  hoặc EMA làm đầu vào của bộ dữ liệu mới**.

Thuật toán quan sát RC1 được giữ nguyên. CALL/PUT, ATR 3 pip, T+1, kiểm tra
quote/khóa, sổ công bố và toàn bộ Forex không đổi. Không có model mới được
huấn luyện hoặc kích hoạt trong bản này. Source có công cụ chuẩn bị dữ liệu,
không có trọng số TCN đủ kiểm định hoặc quyền mới để điều khiển tín hiệu.

## Tuổi ổn định nghĩa là gì?

**Cùng một chuỗi đầu vào đã cam kết**, cùng seed, cấu hình và nguồn, khôi phục
checkpoint phải tiếp tục đúng trạng thái như chạy liên tục. Đây là mục tiêu
kiểm chứng restart. Nó không biến hai lượt mới bắt đầu từ hai đoạn lịch sử
khác nhau thành cùng tuổi nhãn, cũng không xác định tuổi thật của thị trường.

Ở nhánh dữ liệu học mới, đặc trưng dùng cửa sổ thời gian cố định và thời điểm
khả dụng; cùng cửa sổ đầy đủ phải cho cùng kết quả dù có thêm lịch sử cũ hơn.
Khoảng trống được đánh dấu bằng mask, không nội suy hoặc bịa nến để làm đầy.
Đây là cách loại sự phụ thuộc seed EMA/tuổi nhãn khỏi đầu vào nghiên cứu mới.

## Cài đặt và vận hành

1. Giải nén vào thư mục riêng; chép nội dung `MQL4` vào Data Folder/MQL4.
2. Compile `EURUSD_M5_Intelligence_V226.mq4` bằng MetaEditor. Môi trường phát
   triển chưa có MetaEditor; kiểm thử C++ không thay thế bước compile Windows.
3. Binary dùng chart EURUSD/EURUSDz M5. Preset
   `EURUSD_M5_V226_Embedded_Pilot_UTC0.set` bật quan sát, tắt Forex và tư vấn
   tác động. Offset UTC+0 chỉ áp dụng nguồn/giai đoạn đã được xác nhận.
4. Dùng InstanceTag V226 mới, không ghi chồng thư mục V225. Không cần chạy lại
   sáu tháng để tạo tập nghiên cứu vì dữ liệu lịch sử đã có được dùng lại.
5. Phần nhúng không cần CMD. Bộ học sâu và lịch tin vẫn là tiến trình ngoài
   như trước. Nếu chỉ kiểm tra giao diện/định dạng, chạy một lượt ngắn với tag
   riêng; không coi đó là bằng chứng cải thiện chiến lược.

Checkpoint hỗ trợ **khôi phục bộ quan sát khi gắn lại EA live với cùng tag**,
không nối lại một lệnh/episode đã hết. Quy tắc phục hồi native vẫn giữ nguyên.
Tester tiếp tục yêu cầu tag mới mỗi lượt và không thể bấm Start để nối tiếp
một bộ đã hoàn tất/dừng. V226 chưa được kiểm chứng checkpoint trên MT4 Windows.

## Các file mới

Trong `BO_V2/<tag>[_TESTER]_<symbol>/`:

- `embedded_context_v226_<session>.csv`: snapshot bối cảnh, asof, available,
  tuổi, cờ và trạng thái model chưa có. Contract V226_EMBEDDED_CONTEXT_V2.
- `embedded_v226/embedded_lineage_v226_<session>.csv`: metadata khởi tạo/restore.
- `embedded_v226/packets/embedded_packet_v226_<sequence>.bin`: gói đầu vào
  bất biến; nguồn gốc và checksum. Contract V226_CLOSED_M5_STREAM_V1.
- `embedded_v226/state/embedded_checkpoint_v226_<sequence>.bin`: trạng thái
  số cùng layout/terminal, contract V226_CONTEXT_CHECKPOINT_V1.

Packet được cam kết trước khi thay trạng thái quan sát; checkpoint được cam
kết sau. Mất điện giữa hai bước có thể replay phần packet còn lại. Giữ tối đa
hai checkpoint, còn packet không bị xóa. Checkpoint không phải định dạng model,
không được import vào tài khoản khác hoặc chỉnh tay.

Checksum giúp phát hiện hỏng dữ liệu cục bộ, không xác thực độc lập broker hay
chứng minh chống sửa ác ý. Reader Python chỉ đọc packet số với layout đã biết,
không giải tuần tự checkpoint chứa layout riêng của terminal, không dùng pickle.

## Khi khôi phục bị từ chối

Đổi nguồn/feed, symbol, policy, offset, bootstrap policy hoặc terminal/layout
sẽ không tự nối state. Checkpoint mới nhất hỏng **không tự rơi về bản cũ** rồi
quảng bá trạng thái liên tục. Thiếu/hỏng packet liên kết hoặc đứt chuỗi sẽ dừng
riêng bộ quan sát, báo nguyên nhân trên panel. Hãy giữ nguyên hồ sơ để chẩn đoán;
nếu cần bắt đầu lại, dùng tag mới để có lineage mới, không xóa bằng chứng.

Khi broker sửa nến đã tiêu thụ trong cửa sổ còn đối chiếu được, trạng thái là
HISTORY_CHANGED_NEW_INSTANCE_TAG. Gắn lại cùng tag sẽ tiếp tục gặp sai khác;
không ghi đè history cũ hoặc tự sửa nhãn trước đó. Nếu replay tail quá 4.800
packet, khôi phục native observer từ chối thay vì chạy vô hạn trong OnInit.

Các lỗi riêng này **chưa chặn CALL/PUT của lõi gốc**. Chức năng mới vẫn chỉ
quan sát; các guard dữ liệu/quote của lõi EA giữ nguyên. Không gọi đây là bộ
phát hiện gian lận hoặc cơ chế AI tự sửa chiến lược.

## Bộ dữ liệu học giá V226

`tools/prepare_price_behavior.py --plan <frozen_data_plan.json> --output <thư_mục_mới>`
dùng Python cùng requirements-learning.txt. Plan nêu rõ nguồn đã seal và hash
các biên bản audit; sửa đường dẫn khi chuyển máy nhưng giữ hash và quy tắc.
Không chạy code từ thư mục nhật ký được cung cấp.

Đặc trưng chỉ dùng nến đã đóng tại ANCHOR và đã quan sát trước thời điểm khóa
dự kiến 32 giây trước Entry. Không có dữ liệu trong tương lai hoặc giá Entry
trong tensor đầu vào. H1/M15 cần đủ thành phần đã biết; phần thiếu là mask.

Các tensor: 32 M5 × 9 kênh, 16 M15 × 9 kênh, 16 H1 × 9 kênh và bối cảnh phiên/
thời gian/độ phủ. Kênh gồm log return, thân/range/râu theo giá tham chiếu đã
đóng, log tick volume, gap, return_known, bar_known. Tick volume không phải
khối lượng thị trường tập trung. Không có chuẩn hóa học từ toàn dữ liệu;
scaler tương lai chỉ được fit trên train.

Nhãn chính: hướng giá **Entry+30 phút so với Entry**; 5 và 15 phút là đối chiếu.
Mỗi biên lấy TICK đầu tiên tại/sau mục tiêu, không muộn quá 2 giây, cùng session.
Thiếu giá giữ UNAVAILABLE (mã 9), hòa là mã 0, không biến thành LOSS. Đây là
nghiên cứu hướng BID mô phỏng, không phải kết quả giao dịch hoặc lợi nhuận.
Input Binary của EA vẫn chỉ có 5/10/15 phút; không nhập 30 vào Input hiện tại.

Tập gồm cả các ANCHOR mà EA chọn WAIT, không chỉ vài trăm publication. Ghép hai
nguồn theo quy tắc thời gian cố định; không đếm mẫu trùng giữa các lượt. Phân
đoạn train/inner validation/calibration/đánh giá hồi cứu theo thời gian, có
purge/embargo 18 giờ 35 phút và loại cửa sổ nhãn vượt ranh giới. Toàn bộ lịch
sử đã được nghiên cứu trước: phần đánh giá không phải holdout độc lập mới.

File NPZ chỉ chứa mảng số; đọc với `allow_pickle=False`. Metadata JSON/gzip và
manifest SHA256 giữ source, mẫu, giá biên, thời điểm khả dụng, phần thiếu và
partition. Dataset này là contract mới; không nạp thẳng vào script TCN legacy
hoặc lẫn model cũ rồi bật tác động lên EA. Bước sau mới là huấn luyện baseline/
TCN nhỏ theo protocol, kiểm định và tiếp tục quan sát mô hình đủ điều kiện.

## Giới hạn hiện tại

Không có model giao dịch mới, không có bằng chứng tăng tỷ lệ thắng, không tự
chặn tín hiệu bằng tuổi nhãn hoặc bộ lọc hướng chưa đạt kiểm chứng. Khoảng nghỉ
thị trường có thể làm cache thiếu nến; V226 lưu đúng cái thực nhận chứ chưa thêm
nguồn giá hoặc bù nến qua cuối tuần. Kiểm thử nguồn/corruption/restart trong gói
là kiểm thử phần mềm; kiểm chứng native MetaEditor và live vẫn phải thực hiện.
