# V222 build environment

Canonical checkout: /workspace/ForexVPS/v222. Python environment:
/workspace/.venv-v219/bin/python, with requirements-learning/deep and g++17.
Run the complete no-skip unittest suite from the source root. MQL source is
executed through a test-only C++ API shim; MetaEditor and MT4 Windows are not
available here. No broker connection or live news fetch was performed for this
release. News tests use explicit fixtures. Runtime/source archives stay separate.

V219 and V220 were preserved. New work after this release starts at V222.
See docs/v222-binary-preservation.json and validation/tests.txt in the ZIP.
