#!/bin/bash
cd "$(dirname "$0")"
P=/home/patrickb/.venvs/aid/bin/python
$P -u fetch_facilities.py && $P -u fetch_centroids.py
