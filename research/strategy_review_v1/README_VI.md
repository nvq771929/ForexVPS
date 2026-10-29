# Strategy Review v1 — BO và Forex, ngoại tuyến

Đây là bộ nghiên cứu Python/C++, không phải EA hoặc bản nâng cấp vận hành. Giữ nguyên V229 và các bản nghiên cứu trước. Đọc `STRATEGY_AUDIT_VI.md` và `protocol.json` để biết khác biệt giữa proxy OHLC và backtest native/platform.

Protocol đã được đóng băng trước vòng điểm kinh tế này. Năm hợp đồng cố định,3mức payout BO và6kịch bản Forex mỗi model tạo45luồng mô tả; không tối ưu tham số hoặc chọn model theo kết quả. Dữ liệu đã được xem mô tả, nên không có claim holdout mới. Không có model được train/activate.

## Chạy lại

Cần Python3, g++ C++17 và `tzdata==2026.4` (đã có trong môi trường dự án). Tại thư mục này:

```bash
python -m unittest discover -s tests -v
python screen.py --source /path/EURUSDz5.csv --output /path/new-screen-directory
```

Thư mục output phải chưa tồn tại. Input của protocol v1 được ràng buộc SHA256 `af3bc3327806ee6ab2d8f92921b61b6e418f72646b49dd86a2155c8f02e5877c`. Dữ liệu mới cần một protocol phiên bản mới, giữ protocol/outputs cũ; không tự thay lịch sử mà vẫn gọi là cùng thử nghiệm. Không đưa source CSV hoặc outputs riêng vào Git.

`native_scan.cpp` là bản trích frozen của lõi Market/Forecast/Contract với shim để tái tạo candidate, không có kết nối broker hoặc OrderSend. Scanner dùng64nến đóng liên tục; vòng native hiện có được đối chiếu từng byte với lần quét đã kiểm tra trước. Hai model legacy chỉ dùng candidate của lõi này, không phải bộ lọc xác nhận/LOCK/news/model của EA.

## Đầu ra

- `run.json`: hash input/protocol/code, audit dữ liệu, coverage, số kịch bản và các giới hạn.
- `native_scan.csv`: candidate scan, không phải lệnh.
- `signals.csv`: thời điểm anchor/entry dự kiến, hướng, ATR; tính chỉ từ quá khứ.
- `reference_trades.csv`: toàn bộ nhãn BO tham chiếu và vị thế Forex mô phỏng, gồm outcome UNAVAILABLE.
- `summary.csv`: thống kê mỗi hợp đồng/kịch bản; CI95% block bootstrap theo37tuần quan sát của input hiện tại,2.000lần mặc định.
- `breakdowns.csv`: tháng broker và phiên tại entry ở kịch bản chính (BO82%, Forex cost_addon/stop_first).
- `session_offset_sensitivity.csv`: phân nhóm lại theo giả định brokerUTC−1/UTC0/UTC+1. Mặc địnhUTC0 chưa được xác minh cho toàn lịch sử.

Các file kết quả giữ nhãn `BO_MT4_REFERENCE` hoặc `FX_REFERENCE_NOT_EA`. Không nhập chúng vào bộ học/live ledger như các tín hiệu đã phát thực tế. Weekly CI là mô tả; chưa điều chỉnh chọn lọc/nhiều phép thử và không đủ để promote.

## Hợp đồng kinh tế và giới hạn

BO dùng Bid mở nến entry và Bid mở nến tiếp theo sau5phút; TIE hoàn tiền ở phép chính, có độ nhạy TIE thua. Các mức payout70/82/90% là giả định, không là lịch sử Olymp Trade. Không mô phỏng độ trễ thao tác, quote platform hoặc cooldown phát lệnh native.

Forex vào BUY ở BidOpen+spread giả định, SELL ở BidOpen; thoát BUY theo Bid và SELL theo Ask tái tạo. SL=max(1.5ATR,6pip), làm tròn ra ngoài theo tick0.00001, reject nếu>30pip; TP2R, timeout60phút; một vị thế mỗi model/scenario, không vào lại ở nến còn vị thế tại open. SL này không phải structural SL đầy đủ của V229. MFE/BE/trailing/news/risk caps, lot/margin, permission và tick guards chưa mô phỏng. Portfolio các model không được gộp làm một tài khoản.

Spread được mô phỏng trong giá, commission và slippage roundtrip trừ vào P&L. Cost cases là giả định đã công bố, không xác nhận phí broker. R chuẩn hóa theo khoảng SL ban đầu, không phải lợi nhuận USD hoặc equity curve có compounding. Gap giá adverse được khớp theo open quan sát; gap thiếu nến tạo UNAVAILABLE thay vì tự điền. Cùng nến chạm SL/TP được báo ở hai thứ tự; đó là độ nhạy, không tái dựng tick.

Những trade chưa rõ kết quả không được tính thành0lãi/lỗ. Tổng/CI/PF/drawdown chỉ trên tập resolved; kiểm tra coverage trước khi diễn giải. Positive screen vẫn cần tick/platform và kiểm định mới; negative screen không tự chứng minh toàn bộ EA native thua vì proxy bỏ những điều kiện khác.

## Xác minh

24 kiểm thử kiểm tra causality/prefix thời gian, cấu trúc các giả thuyết cả hai hướng, settlement BO, Bid/Ask Forex, phí, ambiguous exits, gap, timeout, không chồng vị thế, stop cap/rounding và bootstrap. Kiểm tra ledger ngoài Git còn đối chiếu phí giữa các cost case, chênh lệch payout và hai thứ tự chạm barrier. Không có thay đổi source vận hành nên không chạy lại những bộ test EA không liên quan cho bộ nghiên cứu độc lập này.
