#!/usr/bin/env node
/**
 * Falsification harness (A16). Language-agnostic: it mutates text and runs a command, so one
 * engine serves a TypeScript or a Python project.
 *
 * Mental model: a green test and a worthless one are the same observation, so the red is the
 * proof. Each case reverts one guard, watches its test fail for a stated reason, restores.
 * Anything that is not "red for the stated reason" fails the run, never skips it.
 *
 * Invariants: the run starts from a verified-green baseline (`baseline` in the case file);
 * the anchor matches exactly once; the mutation is confirmed on disk before the
 * test runs; the sha256-verified restore OVERRIDES the test verdict, so a softened guard
 * cannot ship under a passing receipt; the original bytes are parked outside the repo first,
 * so recovery survives a crash. `--require-clean` restores refuse-if-dirty.
 *
 *   node falsify.mjs [--cases <f>] [--only <id>] [--list] [--json <o>] [--require-clean]
 */
import { readFileSync, writeFileSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { join, resolve, basename } from 'node:path';
import { tmpdir } from 'node:os';

const sha = (s) => createHash('sha256').update(s).digest('hex');
const REQUIRED = ['id', 'file', 'anchor', 'mutation', 'test', 'expect'];

export function validateCase(c, index) {
  const missing = REQUIRED.filter((f) => !c?.[f]);
  if (missing.length) return `case ${c?.id ?? `#${index}`} is missing: ${missing.join(', ')}`;
  if (c.anchor === c.mutation) return `case ${c.id}: anchor and mutation are identical — nothing is reverted`;
  return null;
}

export function occurrences(haystack, needle) {
  let n = 0;
  let i = haystack.indexOf(needle);
  while (i !== -1) {
    n += 1;
    i = haystack.indexOf(needle, i + needle.length);
  }
  return n;
}

function isDirty(root, file) {
  const git = spawnSync('git', ['status', '--porcelain', '--', file], { cwd: root, encoding: 'utf8', shell: false });
  if (git.status !== 0) return false; // not a repo, or git unavailable: the hash restore is the guard
  return git.stdout.trim().length > 0;
}

/**
 * The original bytes, parked OUTSIDE the repo before any mutation: recovery that survives a
 * crash, without copying a dependency tree per case. Why, and the PIT/Stryker comparison:
 * lineage A-V09-EXTERNAL.
 */
function parkOriginal(file, text) {
  const dir = mkdtempSync(join(tmpdir(), 'falsify-backup-'));
  const path = join(dir, basename(file));
  writeFileSync(path, text, 'utf8');
  return { dir, path };
}

function discardBackup(backup) {
  try {
    rmSync(backup.dir, { recursive: true, force: true });
  } catch {
    /* a leftover backup is harmless; losing the guard is not */
  }
}

function runTest(command, root, timeout) {
  const r = spawnSync(command, { cwd: root, shell: true, encoding: 'utf8', timeout, windowsHide: true });
  return { code: r.status, output: `${r.stdout ?? ''}${r.stderr ?? ''}`, timedOut: r.error?.code === 'ETIMEDOUT' };
}

/**
 * The green baseline, once per run — Stryker's initial dry run in one line of config. A
 * case whose test was ALREADY red goes red under the mutation too and is recorded
 * FALSIFIED over a guard nobody has shown to work. One whole-suite run settles it for
 * every case (a filtered subset of a green suite is green) where a per-case dry run would
 * double the wall clock. An undeclared baseline is REPORTED, never assumed (A10).
 */
export function checkBaseline(command, { root, timeout }) {
  if (!command) return { ok: true, declared: false };
  const { code, output, timedOut } = runTest(command, root, timeout);
  if (timedOut) return { ok: false, declared: true, detail: `the baseline command exceeded ${timeout}ms` };
  if (code !== 0) {
    return { ok: false, declared: true, detail: `the baseline suite is RED before any mutation:\n${output.slice(-1500)}` };
  }
  return { ok: true, declared: true };
}

/** The mutate-run-judge middle. Never returns without the file needing a restore. */
function attempt(c, { path, original, root, timeout, fail }) {
  const mutated = original.replace(c.anchor, c.mutation);
  writeFileSync(path, mutated, 'utf8');
  const onDisk = readFileSync(path, 'utf8');
  if (onDisk === original || !onDisk.includes(c.mutation)) {
    return fail('MUTATION_NO_OP', 'the mutation did not land on disk — the edit was a no-op, so any result is unusable');
  }
  const { code, output, timedOut } = runTest(c.test, root, timeout);
  if (timedOut) {
    return fail('TIMEOUT', `test command exceeded ${timeout}ms — the shell was killed, but a grandchild process may survive it and hold a lock; check for strays if the restore then fails`);
  }
  if (code === 0) return fail('STAYED_GREEN', 'the suite passed with the guard reverted — this test pins nothing');
  if (!new RegExp(c.expect, 'i').test(output)) {
    return fail('WRONG_REASON', `went red, but not for its stated reason (/${c.expect}/i not found in the failure output)`);
  }
  return { id: c.id, ok: true, verdict: 'FALSIFIED', detail: `red for its stated reason (/${c.expect}/i)` };
}

/**
 * One case. The restore is judged, not merely attempted: its verdict OVERRIDES the test's,
 * because a `finally` that only logs cannot change a value already returned — and a failed
 * restore would ship a softened guard under a passing receipt (A8).
 */
export function runCase(c, { root, timeout, requireClean = false }) {
  const path = join(root, c.file);
  const fail = (verdict, detail) => ({ id: c.id, ok: false, verdict, detail });

  if (!existsSync(path)) return fail('MISSING_FILE', `${c.file} does not exist`);
  if (requireClean && isDirty(root, c.file)) {
    return fail('DIRTY_TARGET', `${c.file} has uncommitted changes and --require-clean was passed`);
  }

  const original = readFileSync(path, 'utf8');
  const originalHash = sha(original);
  const hits = occurrences(original, c.anchor);
  if (hits !== 1) {
    return fail('ANCHOR_NOT_UNIQUE', `anchor matched ${hits} times, expected exactly 1 — re-point the case at the guard as it now reads`);
  }

  const backup = parkOriginal(c.file, original);
  let result;
  try {
    result = attempt(c, { path, original, root, timeout, fail });
  } catch (e) {
    result = fail('HARNESS_ERROR', e instanceof Error ? e.message : String(e));
  }

  let restoreError = null;
  try {
    writeFileSync(path, original, 'utf8');
    if (sha(readFileSync(path, 'utf8')) !== originalHash) restoreError = 'content does not match the saved sha256';
  } catch (e) {
    restoreError = e instanceof Error ? e.message : String(e);
  }
  if (restoreError !== null) {
    // the backup is deliberately NOT discarded: it is the recovery path, and its location is
    // returned so a caller can act on it rather than hunt through temp
    return {
      ...fail(
        'RESTORE_FAILED',
        `${c.file} may still be MUTATED on disk (${restoreError}). Expected sha256 ${originalHash}. ` +
          `The original is parked at ${backup.path} — restore from it before anything else. ` +
          `This outranks the test result, which was ${result.verdict}.`,
      ),
      backup: backup.path,
    };
  }
  discardBackup(backup);
  return result;
}

function main(argv) {
  const arg = (flag, dflt) => {
    const i = argv.indexOf(flag);
    return i >= 0 ? argv[i + 1] : dflt;
  };
  const root = resolve(arg('--root', '.'));
  const casesPath = resolve(arg('--cases', join(root, 'falsify.cases.json')));
  if (!existsSync(casesPath)) {
    console.error(`falsify: no case list at ${casesPath}. A16: a project whose gate has no harness declares that\n` +
      `         as an open ledger item, never as silence.`);
    return 2;
  }
  const spec = JSON.parse(readFileSync(casesPath, 'utf8'));
  const timeout = Number(spec.timeoutMs ?? 300000);
  let cases = (spec.cases ?? []).map((c) => ({ ...c, test: c.test ?? spec.test }));

  const only = arg('--only');
  if (only) cases = cases.filter((c) => c.id === only);
  if (argv.includes('--list')) {
    for (const c of cases) console.log(`${c.id}\t${c.file}\t/${c.expect}/`);
    return 0;
  }
  if (!cases.length) {
    console.error(only ? `falsify: no case with id "${only}"` : 'falsify: the case list is empty — an empty harness is not a pass');
    return 2;
  }

  const baseline = checkBaseline(spec.baseline, { root, timeout });
  if (!baseline.ok) {
    console.error(
      `falsify: ${baseline.detail}\n` +
        '         No case can be evidence until this passes — a test that was already red goes red\n' +
        '         under the mutation too, and reads as FALSIFIED over a guard nobody has shown to work.',
    );
    return 2;
  }
  console.log(
    baseline.declared
      ? 'falsify: baseline suite green — every case starts from a verified pass.'
      : 'falsify: no `baseline` command in the case list, so no case starts from a verified-green suite (A10).',
  );

  const invalid = cases.map(validateCase).filter(Boolean);
  if (invalid.length) {
    for (const m of invalid) console.error(`falsify: ${m}`);
    return 2;
  }

  const results = [];
  for (const c of cases) {
    process.stdout.write(`  ${c.id} … `);
    const r = runCase(c, { root, timeout, requireClean: argv.includes('--require-clean') });
    results.push(r);
    console.log(r.ok ? `FALSIFIED` : `FAIL (${r.verdict})`);
    if (!r.ok) console.log(`      ${r.detail}`);
  }

  const failed = results.filter((r) => !r.ok);
  const out = arg('--json');
  if (out) writeFileSync(resolve(out), JSON.stringify(results, null, 2));
  console.log(`\nfalsify: ${results.length - failed.length}/${results.length} guards seen red for their stated reason.`);
  if (failed.length) console.log(`         ${failed.length} case(s) failed — a failed case is a finding, not a skip.`);
  return failed.length ? 1 : 0;
}

if (process.argv[1] && process.argv[1].endsWith('falsify.mjs')) {
  process.exit(main(process.argv.slice(2)));
}
