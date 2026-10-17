"""make_zip.py - build a deployment zip with forward-slash paths and 0644 file modes.
Windows Compress-Archive writes backslash entries (a file literally named 'contracts\\x.yaml' on Linux); a zip built on a
0700-mode mount keeps those bits and the Function host then cannot read host.json. This does neither.
Usage: python make_zip.py <out.zip> <file-or-dir>..."""
import os, sys, zipfile
out, items = sys.argv[1], sys.argv[2:]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for it in items:
        paths = [it] if os.path.isfile(it) else [os.path.join(d, f) for d, _, fs in os.walk(it) for f in fs]
        for p in paths:
            zi = zipfile.ZipInfo(p.replace(os.sep, "/"))
            zi.external_attr = (0o644 << 16)
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(p, "rb") as fh:
                z.writestr(zi, fh.read())
    print(z.namelist())
