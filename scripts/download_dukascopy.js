// ACIS OOS data acquisition — Dukascopy TICK download (§14 guard-2, master §13, ACIS-09 §5).
//
// Full bid/ask tick history for the ratified 8-instrument universe, 2012–2025.
// Designed to run unattended for weeks and survive anything short of disk loss:
//
//   ORDER      Reverse-chronological, all 8 instruments per day (2025-12-31 back to
//              2012-01-01). Wherever the run stands, the data on disk is one CONTIGUOUS
//              recent window covering EVERY instrument — never 14 yrs of one pair and
//              nothing of the rest.
//   CHUNK      One UTC day per instrument (24 hourly .bi5 files). A day is the largest
//              unit proven to clear Dukascopy's per-IP volume window on a residential
//              link; a week reliably 429s.
//   RATE       Adaptive: the inter-request pause shrinks after success streaks and
//              grows on 429, followed by an escalating cooldown. Converges on whatever
//              the current connection sustains (the ceiling moves; datacenter IPs are
//              hard-banned — run this from a residential connection only).
//   NETWORK    A network error is NEVER counted as a failure. The chunk waits until DNS
//              resolves again, then retries — indefinitely.
//   ATOMIC     Written to <file>.tmp then renamed, so a crash mid-write can never leave
//              a truncated file that resume would mistake for a finished chunk.
//   RESUME     Any existing non-empty .csv.gz is skipped. The supervisor
//              (scripts/dl_supervisor.ps1) restarts this process whenever it exits.
//   DISK       Pauses (does not exit) if free space drops below DISK_MIN_GB.
//   HONESTY    An empty WEEKDAY is suspicious (Dukascopy can answer a throttled request
//              with nothing). It is retried, and if still empty it is written but listed
//              in empty_days.log for inspection — never silently accepted.
//              `failAfterRetryCount` stays at its default (true): a partially-fetched
//              day throws instead of being written with hours missing.
//
// Output:  data/dukascopy/<INSTRUMENT>/<YYYY>/<sym>-<YYYY-MM-DD>.csv.gz
//          columns: timestamp,askPrice,bidPrice,askVolume,bidVolume   (ms epoch UTC)
// Status:  data/dukascopy/status.json   (progress, rate, ETA — rewritten every chunk)
// Log:     data/dukascopy/download.log
//
// Exit codes: 0 = complete (writes data/dukascopy/COMPLETE)   3 = another instance holds
// the lock   2 = fatal (the supervisor restarts it).

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const dns = require('dns').promises;
const { getHistoricalRates } = require('dukascopy-node');

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
const END_YEAR = 2025;                       // inclusive → 14 years

const ROOT = path.join(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'data', 'dukascopy');
const LOG_FILE = path.join(OUT_DIR, 'download.log');
const STATUS_FILE = path.join(OUT_DIR, 'status.json');
const EMPTY_LOG = path.join(OUT_DIR, 'empty_days.log');
const STATE_FILE = path.join(OUT_DIR, 'state.json');
const LOCK_FILE = path.join(OUT_DIR, 'download.lock');
const COMPLETE_FILE = path.join(OUT_DIR, 'COMPLETE');

// --- adaptive rate controller -------------------------------------------------
const START_PAUSE_MS = 1500;       // proven: a day at 1.5 s/request completed clean
const MIN_PAUSE_MS = 600;
const MAX_PAUSE_MS = 20000;
const SPEEDUP = 0.9;
const BACKOFF = 2;
const STREAK_TO_SPEEDUP = 8;       // days in a row before we try going faster
const COOLDOWN_BASE_MS = 5 * 60e3; // first 429 cooldown
const COOLDOWN_MAX_MS = 60 * 60e3; // cap: one hour
const NET_PROBE_MS = 30e3;         // how often to re-check a dead connection
const HARD_ERR_ATTEMPTS = 5;       // non-network, non-429 errors per chunk per run
const EMPTY_RETRIES = 2;           // extra fetches for a suspicious empty weekday
const PERM_FAIL_RUNS = 3;          // a chunk hard-failing in this many runs is skipped
const DISK_MIN_GB = 3;

let pauseMs = START_PAUSE_MS;
let streak = 0;
let consecutive429 = 0;

fs.mkdirSync(OUT_DIR, { recursive: true });

function log(msg) {
  const line = `${new Date().toISOString()}  ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + '\n');
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- single-instance lock (PID-checked, stale locks reclaimed) ------------------
function acquireLock() {
  if (fs.existsSync(LOCK_FILE)) {
    const pid = parseInt(fs.readFileSync(LOCK_FILE, 'utf8'), 10);
    let alive = false;
    try { if (pid) { process.kill(pid, 0); alive = true; } } catch (_) { alive = false; }
    if (alive && pid !== process.pid) return false;
  }
  fs.writeFileSync(LOCK_FILE, String(process.pid));
  const release = () => { try {
    if (fs.readFileSync(LOCK_FILE, 'utf8') === String(process.pid)) fs.unlinkSync(LOCK_FILE);
  } catch (_) {} };
  process.on('exit', release);
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGBREAK', 'SIGHUP']) {
    process.on(sig, () => { release(); process.exit(130); });
  }
  return true;
}

// --- persistent state: permanent-failure counts across runs ---------------------
function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch (_) { return { hardFails: {} }; }
}
function saveState(s) {
  fs.writeFileSync(STATE_FILE + '.tmp', JSON.stringify(s, null, 1));
  fs.renameSync(STATE_FILE + '.tmp', STATE_FILE);
}

// --- plan: every (day, instrument), newest first --------------------------------
function buildPlan() {
  const plan = [];
  const first = Date.UTC(START_YEAR, 0, 1);
  for (let t = Date.UTC(END_YEAR, 11, 31); t >= first; t -= 86400e3) {
    const d = new Date(t);
    const dow = d.getUTCDay();
    if (dow === 6) continue;                            // Saturday: market closed
    const day = d.toISOString().slice(0, 10);
    const year = day.slice(0, 4);
    for (const [sym, dir] of Object.entries(INSTRUMENTS)) {
      plan.push({
        sym, dir, day, dow,
        file: path.join(OUT_DIR, dir, year, `${sym}-${day}.csv.gz`),
        from: d,
        to: new Date(t + 86400e3),
      });
    }
  }
  return plan;
}

function isDone(c) {
  try { return fs.statSync(c.file).size > 0; } catch (_) { return false; }
}

// A weekday with zero ticks is suspicious — except the days FX is genuinely shut.
function emptyIsExpected(c) {
  if (c.dow === 0) return true;                         // Sunday: only ~2h (22:00+)
  const md = c.day.slice(5);
  return md === '12-25' || md === '01-01';
}

// --- error classification --------------------------------------------------------
const NET_RE = /fetch failed|ENOTFOUND|EAI_AGAIN|ECONNRESET|ECONNREFUSED|ETIMEDOUT|ENETUNREACH|EHOSTUNREACH|socket|network|aborted|timeout|other side closed|UND_ERR/i;
function classify(e) {
  const m = `${e && e.message} ${e && e.cause && (e.cause.code || e.cause.message)}`;
  if (/\b429\b/.test(m)) return 'rate';
  if (/\b5\d\d\b/.test(m)) return 'server';
  if (NET_RE.test(m)) return 'network';
  return 'hard';
}

async function online() {
  try { await dns.resolve4('datafeed.dukascopy.com'); return true; } catch (_) { return false; }
}

async function waitForNetwork() {
  if (await online()) return;
  log('NETWORK DOWN — waiting for connectivity (checking every 30 s)…');
  const t0 = Date.now();
  while (!(await online())) await sleep(NET_PROBE_MS);
  log(`NETWORK BACK after ${Math.round((Date.now() - t0) / 60e3)} min — resuming`);
}

function freeGB() {
  try { const s = fs.statfsSync(OUT_DIR); return (s.bavail * s.bsize) / 1e9; } catch (_) { return Infinity; }
}

async function waitForDisk() {
  if (freeGB() >= DISK_MIN_GB) return;
  log(`DISK LOW (${freeGB().toFixed(1)} GB free < ${DISK_MIN_GB}) — paused; free space to continue`);
  while (freeGB() < DISK_MIN_GB) await sleep(10 * 60e3);
  log('DISK OK — resuming');
}

// --- progress / ETA ---------------------------------------------------------------
const recent = [];                                      // completion timestamps (rolling)
function writeStatus(s) {
  const now = Date.now();
  recent.push(now);
  while (recent.length > 200) recent.shift();
  const spanH = recent.length > 1 ? (now - recent[0]) / 3600e3 : 0;
  const perHour = spanH > 0 ? (recent.length - 1) / spanH : 0;
  const left = s.total - s.done - s.skipped;
  const out = {
    updated: new Date(now).toISOString(),
    done: s.done, total: s.total, skipped_permanent: s.skipped,
    percent: +((100 * s.done) / s.total).toFixed(2),
    downloaded_this_run_gb: +(s.bytes / 1e9).toFixed(3),
    chunks_per_hour: +perHour.toFixed(1),
    eta_days: perHour > 0 ? +(left / perHour / 24).toFixed(1) : null,
    pause_ms: pauseMs,
    reached_back_to: s.current,
    free_disk_gb: +freeGB().toFixed(1),
    pid: process.pid,
  };
  fs.writeFileSync(STATUS_FILE + '.tmp', JSON.stringify(out, null, 1));
  fs.renameSync(STATUS_FILE + '.tmp', STATUS_FILE);
}

async function fetchDay(c) {
  return getHistoricalRates({
    instrument: c.sym,
    dates: { from: c.from, to: c.to },
    timeframe: 'tick',
    format: 'csv',
    batchSize: 1,
    pauseBetweenBatchesMs: pauseMs,
    retryCount: 2,                                      // absorb a single dropped hour
    pauseBetweenRetriesMs: 5000,
  });
}

function writeAtomic(file, buf) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file + '.tmp', buf);
  fs.renameSync(file + '.tmp', file);
}

// Returns true on success, false on a hard failure for this run.
async function downloadChunk(c, s, state) {
  let hard = 0, empties = 0, netFails = 0;
  for (;;) {
    await waitForDisk();
    try {
      const csv = await fetchDay(c);
      const body = csv || '';
      const rows = Math.max(0, body.split('\n').filter(Boolean).length - 1);   // minus header
      if (rows <= 0 && !emptyIsExpected(c) && empties < EMPTY_RETRIES) {
        empties++;
        log(`EMPTY? ${c.dir} ${c.day} (weekday, 0 ticks) — refetch ${empties}/${EMPTY_RETRIES}`);
        await sleep(30e3);
        continue;
      }
      if (rows <= 0 && !emptyIsExpected(c)) {
        fs.appendFileSync(EMPTY_LOG, `${c.dir} ${c.day}\n`);
      }
      const gz = zlib.gzipSync(body);
      writeAtomic(c.file, gz);
      s.bytes += gz.length;
      consecutive429 = 0;
      if (++streak >= STREAK_TO_SPEEDUP) {
        pauseMs = Math.max(MIN_PAUSE_MS, Math.round(pauseMs * SPEEDUP));
        streak = 0;
      }
      if (state.hardFails[c.file]) { delete state.hardFails[c.file]; saveState(state); }
      return true;
    } catch (e) {
      const kind = classify(e);
      streak = 0;
      if (kind === 'network') {
        // DNS can resolve while the link is still unusable (captive portal, flaky
        // Wi-Fi), so back off on repeats instead of spinning: 5s, 10s, … capped 10 min.
        const wait = Math.min(10 * 60e3, 5000 * 2 ** netFails++);
        log(`NET   ${c.dir} ${c.day}  ${e.message} — retry in ${Math.round(wait / 1000)}s`);
        await sleep(wait);
        await waitForNetwork();
      } else if (kind === 'rate') {
        consecutive429++;
        pauseMs = Math.min(MAX_PAUSE_MS, Math.round(pauseMs * BACKOFF));
        const cool = Math.min(COOLDOWN_MAX_MS, COOLDOWN_BASE_MS * 2 ** (consecutive429 - 1));
        log(`429   ${c.dir} ${c.day}  cooldown ${Math.round(cool / 60e3)} min, pause→${pauseMs}ms`);
        await sleep(cool);
      } else if (kind === 'server') {
        log(`5xx   ${c.dir} ${c.day}  ${e.message} — retry in 2 min`);
        await sleep(120e3);
      } else {
        hard++;
        log(`ERR   ${c.dir} ${c.day}  ${hard}/${HARD_ERR_ATTEMPTS}  ${e.message}`);
        if (hard >= HARD_ERR_ATTEMPTS) {
          state.hardFails[c.file] = (state.hardFails[c.file] || 0) + 1;
          saveState(state);
          log(`FAIL  ${c.dir} ${c.day}  (run ${state.hardFails[c.file]}/${PERM_FAIL_RUNS})`);
          return false;
        }
        await sleep(15e3);
      }
    }
  }
}

async function main() {
  if (fs.existsSync(COMPLETE_FILE)) { log('COMPLETE marker present — nothing to do'); return 0; }
  if (!acquireLock()) { console.log('another downloader holds the lock'); return 3; }

  const state = loadState();
  const plan = buildPlan();
  const s = { total: plan.length, done: 0, skipped: 0, bytes: 0, current: null };
  const todo = [];
  for (const c of plan) {
    if (isDone(c)) s.done++;
    else if ((state.hardFails[c.file] || 0) >= PERM_FAIL_RUNS) s.skipped++;
    else todo.push(c);
  }
  log(`START pid=${process.pid} chunks=${s.total} done=${s.done} permanent-skips=${s.skipped} ` +
      `remaining=${todo.length} free=${freeGB().toFixed(1)}GB pause=${pauseMs}ms`);

  await waitForNetwork();
  let n = 0;
  for (const c of todo) {
    if (isDone(c)) { s.done++; continue; }             // landed by an earlier run meanwhile
    s.current = c.day;
    const ok = await downloadChunk(c, s, state);
    if (ok) s.done++;
    writeStatus(s);
    if (ok && ++n % 40 === 0) {
      log(`OK    reached ${c.day}  [${s.done}/${s.total} = ${((100 * s.done) / s.total).toFixed(2)}%]  ` +
          `pause=${pauseMs}ms  run=${(s.bytes / 1e9).toFixed(2)}GB  free=${freeGB().toFixed(1)}GB`);
    }
    await sleep(pauseMs);
  }

  const remaining = plan.filter((c) => !isDone(c)).length;
  const perm = plan.filter((c) => !isDone(c) && (state.hardFails[c.file] || 0) >= PERM_FAIL_RUNS);
  if (remaining === perm.length) {
    fs.writeFileSync(COMPLETE_FILE, `${new Date().toISOString()} done=${s.total - perm.length} ` +
      `permanent_failures=${perm.length}\n` + perm.map((c) => `${c.dir} ${c.day}`).join('\n') + '\n');
    log(`FINISHED — all chunks done (${perm.length} permanent failures listed in COMPLETE)`);
    return 0;
  }
  log(`PASS ENDED with ${remaining - perm.length} chunks still missing — supervisor will rerun`);
  return 1;
}

main().then((code) => { process.exitCode = code; }).catch((e) => {
  log(`FATAL ${e && (e.stack || e.message)}`);
  process.exitCode = 2;
});
