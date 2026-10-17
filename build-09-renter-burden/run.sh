#!/bin/bash
cd "$(dirname "$0")"
P=/home/patrickb/.venvs/aid/bin/python
$P -u run_analysis.py && $P -u model.py
