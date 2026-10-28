# V217 cloud development setup

Use /workspace/ForexVPS/v217, existing checkout, no worktree required. Reuse /tmp/forexvps-v212-venv/bin/python with requirements-deep.txt and g++17. Requirements are unchanged from V216. Full suite: 160 passed, no skips. Native tests are source semantics through a C++ shim, not Windows/MetaEditor certification. No services or secrets needed for the cloud test workflow.

Session clock fix is observation-only, TTL15min, no native guard changes. Public calendar network access remains unverified in cloud; network configuration saved previously is still a draft requiring publication, not automatically applied. Windows screenshots are consistent with a usable cache; they do not validate cloud access. Do not bypass network policy or TLS.

Preserve V216 archive and new Final V217 archive. Future source starts V2.22. Runtime outputs outside source. Compatible V216 journal may continue under the same tag after stopping old processes, backing up, compiling V217 and restarting both V217 companions. Bridge/lease names remain V216 deliberately.
