#!/usr/bin/env bash
# install_sql_driver.sh - adds the Azure SQL driver and the Entra sign-in library to the venv.
set -e
"$HOME/.venvs/aid/bin/pip" install --quiet mssql-python azure-identity
"$HOME/.venvs/aid/bin/python" - <<'PY'
import mssql_python, azure.identity
print("drivers ok", mssql_python.__version__)
PY