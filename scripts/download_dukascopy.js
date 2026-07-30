// ACIS OOS data acquisition — Dukascopy tick download (§14 guard-2, ACIS-09 §5).
//
// Downloads institutional bid/ask tick data for the ratified 8-instrument universe
// over the 14-yr walk-forward window, in MONTHLY chunks (a full year of ticks would
// OOM a small VM; a month is ~150MB raw / ~30MB gzipped and safe on 2GB RAM).
//
// Output layout (one gzipped dukascopy-node tick CSV per instrument-month):
//     data/dukascopy/<INSTRUMENT>/<sym>-<YYYY>-<MM>.csv.gz
//     columns: timestamp,askPrice,bidPrice,askVolume,bidVolume  (ms epoch UTC)
// This is the exact format the deferred Dukascopy `TickSource` adapter will read
// (tests/backtest/data_loader.py) — provenance = "dukascopy", primary source.
//
// SURVIVAL (unmonitored multi-day run):
//   * retryCount:8 — dukascopy-node defaults to 0, so a single transient failure
//     silently loses a chunk. This is the single most important setting.
//   * batchSize:5 + pauseBetweenBatchesMs:3000 — the docs' large-download advice:
//     minimise concurrency, maximise the pause, to survive rate limits.
//   * RESUMABLE — a completed non-empty chunk is skipped, so re-running after any
//     crash/disconnect retries only what is missing. A failed month is logged and
//     skipped, never fatal to the run.
//
// Run under tmux so it survives SSH disconnect:  tmux new -s dl; node download_dukascopy.js
// Retry any failures afterwards by simply re-running the same command.

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { getHistoricalRates } = require('dukascopy-node');

// dukascopy-node symbol -> ACIS instrument directory (the ratified 8-set).
const INSTRUMENTS = {
  eurusd: 'EUR_USD',
  usdjpy: 'USD_JPY',
  gbpusd: 'GBP_USD',
  audusd: 'AUD_USD',
  usdchf: 'USD_CHF',
  usdcad: 'USD_CAD',
  eurgbp: 'EUR_GBP',
  xauusd: 'XAU_USD',
};

const START_YEAR = 2012;
const END_YEAR = 2025;                       // inclusive; 2012-01 .. 2025-12 = 14 yrs
const OUT_DIR = './data/dukascopy';
const LOG_FILE = './download.log';

function log(msg) {
  const line = `${new Date().toISOString()}  ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + '\n');
}

async function main() {
  let done = 0;
  let failed = 0;
  const failures = [];

  for (const [sym, dir] of Object.entries(INSTRUMENTS)) {
    const outDir = path.join(OUT_DIR, dir);
    fs.mkdirSync(outDir, { recursive: true });

    for (let y = START_YEAR; y <= END_YEAR; y++) {
      for (let m = 1; m <= 12; m++) {
        const mm = String(m).padStart(2, '0');
        const file = path.join(outDir, `${sym}-${y}-${mm}.csv.gz`);

        // Resume: skip a chunk already downloaded (non-empty).
        if (fs.existsSync(file) && fs.statSync(file).size > 0) {
          done++;
          continue;
        }

        const from = new Date(Date.UTC(y, m - 1, 1));
        const to = new Date(Date.UTC(m === 12 ? y + 1 : y, m === 12 ? 0 : m, 1));

        try {
          const csv = await getHistoricalRates({
            instrument: sym,
            dates: { from, to },
            timeframe: 'tick',
            format: 'csv',
            // --- rate-limit survival (see header) ---
            batchSize: 5,
            pauseBetweenBatchesMs: 3000,
            retryCount: 8,
            pauseBetweenRetriesMs: 3000,
          });

          if (!csv || csv.length === 0) {
            // Empty is legitimate for some weeks (holidays); record and move on.
            fs.writeFileSync(file, zlib.gzipSync(''));
            done++;
            log(`EMPTY ${dir} ${y}-${mm}  (no ticks — likely holiday/closed)`);
            continue;
          }

          fs.writeFileSync(file, zlib.gzipSync(csv));       // ~5x smaller on disk
          done++;
          log(`OK    ${dir} ${y}-${mm}  ${(csv.length / 1e6).toFixed(1)}MB raw  [${done} done]`);
        } catch (e) {
          failed++;
          failures.push(`${dir} ${y}-${mm}`);
          log(`FAIL  ${dir} ${y}-${mm}  ${e.message}`);
        }
      }
    }
  }

  log(`FINISHED. ok=${done} failed=${failed}`);
  if (failed > 0) {
    log(`FAILURES: ${failures.join(', ')}`);
    log('Re-run this script to retry ONLY the failed/missing chunks (resume is automatic).');
    process.exitCode = 1;
  }
}

main().catch((e) => {
  log(`FATAL ${e.stack || e.message}`);
  process.exitCode = 2;
});
