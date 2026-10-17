#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/home/patrickb/.venvs/aid/bin/python
$PY -m pip install -q azure-kusto-data azure-kusto-ingest 2>&1 | tail -1
$PY -u adx_setup.py "$1" "$2"
