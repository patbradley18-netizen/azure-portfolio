"""Build #22: the showcase feed.
Walks every build-*/ folder, turns each committed tabular JSON under data/ into one small, uniform JSON table
(columns + rows), and writes an index. Static files on the existing site; nothing else to run or pay for.
Shape is versioned (schema azportfolio-showcase/1) so a reader (Kiln Studio, the website) can rely on it.
Refuses to write anything that looks like an email address or a GUID: the feed is public by design.
Usage: python3 build_feed.py <repo root> <out dir>   (CI calls it with dist/showcase)"""
import json, os, re, sys, subprocess, datetime

ROOT = os.path.abspath(sys.argv[1]); OUT = os.path.abspath(sys.argv[2])
SITE = "https://stazportfoliob1.z14.web.core.windows.net/"
REPO = "https://github.com/patbradley18-netizen/azure-portfolio/tree/main/"
SCHEMA = "azportfolio-showcase/1"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
SCALAR = (str, int, float, bool, type(None))

def tracked(path):
    r = subprocess.run(["git", "ls-files", "--", path], cwd=ROOT, capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.endswith(".json")]

def load(p):
    try:
        return json.load(open(os.path.join(ROOT, p), encoding="utf-8-sig"))
    except Exception:
        return None

def readme_meta(bdir):
    p = os.path.join(ROOT, bdir, "README.md"); title = anchor = ""
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if not title and line.startswith("# "):
                title = re.sub(r"^#\s*Build #\d+[:\s—-]*", "", line.strip()).strip()
            m = re.search(r"[Aa]nchor phrases?:?\**\s*\*?([^*\n]{5,160})", line)
            if m and not anchor:
                anchor = m.group(1).strip().rstrip(".").strip()
            if title and anchor: break
    return title, anchor

def as_table(obj, key_hint):
    """Return (columns, rows) for the shapes the builds actually wrote, or None."""
    if isinstance(obj, dict) and isinstance(obj.get("columns"), list) and isinstance(obj.get("rows"), list):
        cols = obj["columns"]; rows = obj["rows"]
        if rows and isinstance(rows[0], dict): rows = [[r.get(c) for c in cols] for r in rows]
        return cols, rows
    if isinstance(obj, dict) and isinstance(obj.get("Columns"), list) and isinstance(obj.get("Rows"), list):   # Kusto / ARM query
        return [c.get("ColumnName") or c.get("name") for c in obj["Columns"]], obj["Rows"]
    if isinstance(obj, list) and obj and all(isinstance(r, dict) for r in obj):
        cols = [k for k in obj[0] if isinstance(obj[0][k], SCALAR)]
        if not cols: return None
        return cols, [[r.get(c) for c in cols] for r in obj]
    return None

def drop_guid_columns(cols, rows):
    """A run id or a resource id is a GUID; the rule is GUIDs never leave the repo. Drop the column, keep the table."""
    keep = [i for i, c in enumerate(cols) if not any(isinstance(r[i], str) and GUID.search(r[i]) for r in rows[:50])]
    dropped = [c for i, c in enumerate(cols) if i not in keep]
    return [cols[i] for i in keep], [[r[i] for i in keep] for r in rows], dropped

def scrub_check(text, where):
    if EMAIL.search(text) or GUID.search(text):
        sys.exit(f"REFUSED: {where} contains an email address or a GUID; the feed is public")

def write(rel, obj):
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    scrub_check(text, rel)
    open(p, "w", encoding="utf-8").write(text); return len(text.encode("utf-8"))

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
builds = []
for bdir in sorted(d for d in os.listdir(ROOT) if re.match(r"build-\d\d-", d)):
    num = int(bdir[6:8]); title, anchor = readme_meta(bdir)
    series = []
    for f in tracked(f"{bdir}/data"):
        obj = load(f)
        if obj is None: continue
        stem = os.path.splitext(os.path.basename(f))[0]
        candidates = []
        t = as_table(obj, stem)
        if t: candidates.append((stem, "", t))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                t = as_table(v, k)
                if t: candidates.append((k, v.get("question", "") if isinstance(v, dict) else "", t))
        for sid, question, (cols, rows) in candidates:
            if not rows: continue
            if any(x["id"] == sid for x in series): sid = f"{stem}_{sid}"   # same key in two files (e.g. whatif before/after)
            cols, rows, dropped = drop_guid_columns(cols, rows)
            if not cols: continue
            if any(isinstance(v, str) and len(v) > 300 for r in rows[:50] for v in r): continue   # documents are not figures
            rel = f"{bdir}/{sid}.json"
            b = write(rel, {"schema": SCHEMA, "build": num, "id": sid, "title": question or sid, "columns": cols, "rows": rows,
                            "n": len(rows), "source": f"{bdir}/{f.split('/', 1)[1]}", "dropped_columns": dropped, "generated_at": now, "commit": sha})
            series.append({"id": sid, "title": question or sid, "columns": cols, "n": len(rows), "bytes": b, "url": SITE + "showcase/" + rel})
    page = SITE + bdir + "/" if os.path.exists(os.path.join(ROOT, bdir, "findings.html")) or os.path.exists(os.path.join(ROOT, bdir, "dashboard.html")) else None
    entry = {"build": num, "dir": bdir, "title": title, "anchor": anchor, "page": page, "readme": REPO + bdir + "/README.md",
             "image": next((page + img for img in ("findings.png", "dashboard.png") if page and os.path.exists(os.path.join(ROOT, bdir, img))), None),
             "series": series, "manifest": SITE + "showcase/" + bdir + ".json"}
    write(f"{bdir}.json", {"schema": SCHEMA, "generated_at": now, "commit": sha, **entry})
    builds.append({k: v for k, v in entry.items() if k != "series"} | {"series_count": len(series)})
write("index.json", {"schema": SCHEMA, "generated_at": now, "commit": sha, "site": SITE, "licence": "public data; non-commercial learning project",
                     "how_to_read": "index -> <dir>.json manifest -> one JSON table per series: columns[] + rows[][]", "builds": builds})
print(f"{len(builds)} builds, {sum(b['series_count'] for b in builds)} series -> {OUT}")
