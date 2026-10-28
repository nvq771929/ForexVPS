# LearningSupervisor inside V2.24 Full RC3

`run_ai_assistant.py` is a third, isolated read-only process. It validates native
BIN/anchors, replays the frozen RC1 context engine, and writes its own grounded
report. Optional loopback Ollama selects verified fact/question IDs only. It
never writes advisory replies or changes native/Forex behavior. Read
`../LOCAL_AI_V224_VI.md`. No language-model weights are bundled.

This folder contains two separate model/data contracts:

1. `run_supervisor.py`: official-signal MT4 observer, inherited RC1 contracts.
2. `run_dialogue.py`: actual before-lock query snapshots, scoped peer replies,
   new pre-lock models and native-received prospective validation.

Read ../LEARNING_DIALOGUE_V224_VI.md for the new adviser and
HUONG_DAN_VI.md for the official-signal observer. The RC1 observer remains
read-only; only the explicitly scoped dialogue worker writes reply files.
A LOCK model cannot enter the pre-lock adviser. No market-trained weights or
qualification receipts are supplied. Forex does not use either Binary model.

The display indicator reports official-signal learning progress. Adviser
permissions/status are reported by the EA and dialogue_status.json.
Tests: python -m unittest discover -s tests -v with pinned CPU dependencies.
