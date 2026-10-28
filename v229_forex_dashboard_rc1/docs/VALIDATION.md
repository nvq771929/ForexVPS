# V2.22 validation

Run Python 3.11+, g++17, requirements-deep.txt:

```
python -m unittest discover -s tests -v
```

The release includes the completed no-skip log at validation/tests.txt. Coverage includes inherited historical/ML/deep/session/news/clock contracts, source mirror, native POD/FNV compatibility and V222 manual publications. Manual tests exercise post-LOCK cancellation with LOSS retained, CALL/PUT and all three horizons, missing entry/expiry, exact +2s/+3s boundary, pause/restart/dedup, disk failure, late commit withholding, corrupt/orphan/partial books and separate research ZIP output without source mutation. Notification delivery and Olymp fills are not inferred.

The native preservation audit compares V222 with the frozen V217 archive after namespace and explicitly enumerated observer/notification hooks. Existing includes change only in UI; new ManualSignals is a separate observer. Native guards, BIN structs, feature and activation contracts are unchanged. Golden native decisions and V217 journal resume are checked separately in validation-v222.json.

Native execution uses a C++17 MT4 API shim and Python decoders. This is not a MetaEditor compilation, Strategy Tester/Windows runtime validation, or evidence of market profitability. No EX4 or pretrained market weights are included. Live calendar network access remains unverified in cloud; fixtures test parser/cache/failure behavior.
