#!/bin/bash
cd "$(dirname "$0")"
/home/patrickb/.venvs/aid/bin/python -u route_counties.py "$@"
