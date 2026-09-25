"""Lead check on PLAN_R1 §2.7 (execute FX at 17:05 New York): median EUR/USD and USD/JPY spread by
minute-of-rollover versus the day, on Dukascopy ticks, Jan-Feb 2019 (winter: 17:00 NY = 22:00 UTC).
Reads SPREADS only (ask - bid), never a price level or a return. Dukascopy's ECN book, not FTMO's."""
import lzma, struct, statistics, sys
from pathlib import Path
R = Path(sys.argv[1]); REC = struct.Struct(">IIIff")
for inst, scale in (("EUR_USD", 1e5), ("USD_JPY", 1e3)):
    buckets = {}
    for mm in ("00", "01"):
        for f in sorted((R / "data/dukascopy" / inst / "2019" / mm).glob("*_ticks.bi5")):
            raw = f.read_bytes()
            if not raw: continue
            data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
            for off in range(0, len(data), 20):
                ms, ask, bid, _, _ = REC.unpack_from(data, off)
                minute = ms // 60000                       # minute of the UTC day
                if 21*60+30 <= minute < 23*60:             # 16:30-18:00 New York (EST)
                    key = f"NY {16 + (minute - 21*60) // 60}:{(minute % 60):02d}"[:8]
                    key = "NY %02d:%02d" % (17 + (minute - 22*60) // 60, (minute % 60) // 5 * 5)
                else:
                    key = "rest of day" if 7*60 <= minute < 16*60 else None   # London+NY hours
                if key:
                    buckets.setdefault(key, []).append((ask - bid) / scale * (1e4 if scale == 1e5 else 1e2))
    print(inst, "median spread in pips (ticks in bucket):")
    for k in sorted(buckets):
        v = buckets[k]; print(f"   {k:12s} {statistics.median(v):6.2f}  ({len(v):,})")
