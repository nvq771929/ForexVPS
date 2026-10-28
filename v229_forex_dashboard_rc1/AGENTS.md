# V2.29 Forex dashboard

Current user request authorizes a Forex-specific readable dashboard with essential account, order, risk and operational information. Work in this tree; preserve delivered V2.28 source and ZIP. Supersede old recovery-only/version/work-directory restrictions below for this UI change. Keep every inherited header byte-identical; add the dashboard through the Expert adapter. No change to decisions, orders, risk, news, guards, models or Binary UI. Run both full no-skip suites before delivery. Preserve EA_MODE_V228 and journal contracts across the upgrade. Next source version 2.30.

# V2.28 recovery work

This is a recovery tree authorized by the current user handoff. Work here; preserve the original ZIP and /workspace/recovery/forexvps/v226_context_data_rc1 unchanged. This current recovery scope supersedes old work-directory/version directions below. Restore only the documented ChartFix1, observation-only clock diagnostics, and per-chart Binary/Forex role continuity; preserve native strategy, lock/freshness/ATR/news/risk behavior. No model training/activation or broker connections. Record differences and do not claim byte identity with the unavailable original V2.28. Run both full test suites without skips before packaging.

The following is the original project guidance, retained for history and applicable invariants:

# V2.24 full EA with optional pre-lock Binary dialogue

User authorized the optional two-way pre-lock adviser on 2026-10-23. This new
authorization permits scoped sidecar request/reply files and an optional
qualified WAIT veto before native publication. It does not authorize reversal,
bypassing native guards, post-lock updates or Forex model integration. Default
dialogue OFF; effects OFF. Missing, stale, invalid, changed or unqualified advice
leaves the native EA decision unchanged, including in Tester. Before-lock models
must use V224_PRELOCK_DIALOGUE_FEATURES_V1; old LOCK models are incompatible.
Preserve delivered V2.23 and the V2.24 supervisor RC1 artifacts. New full release
is RC2. Run full source tests and separate LearningSupervisor tests, no skips.

This is an independent source tree. Use this directory as project root. No older
ForexVPS checkout/source/runtime is needed. Keep all runtime state out of source.

After delivery, new source changes start at V2.25; preserve the delivered V2.24 package and the Final V2.22 baseline
archive and hashes. Before delivery, finish validation of V2.24 in place.
Version feature/journal contracts explicitly when they change. Learning model
IDs are separate from the software version. Do not describe a model refresh as
a software upgrade.

Scope: user-authorized V2.22 native Forex orders on Exness demo and real accounts, plus preserved Binary Option research and MT4_SIMULATED labels. Forex and Binary journals/models stay separate. Default account risk 0.5%; real orders require explicit ForexAllowRealTrading input. Preserve the inherited
market/strategy/T+1/quote/lock guards. Do not add broker orders, login, remote
desktop or credential handling unless the user separately requests that work.

Run `python -m unittest discover -s tests -v` with Python 3.11+, dependencies in
requirements-learning.txt and g++17. These include C++ source semantics tests;
they are not a MetaEditor compile or a Windows MT4 test. State that limitation.
Never infer market profitability from synthetic validation.

Canonical native source lives in mt4. MQL4 is an identical install mirror.
Run tools/package_release.py only with the passing log from the final source. Before packaging, verify namespace audit, source mirror and journal compatibility.
Keep model activation dependent on recorded, pre-outcome native forecasts.
V207 historical data has BACKTEST_MT4 origin and is never live forward evidence.
Only sealed Tester datasets can train; only qualified frozen weights may import
as OBSERVE into a matching LIVE_MT4 target. Preserve this distinction in later
upgrades. Read HISTORY_TRAINING_VI.md before changing the history workflow.

V209 progress must be stage-specific and throttled. Heartbeats are not proof
of file advancement. Never fake a whole-job ETA or bypass FNV/sequence checks.
Single-pass SHA256 must hash exactly the bytes used for learning. Keep V207
contracts compatible, and do not require a new Tester run for existing data.

V214 adds CLOSED_ANCHOR_UP_V1 price research, not execution WIN/LOSS. Preserve
R10 native guards and the legacy feature/model contract. Research classifiers
are OFFLINE_RESEARCH_ONLY and cannot import/activate in the native execution
filter. Compare algorithms only within the train dates, then separate temporal
calibration and untouched test, with embargo and availability checks.
Prepared history is a frozen derived local JSON/gzip snapshot, never pickle,
never live forward; preserve its original cutoff, integrity and source labels.
Do not promote diagnostic sampled windows as a complete sealed Tester dataset.

V214 adds ANCHOR_T1_UP_V1 as a separate research cohort. Keep old cache/data contracts readable, never fabricate T+1 fields for V210 caches. Research remains offline, with exploratory historical evaluation and fresh forward required. Preserve native Types/POD and guards.

V214 deep models are offline experiments: preserve the 32x29 closed-anchor sequence plus 50 corrected T+1 context contract, train-only normalization, chronological embargo, inner-only model selection and separate calibration/test. Never activate deep weights or change native guards. Run all tests with requirements-deep.txt installed; no skipped torch tests. Existing V211 prepared cache filename/kind remain compatible and deliberately unchanged.

V214: all public new T+1 learning uses ANCHOR_T1_UP_V2 (50 features); preserve legacy V1 for old frozen models/cache only. Do not silently overwrite V211 cache features. Select epochs solely within chronological train validation; outer refit uses a fixed epoch count and never calibration/test. Candidate quality is separate, sparse, offline price research. Preserve all R10 guards and three-second post-lock limit.

V214 diagnostics: preserve all native decision guards. Observer schema3 writes numeric analysis_start; readers accept legacy MQL datetime text with strict broker-clock parsing. Raw diagnostics support sealed BACKTEST_MT4 and stable LIVE_MT4 snapshots without training. Cross-check observer sequence, clocks and cancellation facts against authoritative BIN; never combine live and Tester. Retain V213-prefixed ML contracts unchanged because features and labels are unchanged.

V215: candidate research is separate from native filters. READY_AT_LOCK membership uses only immutable LOCK evidence. Keep rule observers and registry read-only relative to native source journals. Future cancellations/outcomes never become feature inputs. New candidate artifacts cannot use the legacy import path; missing samples return COLLECTING with no fitted model. Stable live-prefix research is retrospective, never native forward prediction.

V216: sessions/news are observation only, never write native state/config or alter guards. Broker coordinates are not UTC. Missing clock is UNKNOWN; never use TimeGMT in Tester to label history. Session/news context must be captured before outcomes; do not silently extend the V215 model feature contract. Current live diagnostics refresh independently of frozen model runs. News network calls run outside native tick and the candidate analysis loop, in a dedicated background worker, never turn stale/missing into clear.

V217: session clock calibration expires after 15 minutes monotonic; no dependency on price age. Preserve all native quote/trade guards. Clock observer schema2 includes calibration age/TTL; readers accept legacy schema1 without inventing calibration fields. Preserve bridge context_schedule_v216.csv and model contracts.

V218: manual publications have a separate immutable ledger and MT4 boundary outcomes. Never erase a committed publication because native ENTRY cancels. Preserve all R10 guards/native POD. Missing boundary prices are UNAVAILABLE. Publication is not proof of notification receipt or a manual Olymp fill; do not ingest new labels into native model training without a separate validated contract.

V222: anchor/cache synchronization changes collection availability, not strategy/POD/lock guards. Process boundaries before potentially blocking history work, retry only ANCHOR, preserve the actual quote timestamp and enforce the original 15-second start window. Slot observer schema1 never reconstructs old slots. News policy is V222_NEWS_TRACKING_V1 and bridge schema2 reads legacy schema1; Medium/High plus exact normalized priority events remain OBSERVE_ONLY. Retain provider impact, raw news bodies and immutable snapshots. Native manual ledger remains V218_MANUAL_PUBLICATION_V1 / manual_v218 files for journal compatibility. Never silently lower the live 3-pip ATR gate based on descriptive threshold counts. Verify full no-skip tests, old-journal recovery and mirror before release.

V222: Forex-only news is V222_FOREX_NEWS_V1 and may gate/close Forex orders.
The inherited Binary news/session observer remains read-only. Never use current
calendar vintages in a historical Tester. Preserve original R and birth time
across partial-close residual tickets; never repeat an uncertain reduction.

V222: user requested same-direction averaging at a better price, not hedging.
Implement one bounded addition with a persistent common basket budget/SL and
original hold deadline. Keep averaging OFF by default, provide explicit Tester
preset. Never silently allocate a fresh risk budget per child or widen stops.
Multi-leg basket news exits must close owned legs together; Binary stays isolated.

V224: Binary Option postmortem only. Preserve Forex V222 engine/risk/news/averaging byte-for-byte, all native Binary guards and 3-pip ATR. Loss associations and ex-post MFE/tick timing never become pre-entry features. No fitted filter is included or activated. Require independent evidence before changing strategies. Keep native/manual contracts compatible with V219 sealed datasets.

V224 RC3 scope override: on 2026-10-24 the user explicitly requested continued integration into V2.24 before first compile. Work only in this separate v224_ai_rc3 checkout; preserve delivered RC2 and active V2.23. Local-only AI explanations are observation-only and cannot write advisory replies, train/activate models, change orders, guards or Forex. User prefers local inference with no paid API.

V225 embedded RC1 scope override (2026-10-24): user explicitly authorized native context integration. Work only in v225_embedded_rc1; preserve delivered RC3. Port frozen RC1 as observation only, no native action/Forex effects or trained weights. Preserve all old include files byte-for-byte. Native main may add bounded observer initialization and post-native processing. Verify both real closed-bar corpora, full no-skip tests, mirrors, legacy journals and native ON/OFF parity. No native MetaEditor compiler is available.

V225 release boundary: after the embedded RC1 ZIP is delivered, preserve this
source/release and start subsequent source changes at V2.26. Legacy contracts
may retain V224 names; do not rename data/model contracts merely to match the
software version. New observer code has no training or action permission.

2026-10-25 compiler repair: this separate V226 work branch validates a one-line compatible backport for the user-reported V225 array initialization warnings. Preserve delivered V225 source/archive. Deliver a single-header maintenance patch for V225, no strategy/model/version changes, and run inherited full tests plus real-corpus parity. Do not present this maintenance patch as a V226 feature release.

V226 context/data RC1 user authorization (2026-10-25): user accepted the next step after pilot02: normalize initialization/restart state, archive actual observer inputs, and prepare deduplicated causal price-behavior learning data from existing history. Work only in v226_context_data_rc1. Preserve delivered V225 and maintenance patch. Frozen RC1 numeric engine stays unchanged (including array initializer fix); changes are observation-only persistence/lineage and a new separate research data contract. No model training/activation, native Binary decision/POD/guard changes, Forex changes, current-calendar backfill or broker actions. Separate source version2.26, next2.27; keep legacy namespaces/contracts readable. Run full no-skip root and supervisor tests, checkpoint/restart/corruption/identity tests, source mirror/legacy native preservation, and real source-data audits. No MetaEditor available.
