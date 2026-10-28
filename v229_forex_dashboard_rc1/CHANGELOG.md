# V2.26 RC1 — 2026-10-25

- Immutable closed-M5 input packets and bootstrap/restore lineage metadata.
- Source/layout/config-bound observer checkpoint and checked input-tail replay.
- Separate fixed-window causal multi-frame price research dataset contract.
- No native action/Forex/model activation change; no new trained weights.

# V2.25 RC1 — 2026-10-24

- Native frozen RC1 M5/M15/H1 context and observed trend age, observer only.
- Bounded closed-bar bootstrap on initialization; verified clock required.
- Independent compact panel and journal with distinct asof / availability.
- No trained weights, signal overrides, online deep training or Forex changes.
- Full inherited source bundle. See EMBEDDED_CONTEXT_V225_VI.md and validation.

# V2.24 Full RC3 — 24/10/2026

- User-requested continuation of V2.24 in an isolated checkout before first compile; delivered RC2 and active V2.23 remain preserved.
- Added read-only local AI assistant with integrity-checked native/anchor ingestion, unchanged RC1 context engine, grounded explanations and daily data progress.
- Optional loopback-only Ollama fact/question selection; no cloud API, pretrained weights, generated probabilities or execution actions.
- Added assistant launcher, example config, separate HTML/JSON status and source-bound Common Files telemetry in the learning monitor.
- Native EA/Include/Forex unchanged; existing dialogue effects remain OFF by default. No trained 30-minute model, MetaEditor/Windows validation or market-performance claim.

# V2.24 Full RC2 — 2026-10-23

- Complete EA/source bundle with separate before-lock consultation worker.
- Explicit enable/effect Inputs, default OFF, Binary-only KEEP/WAIT/ABSTAIN.
- Repeated real pre-lock snapshots; no pseudo-LOCK feature conversion.
- Missing/late/invalid/unqualified/changed advice preserves native decision.
- Cached finalization before publication; replies cannot change a locked signal.
- Tester collection only, dedicated pre-lock training and independently audited
  prospective EA-received forecasts before effects. No trained model shipped.
- Native POD, strategy parameters, price guards and Forex modules preserved.
- Existing V2.23/RC1 delivered artifacts remain unchanged.

# V2.24 Binary loss research RC1

Added a read-only Binary postmortem: causal native LOCK inputs, recorded-tick excursions and minute timing, matched winning/loss cohorts and day-block uncertainty. No strategy/ATR/hold/quote guard change or fitted filter. Forex components are preserved byte-for-byte from V222. Existing V219 sealed data remain readable.

# V2.22 bounded averaging RC1

- Optional one same-direction addition after a new confirmed M5 setup, at a better price.
- Reserve 70% of a shared 0.5% basket budget for the first order; smaller addition, no stop widening.
- Persistent basket links, original hold deadline, weighted break-even/trailing and full basket news exits.
- Unknown fills never trigger blind re-entry; known closed legs trigger closing the survivor.
- Projected margin-level/free-equity reserves also apply to normal first orders.
- Averaging OFF by default; explicit Averaging_Tester preset for comparison, not a profitability claim.
- Frozen V221 source unchanged; Binary core and long-running V219 research remain separate.

# V2.21 management/news RC1

- Forex break-even and ATR trailing, persistent initial R and original hold deadline.
- Daily attempts/loss streak/cooldown, own emergency and daily-loss exits, broker schedule.
- Durable close requests with backoff, conservative partial-close recovery.
- Separate live Forex news worker and fail-closed calendar gate; Medium/High and priority events.
- Full/partial pre-news policy with immutable decision IDs; no historical-news validation yet.
- No strategy/ATR guard change or pretrained Forex model.

# V2.20 Forex RC1

- Input TradingMode: mặc định BinaryOption, hoặc Forex đặt lệnh trực tiếp MT4 Exness.
- Forex hỗ trợ demo và real, real mặc định chặn đến khi bật ForexAllowRealTrading.
- Tính lot theo 0,5% min(Balance,Equity), tick value/tick size thực; làm tròn xuống, kiểm tra margin/min lot/spread/stops.
- SL theo cấu trúc + ATR, TP mặc định 2R, giới hạn giữ tối đa 60 phút. Mỗi lúc một exposure EURUSD; không grid/martingale.
- Chỉ quản lý symbol/Magic own; Broker SL/TP gửi cùng OrderSend, không naked fallback. Kiểm tra risk/protection sau fill.
- Intent flush trước gửi, không retry mù; timeout không rõ được latch review. Khôi phục risk ngày/halt, khóa ownership theo account/server/EURUSD.
- Chặn lệnh mới tại equity-day limit mặc định 2%; mốc là quote đầu EA ghi trong broker day, không giả định biết equity nửa đêm nếu mới gắn giữa ngày.
- Journal Forex tách FX_V222, không nhận model/labels Binary. Giữ R10 Binary/POD/feature contracts, bổ sung test bảo đảm Binary không gọi OrderSend.
- Preset Forex_Demo/Forex_Tester; bộ Forex không cần CMD Python. Chưa có bộ lọc lịch tin, model Forex đã fit hoặc ATR theo phiên được kích hoạt.
- Source-only RC1; chưa compile MetaEditor hoặc kiểm thử broker Windows. Giữ nguyên V2.19 đang chạy lượt Tester nghiên cứu.

# V2.19 — 21/10/2026

- Compile fix 1: đổi tên tham số `final` thành `isFinal` trong SlotDiagnostics.mqh vì `final` là từ khóa MQL4. Đồng bộ mirror và thêm kiểm tra khai báo từ khóa mà bộ mô phỏng C++ không phát hiện. Chỉ sửa cú pháp; giữ nguyên logic, schema và dữ liệu thu thập.
- Sửa vòng đời tạo ANCHOR khi cache lịch sử còn thuộc nến trước và tick kế tiếp đến quá cửa sổ. Xử lý giá/ranh giới trước, đồng bộ history rồi thử lại bước tạo ANCHOR trên tick hiện tại; kiểm tra lại thời gian/tuổi quote và giữ timestamp quote thật.
- Observer V222_ANALYSIS_SLOT_V1 ghi lý do chờ/bỏ qua/tạo lượt; báo cáo đối chiếu với BIN, tách từng phiên chạy và không dựng lại slot lịch sử.
- Policy V222_NEWS_TRACKING_V1 theo dõi Medium/High EUR/USD, danh mục ưu tiên ZEW giữ nguyên mức Low của nguồn. Bridge schema2 có metadata đầy đủ, tiếp tục đọc schema1 High-only.
- Dashboard và popup quan sát tin có tên/mức gốc/giờ VN/đếm ngược. Ý định popup được lưu để tránh lặp qua restart; không xác nhận đã nhận thông báo hay đã đặt lệnh.
- Lưu raw response mới cùng snapshot nhận tin; candidate_review_v222.zip có báo cáo theo dõi/loại sự kiện và slot. Các trạng thái rỗng/không theo dõi/không rõ/quá hạn tách khỏi CLEAR.
- Báo cáo ATR và lý do chặn theo ngày Việt Nam/phiên. Ngưỡng chạy vẫn 3–30 pip, guard sau LOCK 3 giây, kỳ hạn/ledger tín hiệu đã công bố không đổi. Không đưa metadata mới vào native model, không kích hoạt deep model.
- Giữ nguyên POD/schema/logic và các hợp đồng cache/học/manual cũ, source namespace V222 và mirror MQL4 đồng bộ. Source sau chốt bản V2.19 bắt đầu V2.22.

# V2.18 — 19/10/2026

- Sổ tín hiệu chính thức bất biến, phục hồi/dedup qua restart. Giữ hướng/ID/lịch sau native cancellation, đối chiếu LOCK và lỗi lưu trữ chặn phát mới.
- Alert đặt hướng/kỳ hạn 5/10/15 phút (1/2/3 M5) lên đầu; Dashboard giữ lịch, cảnh báo dữ liệu riêng và không mời vào muộn.
- Kết quả tín hiệu theo tick Bid MT4 trong [mốc, mốc+2 giây], gồm native bị hủy sau công bố; thiếu giá là UNAVAILABLE. Hai bộ đếm manual-publication và native ENTRY độc lập.
- Báo cáo manual_signal_review.json/manual_signals.csv trong candidate_review_v218.zip; nhãn mới không tham gia mô hình native. Không suy popup V217 từ LOCK.
- Giữ toàn bộ R10 guards, model/cache/session/news contracts; source MetaEditor property sửa thành 2.18. Bản source kế tiếp V2.22.

# V2.17 — 19/10/2026

- Sửa SESSION_UNKNOWN/NEWS_CLOCK_UNCERTAIN do tuổi quote vượt 3 giây trong V216. Tách clock phiên/tin, hiệu chuẩn ba tick, TTL monotonic 15 phút, đối chiếu PC UTC; đổi offset/lệch giờ/hết hạn cần hiệu chuẩn lại.
- Clock observer schema2 ghi tuổi và TTL hiệu chuẩn; reader chấp nhận schema1 V216, không backfill nhãn hoặc đặc trưng.
- Chỉ MarketContext.mqh thay đổi logic sau chuẩn hóa namespace; giữ R10, guards quote3s, BIN/POD, model contracts và bridge quan sát.
- V217 source độc lập; hỗ trợ giữ tag/journal V216 đã thu, cần nâng cả hai CMD. Không cần chạy lại Tester/Train-History để sửa lỗi này.

# V2.16 — 19/10/2026

- Clock/phiên quan sát riêng, UTC ước lượng từ tick mới và giờ máy, IANA DST/giao thoa; dữ liệu cũ/Tester thiếu clock giữ UNKNOWN.
- Báo cáo phiên × regime × setup × kỳ hạn và bối cảnh tin; WIN/LOSS trade tách chất lượng hướng giá.
- Sửa báo cáo hiện tại cập nhật mỗi vòng đọc, không bị đóng băng theo model WAIT_NEW_DATA. Giữ báo cáo huấn luyện bất biến.
- Lịch EUR/USD High công khai, nền Python, TTL/vintage/HTTPS; thiếu hoặc cũ không trả lịch sạch. Chưa xác minh feed live trong môi trường phát triển.
- Vẫn MT4 + hai CMD; không đổi R10/guard/quyền lọc, không tự đặt lệnh. Giữ V208/cache V211/ML contracts.

# V2.15 — 19/10/2026

- Observer điều kiện candidate tại ANCHOR/LOCK; hợp đồng V215_CANDIDATE_DIRECTION_V1 (24/40 biến).
- Pipeline READY_AT_LOCK, priors/Logistic, temporal purge/calibration, trạng thái COLLECTING không fit khi thiếu mẫu.
- Registry snapshot/lượt nghiên cứu bất biến và lịch 7 ngày + 50 nhãn; không kích hoạt native.
- Sửa CSV replay share-read, commit sequence sau ghi thành công, fail-stop; Diagnose-Storage phân loại gap/clock.
- Giữ lõi R10, guard 3 giây, POD/logic và các hợp đồng nghiên cứu cũ. Chưa compile MetaEditor/kiểm thử runtime Windows.

# V2.14 — Windows execution diagnosis and forward observation

- Strict broker datetime/numeric observer parsing; schema3 numeric output.
- Read-only raw sealed Tester/stable live diagnosis, authoritative event and replay checks, input quality and report ZIP.
- Diagnostic dashboard separates incoming tick gap from no-recent-tick checks. New diagnostic presets and Vietnamese forward guide.
- All signal/entry/lock guards and ML contracts preserved; no broker orders or model promotion.

# V2.13

- Fix target sentinel semantics via ANCHOR_T1_UP_V2 (50 features, explicit reward_available); immutable causal migration from V211 caches.
- Default new history/deep T+1 fits use V2. Keep frozen V1 for compatibility/old-model diagnosis only; cache filename and payload remain V211 schema2.
- Train-only binary-aware scaling and numeric clipping for TCN/new T+1 logistic. Chronological inner-validation early stopping; fixed epoch outer refit.
- Export per-stage models for all algorithms, TCN initial/final/best checkpoints, learning curves and runtime fingerprint.
- Separate sparse Bayesian candidate-quality research with train-only setup/direction shrinkage and explicit sample/uncertainty gates.
- ENTRY boundary cancellation summaries. Read-only observer diagnostics and all native R10 guards preserved.
- training_review_v213.zip bundles reports for user review. All deep/candidate models remain offline and unimportable.
- Next source version: V2.14.

V222 chỉ thử lại ANCHOR sau đồng bộ trên tick live. Tester giữ lịch lấy mẫu lịch sử cũ để các golden native, dữ liệu huấn luyện đã niêm phong và so sánh legacy không đổi. Metadata/điều kiện mới được kiểm tra forward riêng, không suy thành lợi thế từ lịch sử.
