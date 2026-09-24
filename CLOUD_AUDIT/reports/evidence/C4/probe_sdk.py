"""C4 receipt: demo-SDK facts from primary registries (PyPI JSON API, OSV.dev). Network, no data.

Prints version, licence, Python bound, last upload, wheel tags, and for ctrader-open-api's
exact-pinned dependencies the OSV advisories that apply to the pinned version.
"""
import json, urllib.request

def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

print("| package | version | licence | python | last upload | wheels |")
print("|---|---|---|---|---|---|")
for p in ["ctrader-open-api", "MetaTrader5", "nautilus_trader", "v20", "oandapyV20", "httpx",
          "skfolio", "arch", "vectorbt"]:
    i = get(f"https://pypi.org/pypi/{p}/json")
    info, rel = i["info"], i["releases"][i["info"]["version"]]
    lic = info.get("license_expression") or (info.get("license") or "").split("\n")[0][:30] or \
        ",".join(c.split("::")[-1].strip() for c in info["classifiers"] if "License" in c) or "(none on PyPI)"
    up = max(f["upload_time"] for f in rel)[:10]
    tags = sorted({f["filename"].rsplit("-", 1)[-1] for f in rel})[:4]
    print(f"| {p} | {info['version']} | {lic} | {info.get('requires_python')} | {up} | {' '.join(tags)} |")

print()
deps = get("https://pypi.org/pypi/ctrader-open-api/json")["info"]["requires_dist"]
print("ctrader-open-api requires_dist:", deps)
for d in deps:
    name, ver = d.split("==")
    v = get("https://api.osv.dev/v1/query", {"package": {"name": name, "ecosystem": "PyPI"}, "version": ver})
    cves = sorted({a for x in v.get("vulns", []) for a in x.get("aliases", []) if a.startswith("CVE")})
    print(f"- {name}=={ver}: {len(cves)} CVE(s) {cves}")
