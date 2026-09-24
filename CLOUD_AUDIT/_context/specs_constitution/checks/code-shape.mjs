#!/usr/bin/env node
/**
 * Code-shape check (A12) — the I/O shell: walks the tree, builds the spec corpus, diffs
 * against git, prints. The rules themselves are in shape-rules.mjs.
 *
 * Mental model: both budgets were written, adopted, then broken again the same week, because
 * review polices them at the moment obeying costs most. So they move into the gate, checked
 * by shape and never by ratio (a ratio would fire on the headers A12 itself requires).
 *
 *   node code-shape.mjs [--config <f>] [--root <d>] [--rule SIZE,QUOTE] [--baseline <f>]
 *                       [--write-baseline <f>] [--since <git-ref>] [--no-quote] [--quiet]
 */
import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from 'node:fs';
import { join, resolve, extname, relative } from 'node:path';
import { spawnSync } from 'node:child_process';

import {
  DEFAULTS, CLEARANCE, inspectFile, shingleSet, diffBaseline, touchedViolations,
} from './shape-rules.mjs';
export {
  commentBlocks, shingleSet, quotedShingle, clearanceReason, inspectFile, diffBaseline, touchedViolations,
} from './shape-rules.mjs';

function walk(dir, cfg, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    if (cfg.exclude.includes(name)) continue;
    const path = join(dir, name);
    const st = statSync(path);
    if (st.isDirectory()) walk(path, cfg, out);
    else if (cfg.extensions.includes(extname(name))) out.push(path);
  }
  return out;
}

/**
 * Files changed against a git ref, repo-relative. Returns null when the ref cannot be
 * resolved, which is the case that must never read as "nothing changed": a shallow clone
 * or a bad ref would otherwise print a green burn-down over a set it never computed.
 */
function changedSince(root, ref) {
  const verified = spawnSync('git', ['rev-parse', '--verify', '--quiet', `${ref}^{commit}`], { cwd: root, encoding: 'utf8' });
  if (verified.status !== 0) return null;
  const r = spawnSync('git', ['diff', '--name-only', ref, '--'], { cwd: root, encoding: 'utf8' });
  if (r.status !== 0) return null;
  return r.stdout.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
}

function main(argv) {
  const arg = (flag, dflt) => {
    const i = argv.indexOf(flag);
    return i >= 0 ? argv[i + 1] : dflt;
  };
  const root = resolve(arg('--root', '.'));
  const configPath = resolve(arg('--config', join(root, 'code-shape.config.json')));
  const cfg = { ...DEFAULTS, ...(existsSync(configPath) ? JSON.parse(readFileSync(configPath, 'utf8')) : {}) };
  const only = (arg('--rule') ?? '').split(',').filter(Boolean);

  const specShingles = new Set();
  for (const s of cfg.specs) {
    const p = join(root, s);
    if (!existsSync(p)) continue;
    const files = statSync(p).isDirectory() ? walk(p, { ...cfg, extensions: ['.md'] }) : [p];
    for (const f of files) for (const k of shingleSet(readFileSync(f, 'utf8'), cfg.shingleWords)) specShingles.add(k);
  }

  const files = cfg.include.flatMap((d) => walk(join(root, d), cfg));
  const all = [];
  const clearances = [];
  for (const path of files) {
    const text = readFileSync(path, 'utf8');
    const { findings, cleared } = inspectFile({ path, text, ext: extname(path), cfg, specShingles });
    if (cleared) clearances.push(`${relative(root, path)} (${cleared} lines)`);
    for (const f of findings) {
      if (only.length && !only.includes(f.rule)) continue;
      all.push({ ...f, file: relative(root, path).replace(/\\/g, '/') });
    }
  }

  const byRule = {};
  for (const f of all) (byRule[f.rule] ??= []).push(f);
  for (const rule of Object.keys(byRule).sort()) {
    console.log(`\n${rule} — ${byRule[rule].length}`);
    for (const f of byRule[rule]) console.log(`  ${f.file}:${f.line}  ${f.detail}`);
  }
  if (clearances.length && !argv.includes('--quiet')) {
    console.log(`\ncleared by ${CLEARANCE} (a claim an auditor may reject, not a licence):`);
    for (const c of clearances) console.log(`  ${c}`);
  }
  console.log(`\ncode-shape: ${all.length} finding(s) over ${files.length} file(s).`);

  // A10: SKIPPED is never rendered as PASS. A run that scanned nothing, or that could not
  // check QUOTE for want of a spec corpus, is not a green gate — it is a gate that did not run.
  if (!files.length) {
    console.error(`code-shape: scanned 0 files — check \`include\` in ${configPath}. A green gate over nothing is not a pass.`);
    return 2;
  }
  if (!specShingles.size && !argv.includes('--no-quote')) {
    console.error(`code-shape: no spec corpus resolved from \`specs\`, so the QUOTE rule did not run. Configure it, or pass --no-quote to declare the skip.`);
    return 2;
  }

  const write = arg('--write-baseline');
  if (write) {
    const counts = {};
    for (const f of all) counts[`${f.file}|${f.rule}`] = (counts[`${f.file}|${f.rule}`] ?? 0) + 1;
    writeFileSync(resolve(write), `${JSON.stringify(counts, null, 2)}\n`);
    console.log(`baseline written to ${write} — ${Object.keys(counts).length} file/rule pairs frozen.`);
    console.log('A12: a baseline needs a live ledger item that owns its burn-down, or it is a closed label over unowned work.');
    return 0;
  }

  const basePath = arg('--baseline');
  if (!basePath) return all.length ? 1 : 0;
  if (!existsSync(basePath)) {
    console.error(`code-shape: --baseline ${basePath} does not exist. Write it once with --write-baseline.`);
    return 2;
  }
  const { added, improved } = diffBaseline(all, JSON.parse(readFileSync(basePath, 'utf8')));
  if (improved.length) {
    console.log(`\nburned down (lower the baseline): ${improved.map((i) => `${i.key} ${i.was}→${i.now}`).join(', ')}`);
    // Opt-in, because a gate red on the day it lands is the gate somebody disables (A16):
    // a project turns this on once its baseline is current. Until then the burn-down is only
    // PRINTED, so the next --write-baseline re-freezes whatever happens to survive — the door
    // ESLint's unused-suppression error closes by failing the run rather than reporting it.
    if (argv.includes('--strict-baseline')) {
      console.error(
        `\ncode-shape: the baseline is STALE — ${improved.length} file/rule pair(s) are now cleaner\n` +
          `            than it allows. Lower it with --write-baseline, or the next rebase silently\n` +
          `            re-freezes whatever survives.`,
      );
      return 1;
    }
  }

  // you fix what you touch: a file this phase edited forfeits its grandfathering
  let owed = [];
  const since = arg('--since');
  if (since) {
    const touched = changedSince(root, since);
    if (touched === null) {
      console.error(
        `code-shape: --since ${since} did not resolve to a commit (not a repo, a bad ref, or a shallow\n` +
          `            clone with no history). The burn-down rule did NOT run, and that is not a pass.`,
      );
      return 2;
    }
    owed = touchedViolations(all, touched);
    if (owed.length) {
      console.error(`\nfiles this phase touched still carry findings — a touched file gets no baseline allowance:`);
      for (const f of owed) console.error(`  ${f.file}:${f.line}  ${f.rule}  ${f.detail}`);
    } else if (!touched.length) {
      // an honest pass, stated as what it is: the rule ran and had nothing to judge
      console.log(`burn-down: no files changed since ${since}, so nothing was owed. The rule ran; it judged nothing.`);
    } else {
      console.log(`burn-down: all ${touched.length} file(s) changed since ${since} are clean.`);
    }
  }

  if (!added.length && !owed.length) {
    console.log(`no NEW violations against the baseline${since ? ', and nothing owed on touched files' : ''}.`);
    return 0;
  }
  if (added.length) {
    console.error(`\nNEW violations — the ratchet only turns one way:`);
    for (const a of added) console.error(`  ${a.key}: ${a.count} now, baseline allows ${a.allowed}`);
  }
  return 1;
}

if (process.argv[1] && process.argv[1].endsWith('code-shape.mjs')) {
  process.exit(main(process.argv.slice(2)));
}
