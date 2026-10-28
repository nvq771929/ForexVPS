# Từ V2.19/V2.20/V2.21 sang V2.22 Forex

V2.19 đang chạy Tester để nghiên cứu Binary Option: tiếp tục đến hết, lưu dữ
liệu riêng và giữ bộ công cụ V2.19 để đánh giá. Không trộn Forex, Binary và
live thành một bộ học.

V2.22 kế thừa hòa vốn/trailing/né tin V2.21 và thêm bình quân cùng chiều có
giới hạn, OFF mặc định; xem AVERAGING_V222_VI.md. Mặc định BinaryOption giữ core,
guard và POD mô phỏng kế thừa; trong chế độ này không đặt lệnh broker.
Forex có hợp đồng quản lý lệnh riêng, không chuyển model/payout Binary thành
mô hình lợi nhuận Forex.

Giải nén/cài/compile theo INSTALL_V222_VI.md sau khi Tester cũ đã hoàn tất.
Bắt đầu Forex bằng preset Forex_Demo hoặc Forex_Tester, tag mới và root FX_V222.
Real được hỗ trợ nhưng mặc định chưa được phép gửi lệnh đến khi bật Input riêng.

Nếu sau này chạy Binary trên V2.22, chọn preset Binary ghi rõ TradingMode=0
và tag nghiên cứu riêng. Cache legacy vẫn thuộc nghiên cứu Binary, không
import vào Forex. Source và journal V2.19 không bị sửa bởi việc chuẩn bị V2.22.

Không đổi TradingMode hoặc Magic khi còn vị thế của EA. EA chặn chuyển sang
Binary nếu phát hiện lệnh Forex của nó, để tránh bỏ quản lý thời gian giữ.
Broker SL/TP còn tồn tại khi EA tắt, nhưng thoát theo thời gian cần MT4 online
và quyền giao dịch. Đọc FOREX_V222_VI.md trước khi bật real.

V221/V220 được giữ nguyên; không nâng cấp khi còn vị thế của bản cũ. V222
dùng Magic/root riêng và không tự nhận metadata vị thế của bản cũ. Live/demo V222 cần worker
Start-Forex-News.cmd; Tester không dùng lịch hiện tại để giả lập tin quá khứ.
