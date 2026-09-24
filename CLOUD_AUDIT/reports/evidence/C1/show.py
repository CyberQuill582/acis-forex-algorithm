"""Print a sim_out_<world>.json table."""
import json, sys
for w in sys.argv[1:]:
    d = json.load(open(f"sim_out_{w}.json"))
    cells = [c for c in d["agg"] if c != "stats"]
    protos = []
    for c in cells:
        for p in d["agg"][c]:
            if p not in protos:
                protos.append(p)
    print(w, "R=", d["R"], "wall", round(d["wall_s"]))
    print("proto".ljust(24), " ".join(c.ljust(9) for c in cells))
    for p in protos:
        print(p.ljust(24), " ".join((("%.3f" % d["agg"][c][p]["rate"]) if p in d["agg"][c] else "  -  ").ljust(9) for c in cells))
    if "stats" in d["agg"]:
        for k, v in d["agg"]["stats"].items():
            print("  ", k, "%.3f sd %.3f nan %d" % (v["mean"], v["sd"], v["n_nan"]))
