#!/bin/bash
cd "$(dirname "$0")"
P=/home/patrickb/.venvs/aid/bin/python
$P -u fetch_acs.py 2023 rentburden && $P -u load_acs.py 2023 rentburden
