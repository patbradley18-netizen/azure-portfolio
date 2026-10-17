#!/bin/bash
cd "$(dirname "$0")"
P=/home/patrickb/.venvs/aid/bin/python
$P -u fetch_facilities.py | tail -12 && $P -u fetch_centroids.py | tail -3 && $P -u load_spatial.py && $P -u run_analysis.py
