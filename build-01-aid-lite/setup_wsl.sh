#!/usr/bin/env bash
# setup_wsl.sh - one-time environment setup inside WSL Ubuntu.
# Creates a Python virtual environment on the Linux disk (fast) and installs the libraries.
set -e
VENV="$HOME/.venvs/aid"
rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet pandas scikit-learn sentence-transformers
"$VENV/bin/python" - <<'PY'
import torch, sklearn, pandas, sentence_transformers, sys
print("python", sys.version.split()[0])
print("torch", torch.__version__, "| sklearn", sklearn.__version__, "| pandas", pandas.__version__)
print("libs ok")
PY
