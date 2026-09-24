#!/usr/bin/env node
/**
 * Adoption check — A14 ("re-pointing is machine-checked") plus the decidable half of A13's
 * read-path duty, which binds at every tier.
 *
 * Mental model: a project adopts by hand-typing a version into CLAUDE.md and orients every
 * fresh session from that file. Nothing checked either, so five of eight projects sat two to
 * five versions stale. This checks the declaration: the pin is current, and the files it
 * names exist. It reports that a reference does not resolve, never that prose is true.
 *
 * Exit 0 clean, 1 drift / no declaration / dangling reference, 2 could not run.
 * `--allow-missing` declares a reference whose ABSENCE is the point (a precondition a guard
 * requires before something may be enabled) — see lineage A-V09.
 *
 *   node constitution-drift.mjs <projectDir> [--constitution <p>] [--quiet]
 *                               [--allow-missing a/b.md,c/d.md]
 */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

export function constitutionVersion(text) {
  const m = text.match(/^\*\*v(\d+\.\d+)/m);
  return m ? m[1] : null;
}

export function declaredPin(text) {
  for (const line of text.split(/\r?\n/)) {
    if (!line.includes('SPEC_CONSTITUTION.md')) continue;
    const m = line.match(/\bv(\d+\.\d+)\b/);
    if (m) return { version: m[1], line: line.trim() };
    return { version: null, line: line.trim() }; // names the file, declares no version
  }
  return null;
}

export function check({ pin, current }) {
  if (pin === null) return { ok: false, code: 'NO_DECLARATION' };
  if (pin.version === null) return { ok: false, code: 'NO_VERSION' };
  if (current === null) return { ok: false, code: 'NO_CONSTITUTION_VERSION' };
  if (pin.version !== current) return { ok: false, code: 'DRIFT', pinned: pin.version, current };
  return { ok: true, code: 'CURRENT', current };
}

/**
 * Files the read path names *as paths*: markdown link targets, plus backticked tokens
 * containing a `/`. A bare basename is a NAME, not a root-relative path — treating it as one
 * produced false positives in four of five projects (lineage A-V09-EXTERNAL).
 */
export function namedFiles(text) {
  const out = new Set();
  for (const m of text.matchAll(/\]\(([^)\s#]+)\)/g)) {
    if (!/^(https?:|mailto:)/.test(m[1])) out.add(m[1]);
  }
  for (const m of text.matchAll(/`([\w.-]+(?:\/[\w.-]+)+\.(?:md|ts|tsx|js|mjs|cjs|py|json|ya?ml|toml|ps1))`/g)) {
    out.add(m[1]);
  }
  return [...out];
}

/**
 * A reference resolves at the project root or under any of `roots`: these docs legitimately
 * write paths relative to a source root (`cli/render.ts` meaning `src/cli/render.ts`).
 */
export function danglingRefs(text, root, roots = [], allowMissing = []) {
  const bases = ['.', ...roots];
  const allowed = new Set(allowMissing);
  return namedFiles(text)
    .filter((f) => !allowed.has(f))
    .filter((f) => !bases.some((b) => existsSync(resolve(root, b, f))));
}

/** First-level directories, as the source roots a reference may be written against. */
function sourceRoots(dir) {
  const skip = new Set(['node_modules', '.git', 'dist', 'build', 'coverage', 'logs', '__pycache__']);
  try {
    return readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isDirectory() && !skip.has(e.name))
      .map((e) => e.name);
  } catch {
    return [];
  }
}

const MESSAGES = {
  NO_DECLARATION: 'CLAUDE.md names no constitution (A2 is structural — it binds at every tier).',
  NO_VERSION: 'CLAUDE.md names the constitution but declares no version — nothing to check against.',
  NO_CONSTITUTION_VERSION: 'could not read a version from the constitution itself.',
};

function main(argv) {
  const args = argv.filter((a) => !a.startsWith('--'));
  const projectDir = resolve(args[0] ?? '.');
  const cIdx = argv.indexOf('--constitution');
  const constitutionPath = cIdx >= 0 ? resolve(argv[cIdx + 1]) : resolve(HERE, '..', 'SPEC_CONSTITUTION.md');
  const quiet = argv.includes('--quiet');

  const claudeMd = join(projectDir, 'CLAUDE.md');
  for (const [label, path] of [['CLAUDE.md', claudeMd], ['constitution', constitutionPath]]) {
    if (!existsSync(path)) {
      console.error(`constitution-drift: cannot run — no ${label} at ${path}`);
      return 2;
    }
  }

  const current = constitutionVersion(readFileSync(constitutionPath, 'utf8'));
  const claudeText = readFileSync(claudeMd, 'utf8');
  const pin = declaredPin(claudeText);
  const result = check({ pin, current });

  // A13: a lie in the read path is a bug fixed on sight. A reference to a file that is not
  // there is the decidable half of that — reported even when the pin is current.
  const aIdx = argv.indexOf('--allow-missing');
  const allowMissing = aIdx >= 0 ? (argv[aIdx + 1] ?? '').split(',').map((x) => x.trim()).filter(Boolean) : [];
  const dangling = danglingRefs(claudeText, projectDir, sourceRoots(projectDir), allowMissing);

  if (result.ok && !dangling.length) {
    if (!quiet) console.log(`constitution-drift: OK — pinned at v${result.current}, and every file CLAUDE.md names exists.`);
    return 0;
  }
  if (dangling.length) {
    console.error(
      `constitution-drift: CLAUDE.md names ${dangling.length} file(s) that do not exist — the read path is orienting ` +
        `fresh sessions at something gone (A13):\n${dangling.map((d) => `  ${d}`).join('\n')}`,
    );
    if (result.ok) return 1;
  }
  if (result.code === 'DRIFT') {
    console.error(
      `constitution-drift: STALE — this project pins v${result.pinned}, the constitution is at v${result.current}.\n` +
        `  Read the amendments between them, discharge each into the ledger (how it binds here, or that\n` +
        `  it does not and why), then move the pin. A14: an undischarged pin bump is a false receipt.`,
    );
    return 1;
  }
  console.error(`constitution-drift: ${MESSAGES[result.code]}`);
  return 1;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  process.exit(main(process.argv.slice(2)));
}
