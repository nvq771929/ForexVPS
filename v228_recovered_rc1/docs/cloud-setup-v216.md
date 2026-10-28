# Development environment V216

Current instance: Python 3.12, pinned learning/CPU torch 2.9.0+cpu and tzdata 2026.4 installed; pip check and CLI startup passed. Full source suite: 158 passed, no skips. Native shim tests do not establish Windows/MetaEditor compatibility.

Reusable install_script and start_skill were saved in the environment configuration draft for V216. Network draft allows the one public calendar host nfs.faireconomy.media plus the existing package-manager preset. Saving does not publish or apply the runtime policy. Calendar access remains unverified in this instance due to network policy; use environment settings to review/publish the draft if live cloud feed checks are needed. The Windows product can be checked separately with Check-News.cmd. No secrets required, no proxy bypass or TLS relaxation.

Use the existing checkout /workspace/ForexVPS/v216; no worktree required. Reuse /tmp/forexvps-v212-venv/bin/python; recreate using requirements-deep.txt when absent. No services need restarting for the cloud test workflow. User live runtime needs MT4 and the two companion CMD processes restarted after reboot. Preserve frozen releases; next source V2.17.
