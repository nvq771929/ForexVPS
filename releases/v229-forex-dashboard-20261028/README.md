# V2.29 Forex Dashboard + nhận diện thư mục tin

Gói full gồm source Expert V229, Includes, bốn preset Demo/Real, .cmd, Python tools và LearningSupervisor. Đọc FOREX_DASHBOARD_V229_VI.md sau giải nén. Không có EX4.

Dashboard Forex dùng bảng nền/chữ lớn, tập trung tài khoản dùng chung, rủi ro, vị thế EA, spread, tin, bảo vệ lệnh và ba mức quyền giao dịch. Binary UI và 39 header đã giao ở V228 được giữ nguyên.

Start-Forex-News nhận Data Folder, MQL4, Files, FX_V222 hoặc LIVE_* hợp lệ; luôn ghi bridge chung FX_V222/news_calendar.csv. Không sửa nhật ký Binary/lệnh.

375 kiểm thử source + 76 LearningSupervisor đạt, không skip. C++/API shim không phải compile MetaEditor, kiểm chứng hiển thị DPI Windows hoặc bằng chứng lợi nhuận. Bật/tắt Dashboard đã đối chiếu kết quả lệnh và nhật ký từng byte trong mô phỏng.

Nếu chỉ cập nhật Forex, thay Expert trên đúng chart Forex; có thể giữ chart Binary V228. Không gắn manager Forex thứ hai hoặc xóa state. Kiểm tra F7 > Common > Allow live trading trên chart Forex và AutoTrading chung của MT4. Demo giữ ForexAllowRealTrading=false. Preset Real vẫn có quyền Real khi mọi điều kiện đạt.

Chỉ chạy một worker Forex news cho mỗi Data Folder; Ctrl+C worker cũ trước khi mở bản script mới. Worker Binary riêng có thể chạy cùng lúc.

Source ở ../../v229_forex_dashboard_rc1; nhánh Git feature/v229-forex-dashboard. remote_backup_verified=false trong ZIP mô tả thời điểm đóng gói trước khi push; xác nhận remote được lưu riêng sau đó.
