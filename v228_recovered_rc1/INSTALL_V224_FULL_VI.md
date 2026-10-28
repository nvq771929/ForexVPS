> Gói hiện tại là V2.25 RC1. Cài/pilot theo [EMBEDDED_CONTEXT_V225_VI.md](EMBEDDED_CONTEXT_V225_VI.md); tài liệu bên dưới mô tả module V2.24 kế thừa.

# Cài bộ hoàn chỉnh V2.24 Full RC2

Gói này có EA, Include, Presets, Indicator, supervisor đánh giá tín hiệu,
worker tư vấn trước khóa, công cụ nghiên cứu và kiểm thử. Không cần source
V2.23 để compile/chạy V2.24. Chưa có `.ex4`: cần compile bằng MetaEditor.

1. **Giữ V2.23 chạy xong Tester hiện tại.** Lưu source, dữ liệu đầy đủ, `.set`
   và report của lượt đó trước khi đổi bản. Không xóa dữ liệu V2.23.
2. Giải nén V2.24 vào thư mục riêng. Chép nội dung `MQL4` vào Data Folder
   MT4 tương ứng: `Experts`, `Include`, `Presets`, và `Indicators` nếu dùng.
   Các tên V224 tách khỏi V223. Không gỡ các EA/indicator khác trong Data Folder.
3. Compile `MQL4/Experts/EURUSD_M5_Intelligence_V224.mq4`. Gửi toàn bộ lỗi nếu
   có; chưa có kiểm thử MetaEditor/Windows trong môi trường phát triển này.
4. Kiểm thử Binary trên **EURUSD M5**. Để nguyên hai Input tư vấn OFF ở lần
   kiểm tra cơ sở, hoặc dùng preset `EURUSD_M5_V224_Binary_Fresh.set`.
5. Để kiểm tra thu thập trước khóa, dùng
   `EURUSD_M5_V224_Binary_Dialogue_Tester.set` trong một lượt pilot với tag mới.
   Dùng Every Tick và ghi đầy đủ input; không cần Visual Mode để thu dữ liệu.
   Tester chỉ thu snapshot, không dùng tư vấn ngoài để chặn tín hiệu.
6. Sau pilot, đọc `LEARNING_DIALOGUE_V224_VI.md` để chuẩn bị dữ liệu, kiểm thử
   worker và chạy quan sát live. Preset live quan sát là
   `EURUSD_M5_V224_Binary_Dialogue_Observe.set`; cờ tác động vẫn OFF.

`Install-Learning-Supervisor.cmd` cài Python dependencies trong `.venv` riêng
của `LearningSupervisor`. `Start-Learning-Dialogue.cmd` khởi động worker hỏi/đáp.
Các CMD learner nhẹ/cấp tin V2.24 hiện có phục vụ chức năng khác, không bị
worker tư vấn thay thế; đặc biệt giữ tiến trình cấp tin nếu muốn cập nhật lịch.
Không chạy hai bản cùng loại ghi cùng nguồn/bridge. Khởi đầu kiểm tra từng
thành phần, theo dõi tài nguyên và tick, chưa giả định máy anh đủ tải nhiều job.

Đánh giá kết quả Tester V2.23 đã hoàn tất vẫn dùng supervisor nhánh sổ tín hiệu:

```bat
cd /d "D:\EA_V224_Full\LearningSupervisor"
.venv\Scripts\python.exe run_supervisor.py cycle --source "D:\Data\V223_COMPLETED_TESTER_EURUSD" --output "D:\Research\V223Review" --broker-utc-offset-minutes 0
```

Chỉ dùng offset 0 khi toàn giai đoạn đã xác nhận UTC+0. Đánh giá V2.23 và huấn
luyện tư vấn pre-lock là hai nhánh khác nhau, không chuyển model LOCK cũ thành
model tư vấn sớm. V2.24 chỉ tư vấn khi có dữ liệu và bằng chứng đúng nhánh.

Forex vẫn có chế độ và bộ preset riêng, hỗ trợ hậu tố EURUSDz trên M5. Rủi ro
mặc định 0,5%, các guard margin, SL/TP, trailing, news và basket giữ nguyên.
Quyền đặt lệnh tài khoản thật vẫn cần Input riêng. Tư vấn Binary không điều
khiển Forex. Không chạy đồng thời hai EA Forex cùng quản lý một nguồn lệnh.

Lưu và nén toàn bộ thư mục journal khi gửi nghiên cứu; bản V2.24 bật trao đổi
cần giữ cả thư mục con `advisory_v224`. Dừng đúng tiến trình ghi trước khi sao
chép một bộ hoàn chỉnh. Dữ liệu runtime nằm ngoài thư mục source để dễ sao lưu.

## Bổ sung RC3

Trợ lý cục bộ dùng `Install-Local-AI-Assistant.cmd` và `Start-Local-AI-Assistant.cmd`; xem [LOCAL_AI_V224_VI.md](LOCAL_AI_V224_VI.md). Giữ V2.23 hoàn tất lượt Tester 01/04–16/05/2026 trước khi pilot. Không có weights LLM/model 30 phút hoặc quyền can thiệp mới trong gói.
