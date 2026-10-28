# Chẩn đoán lượt và ngưỡng ATR V222

`analysis_slots_v222_<session>.csv` là observer riêng, không đổi bố cục BIN hoặc ghi lại các lượt V218 đã bỏ. Theo dõi các slot mà tiến trình thực sự thấy qua đồng hồ broker đã hiệu chuẩn; không suy rằng máy đang chạy trong các khoảng không có sự kiện.

Mỗi slot có các trạng thái chờ khi thay đổi và tối đa một FINAL. CREATED phải trỏ đúng ANCHOR BIN cùng sequence/giờ. MISSED_START_WINDOW giữ blocker cuối: WAIT_TICK, WAIT_HISTORY_BAR, HISTORY_UNAVAILABLE, QUOTE_TOO_OLD hoặc DISCONNECTED. ATTACH_OR_RECOVERY và COOLDOWN được tách riêng. STORAGE_ERROR của native luôn giữ fail-stop; lỗi ghi observer được báo riêng, không làm giả một ANCHOR đã ghi.

EA xử lý ENTRY/OUTCOME/LOCK trước việc tải history. Chỉ thử lại bước tạo ANCHOR trên tick hiện tại sau khi cache đúng bar đã có. Kiểm tra lại giờ thực, cửa sổ 15 giây và tuổi quote tối đa 3 giây sau công việc có thể chờ. `lastQuoteMs` vẫn là giờ quote thật, không phải giờ hoàn tất tải history. Không dùng giá OHLC thay tick hoặc tạo lùi tín hiệu khi đã quá hạn.

`slot_diagnostics_v222.json` kiểm tra identity và liên kết native. Dòng trỏ tới sequence ngoài native prefix sẽ chờ vòng cập nhật sau. Đồng hồ observer có thể đi sau sự kiện native cuối khi không có ANCHOR mới; báo cáo tách native_prefix_asof_ms và observer_asof_ms. Chỉ CREATED có sự kiện ANCHOR đối chiếu; trạng thái chờ/bỏ là dữ kiện observer cục bộ, không phải đầu vào mô hình. Slot đang chờ khi tiến trình dừng được báo open_observed_slots, không tự gán thành lệnh mất. Source cũ không có observer báo UNAVAILABLE_OLD_SOURCE, không coi là 0 lỗi. Báo cáo cần được đọc cùng nhật ký BIN và replay.

Trong `live_session_review.json`, `daily_session_diagnostics` tách ngày Việt Nam và phiên, có lý do chặn đầu tiên, ATR nhỏ nhất/trung vị/lớn nhất. `atr_eligibility_only` so sánh số dòng chỉ qua mức ATR 2/2.5/3 pip như thống kê thăm dò; các số này chồng nhau, không phải số setup/lệnh/thắng và không đề xuất tự đổi ngưỡng. Ngưỡng chạy EA vẫn 3–30 pip, shock vẫn 2.5 lần zoneATR trước nến kích hoạt.

Với các lượt bị chặn sớm, một số điều kiện sau chưa được dùng để hình thành setup; không suy hạ ATR là chắc chắn có lệnh. Muốn thay ngưỡng phải thử đầy đủ chiến lược, giá biên, thời gian và dữ liệu ngoài mẫu; không chọn chỉ từ một ngày.

V222 chỉ thử lại ANCHOR sau đồng bộ trên tick live. Tester giữ lịch lấy mẫu lịch sử cũ để các golden native, dữ liệu huấn luyện đã niêm phong và so sánh legacy không đổi. Metadata/điều kiện mới được kiểm tra forward riêng, không suy thành lợi thế từ lịch sử.
