"""Claimed gain ratios (r_c) from a PR title + description.

r_c > 1 means the claim says "better": 2.0 for "2x faster", 1.67 for "40% less memory",
1.5 for "from 120ms to 80ms". Every metric is treated as a cost (lower is better) unless it is
a rate (ops/s, throughput), where higher is better.

Runs on Purdue's normalized text, with two local fixes (see normalize()). Unlike Purdue's
dimension extractor it does not drop prospective claims ("expected 2x faster"): a claim the
PR makes is a claim PerfEvidence should test. Ranges ("5-10x", "20-40%") use the lower bound.
Claims of a slowdown or regression ("100x slowdown", "20x regression") are skipped: they
describe the bug, not the gain."""
import re
import metric_patterns as mp

# Purdue strips 7-40 char hex runs as commit SHAs, which also eats long digit runs such as
# "4.321790659222757%". Require at least one a-f letter. Also fold the Unicode minus sign.
mp._HEX_RE = re.compile(r'\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b')

def normalize(text):
    return mp.normalize(text).replace('−', '-')

NUM = r'\d(?:[\d,]*\d)?(?:\.\d+)?'
SCALE = {'ns': 1e-9, 'us': 1e-6, 'ms': 1e-3, 's': 1, 'min': 60, 'hr': 3600,
         'b': 1, 'kb': 1e3, 'mb': 1e6, 'gb': 1e9, 'tb': 1e12}
FAMILY = {**{u: 'time' for u in ('ns', 'us', 'ms', 's', 'min', 'hr')},
          **{u: 'bytes' for u in ('b', 'kb', 'mb', 'gb', 'tb')}}
UNIT = (r'(?:ns|us|ms|s|min|hr|b|kb|mb|gb|tb|ir|allocs?(?:/op)?|queries|calls|requests|'
        r'ops?/s|req/s|rps|qps|tps|fps|tokens?/s|(?:kb|mb|gb)/s)')
RATE = re.compile(r'/s$|^(?:rps|qps|tps|fps)$')
GAIN = r'(?:faster|quicker|speed[- ]?ups?|improve\w*|gains?|boost\w*|better|more throughput|throughput)'
SHRINK = (r'(?:reduc\w*|decreas\w*|less|fewer|lower\w*|smaller|cut\w*|sav\w*|drop\w*|'
          r'shr[aiu]n?k\w*|down|eliminat\w*|shorter)')
BAD = re.compile(r'slower|slowdown|regress\w*|worse|degrad\w*')
WRAP = r'[`*_(\[]{0,3}'
UNWRAP = r'[`*_)\]]{0,3}'

def _f(s):
    return float(s.replace(',', ''))

def _words(t, s, e, n_before, n_after):
    return ' '.join(t[max(0, s - 80):s].split()[-n_before:]), ' '.join(t[e:e + 80].split()[:n_after])

MULT_RE = re.compile(rf'(?<![\w.]){WRAP}~?({NUM})(?:\s?-\s?({NUM}))?\s?x\b(?!\s*\d)')
PCT_RE = re.compile(rf'(?<![\w.])([-+])?\s?~?({NUM})(?:\s?-\s?({NUM}))?\s?(?:%|percent\b)')
FROM_TO_RE = re.compile(
    rf'(\bfrom\s+)?{WRAP}~?({NUM})\s?({UNIT})?\b(?:\s*/\s*{NUM}\s?(?:({UNIT})\b|%)?)?{UNWRAP}\s*'
    rf'(->|\bto\b)\s*(?:less than\s+|under\s+|about\s+|~)?{WRAP}~?({NUM})\s?({UNIT})?\b')
HALF_RE = re.compile(r'\bhalv(?:e|es|ed|ing)\b|\b(?:by|in) half\b|\bdoubl\w* (?:the )?(?:throughput|speed|performance)\b')
CELL_X_RE = re.compile(rf'^~?({NUM})\s?x$')

def _mult(t):
    for m in MULT_RE.finditer(t):
        before, after = _words(t, m.start(), m.end(), 4, 4)
        if BAD.search(after.split(' ', 2)[0] if after else '') or BAD.search(' '.join(after.split()[:2])):
            continue
        in_cell = re.match(r'\s*\|', t[m.end():m.end() + 5]) and t[:m.start()].rstrip(' `*~').endswith('|')
        if in_cell or re.search(rf'^\W*(?:\w+\W+){{0,3}}?{GAIN}|^\W*{SHRINK}|^\W*(?:fewer|less|smaller)', after) \
                or re.search(rf'{GAIN}\W*(?:\w+\W*){{0,2}}$', before):
            yield _f(m.group(1)), m.group(0).strip()

def _pct(t):
    for m in PCT_RE.finditer(t):
        p = _f(m.group(2)) / 100
        before, after = _words(t, m.start(), m.end(), 5, 4)
        if BAD.search(' '.join(after.split()[:2])) or BAD.search(' '.join(before.split()[-3:])) \
                or re.search(r'coverage|cpu usage|utili[sz]', before + ' ' + after):
            continue
        first_after = ' '.join(after.split()[:3])
        if re.search(rf'^\W*(?:\w+\W+)?{GAIN}', first_after) or m.group(1) == '+':
            yield 1 + p, m.group(0).strip()
        elif re.search(rf'^\W*(?:\w+\W+)?{SHRINK}', first_after) or re.search(SHRINK, before) or m.group(1) == '-':
            if p < 1:
                yield 1 / (1 - p), m.group(0).strip()
        elif re.search(GAIN, before):
            yield 1 + p, m.group(0).strip()

def _from_to(t):
    for m in FROM_TO_RE.finditer(t):
        frm, a, ua, ua2, arrow, b, ub = m.groups()
        ua = ua or ua2
        if not frm and arrow != '->':
            continue
        if not (frm or ua or ub):
            continue
        ua, ub = ua or ub, ub or ua
        if FAMILY.get(ua, ua) != FAMILY.get(ub, ub):
            continue
        x, y = _f(a) * SCALE.get(ua, 1), _f(b) * SCALE.get(ub, 1)
        if not x or not y or x == y:
            continue
        r = y / x if RATE.search(ua or '') else x / y
        yield r, ' '.join(m.group(0).split())

BEFORE_COL = re.compile(r'^(?:before|baseline|base|old|main|master|next|original|current)\b')
AFTER_COL = re.compile(r'^(?:after|this (?:pr|branch)|new|optimi[sz]ed|pr|head|patched|branch)\b')
SPEED_COL = re.compile(r'^(?:speed[- ]?up|ratio|improvement|gain|change|delta|δ|diff)\b')
CELL_NUM = re.compile(rf'^~?({NUM})\s?({UNIT})?$')

def _tables(t):
    rows = [l.strip() for l in t.split('\n')]
    head = None
    for line in rows:
        if not line.startswith('|'):
            head = None
            continue
        cells = [re.sub(r'[`*_]', '', c).strip() for c in line.strip('|').split('|')]
        if all(re.fullmatch(r':?-+:?', c) for c in cells if c):
            continue
        if head is None:
            head = cells
            continue
        bi = next((i for i, c in enumerate(head) if BEFORE_COL.search(c)), None)
        ai = next((i for i, c in enumerate(head) if AFTER_COL.search(c)), None)
        si = next((i for i, c in enumerate(head) if SPEED_COL.search(c)), None)
        if si is not None and si < len(cells):
            m = CELL_X_RE.match(cells[si])
            if m:
                yield _f(m.group(1)), cells[si]
            else:
                yield from _pct(f' {cells[si]} ')
        if bi is not None and ai is not None and max(bi, ai) < len(cells):
            ma, mb = CELL_NUM.match(cells[bi]), CELL_NUM.match(cells[ai])
            if ma and mb:
                ua, ub = ma.group(2) or mb.group(2), mb.group(2) or ma.group(2)
                x, y = _f(ma.group(1)) * SCALE.get(ua, 1), _f(mb.group(1)) * SCALE.get(ub, 1)
                if x and y and x != y:
                    yield (y / x if RATE.search(ua or '') else x / y), f'{cells[bi]} | {cells[ai]}'

def find_ratios(title, body):
    """List of (r_c, matched text), in text order per rule, gains only (r_c > 1, < 10000)."""
    t = normalize(f"{title or ''}\n\n{body or ''}")
    out = []
    for rule in (_mult, _pct, _from_to, _tables):
        out += [(round(r, 3), q, rule.__name__[1:]) for r, q in rule(t) if 1 < r < 1e4]
    out += [(2.0, m.group(0), 'half') for m in HALF_RE.finditer(t)]
    return out

if __name__ == '__main__':
    rc = lambda s: sorted({r for r, _, _ in find_ratios('', s)})
    assert rc('This is 2.5x faster.') == [2.5]
    assert rc('~80% reduction in allocations') == [5.0]
    assert rc('bulk operations complete ~10% faster') == [1.1]
    assert rc('20-40% faster mesh combining') == [1.2]
    assert rc('gains (5-10x for small files)') == [5.0]
    assert rc('Multi-threading delivers 4.8–7.6× speedup') == [4.8]
    assert rc('reduced time from `32.67/32.63 ms` to `31.57/31.63 ms`') == [1.035]
    assert rc('reduces CI time from ~20 minutes to less than 1 minute') == [20.0]
    assert rc('25.6 s → 19.1 s (−25 %)') == [1.333, 1.34]
    assert rc('`206,953,778 Ir / 21.02%` -> `180,452,234 Ir / 18.83%`') == [1.147]
    assert rc('throughput from 1000 ops/s to 2000 ops/s') == [2.0]
    assert rc('a >100x slowdown reported in #1') == []
    assert rc('bump dependency from 3 to 4') == []  # cost ratio < 1 is not a gain
    assert rc('halving the number of big-integer operations') == [2.0]
    assert rc('| op | before | after |\n|---|---|---|\n| a | 76,240 | 58,640 |') == [1.3]
    assert rc('| op | `next` | this PR | Speedup |\n|--|--|--|--|\n| a | 29.1 ms | 7.8 ms | ~3.7× |') == [3.7, 3.731]
    assert rc('Net regression: +1.4 µs (+5.58%)') == []
    assert rc('public delta: 4.321790659222757%') == []
    print('ok')
