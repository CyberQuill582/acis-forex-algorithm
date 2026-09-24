/**
 * A12's shape rules, as pure functions over text — no disk, no git, no argv.
 *
 * Split from the CLI shell because the shell outgrew the 300-line budget this very module
 * enforces, and a reviewer could name the extraction: the rules have their own name, their
 * own tests, one responsibility. Same split as KALLOS uses for closure-rules.
 *
 * Rules, each failing independently so one noisy rule cannot mask another:
 *  - SIZE     over maxLines, uncleared by a justification token carrying a real reason.
 *  - HEADER   the top comment block over headerMax lines.
 *  - BLOCK    any later comment block over blockMax lines.
 *  - HISTORY  a comment that narrates rather than stating the invariant.
 *  - QUOTE    a comment sharing a verbatim run of shingleWords with a spec document.
 * A ratio is deliberately absent: it would fire on the mental-model headers A12 requires.
 */
export const DEFAULTS = {
  include: ['core', 'server', 'scripts', 'src'],
  specs: [],
  exclude: ['node_modules', 'archive', 'dist', 'build', '__pycache__', '.git', 'coverage'],
  extensions: ['.ts', '.js', '.mjs', '.py'],
  maxLines: 300,
  headerMax: 20,
  blockMax: 5,
  shingleWords: 12,
};
// Bare "used to" is dropped deliberately: its instrumental sense is pervasive in technical
// English ("the sha256 used to verify the restore"), and an external audit measured two false
// positives in three ordinary comments. Google's bar for a check developers keep is under 10%
// effective false positives; a noisy rule is a rule that gets switched off. "used to be" keeps
// the narrative sense, which is the one the ledger owns.
const HISTORY = /\b(previously|formerly|used to be|earlier draft|prior draft|in an earlier|the audit found|we decided|was renamed|before this change|as of the last)\b/i;
export const CLEARANCE = 'A12-SIZE-JUSTIFIED:';


/** Consecutive comment lines, grouped. Python docstrings count: they are that file's header. */
export function commentBlocks(text, ext) {
  const lines = text.split(/\r?\n/);
  const isPy = ext === '.py';
  const marks = new Array(lines.length).fill(false);
  let inBlock = false;
  let fence = null;

  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (inBlock) {
      marks[i] = true;
      if (isPy ? line.includes(fence) : line.includes('*/')) inBlock = false;
      return;
    }
    if (isPy) {
      const m = line.match(/^(?:[rubf]{0,2})("""|''')/i);
      if (m) {
        marks[i] = true;
        const rest = line.slice(line.indexOf(m[1]) + 3);
        if (!rest.includes(m[1])) {
          inBlock = true;
          fence = m[1];
        }
        return;
      }
      if (line.startsWith('#')) marks[i] = true;
      return;
    }
    if (line.startsWith('/*')) {
      marks[i] = true;
      if (!line.includes('*/')) inBlock = true;
      return;
    }
    if (line.startsWith('//') || line.startsWith('*')) marks[i] = true;
  });

  const blocks = [];
  let start = -1;
  marks.forEach((isComment, i) => {
    if (isComment && start === -1) start = i;
    if (!isComment && start !== -1) {
      blocks.push({ start: start + 1, end: i, lines: lines.slice(start, i) });
      start = -1;
    }
  });
  if (start !== -1) blocks.push({ start: start + 1, end: lines.length, lines: lines.slice(start) });
  return blocks;
}

const normalize = (s) =>
  s
    .toLowerCase()
    .replace(/[`*_#>|\[\]()"'’“”]/g, ' ')
    .replace(/[^a-z0-9§.\-\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);

export function shingleSet(text, n) {
  const words = normalize(text);
  const set = new Set();
  for (let i = 0; i + n <= words.length; i += 1) set.add(words.slice(i, i + n).join(' '));
  return set;
}

export function quotedShingle(commentText, specShingles, n) {
  const words = normalize(commentText);
  for (let i = 0; i + n <= words.length; i += 1) {
    const key = words.slice(i, i + n).join(' ');
    if (specShingles.has(key)) return key;
  }
  return null;
}

/**
 * The clearance token, and the reason it must carry. A bare token would clear a file of
 * any length, which is the licence A12 says a justification is not; a reason too short to
 * name a spec requirement is the same thing with punctuation.
 */
export function clearanceReason(text) {
  // the token must OPEN a comment line, not merely appear on one: a mention inside a string
  // literal is a mention, and one was silently clearing a 426-line file
  const m = text.match(/^[ \t]*(?:\/\/|#|\*|\/\*)[ \t]*A12-SIZE-JUSTIFIED:[ \t]*(\S.*)$/m);
  const reason = m?.[1]?.trim() ?? null;
  return reason !== null && reason.length >= 12 ? reason : null;
}

export function inspectFile({ path, text, ext, cfg, specShingles }) {
  const findings = [];
  const lines = text.split(/\r?\n/);
  const count = lines.length - (lines.at(-1) === '' ? 1 : 0); // a trailing newline is not a line
  const cleared = clearanceReason(text) !== null;
  if (count > cfg.maxLines && !cleared) {
    const bare = text.includes(CLEARANCE) ? ' — the clearance token carries no usable reason' : '';
    findings.push({ rule: 'SIZE', line: 1, detail: `${count} lines > ${cfg.maxLines}${bare}` });
  }
  const blocks = commentBlocks(text, ext);
  blocks.forEach((b, idx) => {
    // the header is the block nothing but blanks and a shebang precedes; a block that
    // follows code is prose in the body, held to the tighter cap
    const isHeader = idx === 0 && lines.slice(0, b.start - 1).every((l) => l.trim() === '' || l.startsWith('#!'));
    const body = b.lines.join('\n');
    const limit = isHeader ? cfg.headerMax : cfg.blockMax;
    if (b.lines.length > limit) {
      findings.push({ rule: isHeader ? 'HEADER' : 'BLOCK', line: b.start, detail: `${b.lines.length} comment lines > ${limit}` });
    }
    const hist = body.match(HISTORY);
    if (hist) findings.push({ rule: 'HISTORY', line: b.start, detail: `narrates: "${hist[0]}"` });
    if (specShingles.size) {
      const quote = quotedShingle(body, specShingles, cfg.shingleWords);
      if (quote) findings.push({ rule: 'QUOTE', line: b.start, detail: `verbatim spec run: "${quote.slice(0, 70)}…"` });
    }
  });
  return { findings, cleared: cleared && count > cfg.maxLines ? count : null };
}

/**
 * The burn-down rule: a file this phase touched gets no baseline allowance. Without it the
 * baseline is a permanent amnesty. Sonar's new-code model is the nearest practice and is
 * NOT identical: it measures against a COMMITTED reference — previous version, a date, an
 * analysis, or a branch — so its verdict survives the commit, where a `--since HEAD` diff
 * sees only an uncommitted working tree (lineage A-V09-EXTERNAL; the earlier "identical"
 * claim was withdrawn as false about the world).
 */
export function touchedViolations(findings, touched) {
  const set = new Set(touched);
  return findings.filter((f) => set.has(f.file));
}


/**
 * A12's ratchet. Keyed by file+rule, not by line, so an edit above a finding does not
 * read as a new one. More than the baseline allows in a file fails; fewer is the
 * burn-down, reported so the baseline can be lowered and never silently raised.
 */
export function diffBaseline(findings, baseline) {
  const counts = {};
  for (const f of findings) {
    const k = `${f.file}|${f.rule}`;
    counts[k] = (counts[k] ?? 0) + 1;
  }
  const added = Object.entries(counts)
    .filter(([k, n]) => n > (baseline[k] ?? 0))
    .map(([k, n]) => ({ key: k, count: n, allowed: baseline[k] ?? 0 }));
  const improved = Object.entries(baseline)
    .filter(([k, n]) => (counts[k] ?? 0) < n)
    .map(([k, n]) => ({ key: k, was: n, now: counts[k] ?? 0 }));
  return { added, improved, counts };
}
