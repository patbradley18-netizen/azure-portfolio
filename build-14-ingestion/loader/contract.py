"""contract.py - the data contract checks, shared by the validator Function and the loader container.
Pure functions over parsed JSON: no Azure in here, so the tests run anywhere."""
import re

SENTINEL_MIN = -1e8  # Census suppression codes are large negative numbers


def check(doc, contract, file_name):
    """Returns (ok: bool, reason: str, info: dict). The first failing rule is the reason."""
    m = re.match(contract["file_pattern"], file_name)
    if not m:
        return False, f"file name does not match {contract['file_pattern']}", {}
    year, dset = m.group("year"), m.group("set")
    if dset not in contract["dataset_id"]["allowed_sets"]:
        return False, f"unknown set '{dset}'", {}
    if not isinstance(doc, list) or len(doc) < 2 or not all(isinstance(r, list) for r in doc[:2]):
        return False, "not a JSON array of arrays with a header row", {}
    header, rows = doc[0], doc[1:]
    h = contract["header"]
    for col in h["required"]:
        if col not in header:
            return False, f"header missing required column {col}", {}
    variables = [c for c in header if re.match(h["variable_pattern"], c)]
    if not (h["min_variables"] <= len(variables) <= h["max_variables"]):
        return False, f"{len(variables)} variable columns; contract allows {h['min_variables']}-{h['max_variables']}", {}
    r = contract["rows"]
    if not (r["min"] <= len(rows) <= r["max"]):
        return False, f"{len(rows)} rows; contract allows {r['min']}-{r['max']}", {"rows": len(rows)}
    ix = {c: i for i, c in enumerate(header)}
    keys = set()
    v = contract["values"]
    for n, row in enumerate(rows, 1):
        if len(row) != len(header):
            return False, f"row {n} has {len(row)} cells, header has {len(header)}", {"rows": len(rows)}
        st, co = row[ix["state"]], row[ix["county"]]
        if not re.match(r["state_fips_pattern"], str(st)) or not re.match(r["county_fips_pattern"], str(co)):
            return False, f"row {n} has a bad FIPS ({st}, {co})", {"rows": len(rows)}
        if (st, co) in keys:
            return False, f"duplicate county {st}{co} at row {n}", {"rows": len(rows)}
        keys.add((st, co))
        for var in variables:
            cell = row[ix[var]]
            if cell in (None, ""):
                continue
            try:
                x = float(cell)
            except (TypeError, ValueError):
                return False, f"row {n} {var} is not numeric: {str(cell)[:30]}", {"rows": len(rows)}
            if x > v["max_value"]:
                return False, f"row {n} {var} = {x} exceeds max_value", {"rows": len(rows)}
            if x < 0 and not (v["allow_negative_sentinels"] and x <= SENTINEL_MIN):
                return False, f"row {n} {var} = {x} is negative and not a suppression sentinel", {"rows": len(rows)}
    suffix = contract["dataset_id"]["set_suffix"][dset]
    dataset_id = contract["dataset_id"]["template"].format(year=year, set_suffix=suffix)
    return True, "ok", {"rows": len(rows), "variables": len(variables), "dataset_id": dataset_id, "year": int(year), "set": dset}
