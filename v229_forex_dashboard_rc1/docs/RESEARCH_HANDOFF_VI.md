# Trạng thái nghiên cứu theo bàn giao trước khi mất môi trường

Đây là thông tin từ bản bàn giao của người dùng, không phải kết quả vừa chạy
lại trong phiên phục hồi 28/10/2026. Source nền là V2.26; dữ liệu thị trường và
gói nghiên cứu mới hơn chưa được phục hồi cùng ba phần ZIP source.

- Binary chỉ phát CALL/PUT/WAIT, Dashboard và dữ liệu nghiên cứu; Forex gửi và
  quản lý lệnh. Kết quả Binary theo tín hiệu/giá Exness, không phụ thuộc người
  dùng có vào lệnh thủ công hay không. Không dùng report broker Total trades
  làm kết quả tín hiệu Binary.
- Không tự thay chiến lược, ATR, xác nhận, giờ khóa hoặc freshness; không dùng
  tương lai làm feature. Không đổi bản quan sát thành bộ lọc chính thức.
- TCN chưa chứng minh vượt baseline trong lượt đánh giá đã trao đổi. Không có
  cơ sở kết luận chỉ cần học thêm sẽ giải quyết được. Không có model mới được
  chấp thuận điều khiển CALL/PUT hoặc Forex; ưu tiên AI cục bộ, không API trả phí.
- Nếu sau này được phép bật đối thoại, tư vấn phải hợp lệ và hoàn tất trước hạn
  khóa. Không kịp/không hợp lệ giữ quyết định native; không suy diễn ủy quyền
  đối thoại cũ thành yêu cầu bật lại trong lần phục hồi này.
- Phân biệt tuổi trạng thái kể từ xác nhận với tuổi toàn bộ xu hướng. Chưa có
  đồng hồ biết chính xác đầu/giữa/cuối chu kỳ.
- Chưa chọn thời hạn thay thế 5 phút; 30 phút chưa cho ưu thế ổn định.
- Nhóm 46 tín hiệu giả định với ATR nới xuống 1,5 pip có số đã trao đổi: 10 phút
  30 thắng/16 thua; 30 phút 23/23. Đây là phản thực tế, mẫu nhỏ, không phải giao
  dịch native; không dùng để nới ATR vận hành.
- Nhóm 417 tín hiệu nguồn cũ phải giữ riêng với HST tải lại. Không ghép thành
  một tỷ lệ thắng 12 tháng. Tester, forward, Demo/Real và nguồn lịch sử tách biệt.
- Guard sau khóa 3 giây từng hủy nhiều chuẩn bị do khoảng cách tick Tester.
  Không nới guard rồi coi các lệnh giả định là native.
- Lượt live V2.26 đã trao đổi có 8 sự kiện hủy liên quan thời gian của một chuẩn
  bị, không phải 8 lệnh thua. Raw cũ không ghi đủ tick bị từ chối; chưa xác định
  lỗi do Windows, mạng hay broker. V2.28 phục hồi bổ sung quan sát, không sửa giờ.
- Source V2.28 cũ được báo có 353 kiểm thử source và 76 supervisor, nhưng source
  và log của nó không có trong gói phục hồi. Chỉ dùng log của bản phục hồi này
  cho kiểm chứng hiện tại. C++ shim không chứng minh compile MetaEditor, pilot
  Windows, chất lượng tín hiệu hoặc lợi nhuận Forex trên Exness.

Bước vận hành tiếp theo sau khi đóng gói: compile MetaEditor, pilot hai chart
trên Demo và đối chiếu nhật ký. Không cần chạy lại 12 tháng chỉ để kiểm tra việc
đóng gói và hai chart. Mọi thay đổi chiến lược/model cần phạm vi riêng và bằng
chứng độc lập; công việc hiện tại chỉ phục hồi bàn giao source và cấu hình.
