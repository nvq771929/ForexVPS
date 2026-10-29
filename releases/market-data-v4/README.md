# Independent research recorder — source kit

This is a demo-only read-only observer and data validator, not a trading EA upgrade. The package includes a standalone MQ4 recorder, preset, local Windows ZIP helper and empty actual-platform BO templates. No native EA dependencies or personal capture files are included.

Read the Vietnamese README. Compile the MQ4 file with MetaEditor on the user's MT4 installation, attach it to a separate third EURUSD M5 demo chart, and retain the existing operating charts. The recorder makes no trade calls and requires no AutoTrading change.

See `VALIDATION.json`: tests compile the actual recorder body with a C++ MT4 API shim and validate its synthetic CSV output with Python. These tests are not a native MetaEditor compile or a Windows PowerShell runtime test. Callback consistency is not proof of a complete broker tick feed; timer heartbeats are never quotes. Existing closed-ticket commission is exported only when present, without opening trades.
