"""Find performance claims in a PR's title + description and parse the claimed gain ratio r_c.

status: 'quantified' (at least one numeric claim), 'unquantified' (perf words, no numbers) or 'none'.
r_c > 1 means the claim says "better": 2.0 for "2x faster", 1.67 for "40% less memory",
1.5 for "from 120ms to 80ms". None when the claim has a number but no comparison ("takes 80ms").
Dimension detection is Purdue's extractor (purdue_extract.py); this file only adds the ratio."""
import re
import metric_patterns as mp
from purdue_extract import extract_dimensions

NUM_RE = re.compile(mp.NUM)
UNIT_SCALE = {'ns': 1e-9, 'us': 1e-6, 'ms': 1e-3, 's': 1, 'min': 60, 'hr': 3600,
              'b': 1, 'kb': 1e3, 'mb': 1e6, 'gb': 1e9, 'tb': 1e12}
NUM_UNIT_RE = re.compile(rf"({mp.NUM})\s?({'|'.join(sorted(UNIT_SCALE, key=len, reverse=True))})?\b")
SHRINK_RE = re.compile(r'reduc|decreas|less|fewer|lower|smaller|cut|sav|drop|shr[aiu]n?k|down|(?<![\w.])-\s?\d')
HIGHER_IS_BETTER = {'D2'}  # throughput; every other dimension is a cost
PERF_WORDS = re.compile(r'\b(perf(ormance)?|faster|speed[- ]?up|optimi[sz]\w*|latency|throughput|'
                        r'memory|allocation|efficien\w*|overhead|bottleneck|slow\w*)\b', re.I)

def _num(s):
    return float(s.lstrip('~').replace(',', '').strip())

def ratio(kind, quant, dim, before=''):
    """Claimed gain ratio from one matched quantitative span, or None. ``before``: the few words
    preceding the span, which carry the direction in "reducing X by 40%"."""
    if kind == 'self':  # self-sufficient cue, e.g. "2.5x faster": parse by shape
        kind = 'mult' if re.search(r'\dx\b|times', quant) else 'pct' if '%' in quant or 'percent' in quant else None
    nums = NUM_RE.findall(quant)
    if kind == 'mult' and nums:
        return _num(nums[0]) or None
    if kind == 'pct' and nums:
        p = _num(nums[0]) / 100
        if SHRINK_RE.search(f'{before} {quant}'):
            return 1 / (1 - p) if p < 1 else None
        return 1 + p
    if kind == 'from_to':
        pairs = NUM_UNIT_RE.findall(quant)[:2]
        if len(pairs) < 2:
            return None
        (a, ua), (b, ub) = pairs
        ua, ub = ua or ub, ub or ua  # "from 120 to 80mb": the unit carries over
        a, b = _num(a) * UNIT_SCALE.get(ua, 1), _num(b) * UNIT_SCALE.get(ub, 1)
        if not a or not b:
            return None
        return b / a if dim in HIGHER_IS_BETTER else a / b
    return None  # a bare measurement ("takes 80ms") or one side of before/after

def find_claims(title, body):
    raw = f"{title or ''}\n\n{body or ''}"
    norm = mp.normalize(raw)
    cands = [(dim, m) for dim, ms in extract_dimensions(raw, include_positions=True).items() for m in ms]
    # Purdue's patterns can match one claim several times with overlapping spans; keep the tightest
    cands.sort(key=lambda dm: dm[1]['quant_end'] - dm[1]['quant_start'])
    out, taken = [], []
    for dim, m in cands:
        s, e = m['quant_start'], m['quant_end']
        if any(s < te and ts < e for ts, te in taken):
            continue
        taken.append((s, e))
        quant = norm[s:e]
        r = ratio(m['quant_kind'], quant, dim, ' '.join(norm[max(0, s - 60):s].split()[-5:]))
        out.append({'dim': dim, 'kind': m['quant_kind'], 'quant': ' '.join(quant.split()),
                    'r_c': round(r, 3) if r else None, 'snippet': m['snippet']})
    status = 'quantified' if out else 'unquantified' if PERF_WORDS.search(raw) else 'none'
    return status, out

if __name__ == '__main__':
    assert ratio('mult', '2.5x faster', 'D1') == 2.5
    assert abs(ratio('pct', 'reduced memory by 40%', 'D3') - 1 / 0.6) < 1e-9
    assert abs(ratio('pct', '40% faster', 'D1') - 1.4) < 1e-9
    assert abs(ratio('from_to', 'from 1.2s to 800ms', 'D1') - 1.5) < 1e-9
    assert abs(ratio('from_to', 'from 120mb to 80', 'D3') - 1.5) < 1e-9
    assert ratio('from_to', 'from 1000 req/s to 2000', 'D2') == 2
    assert abs(ratio('pct', 'by ~62.5%', 'D5', 'reducing gpu readback data') - 1 / 0.375) < 1e-9
    assert ratio('time', '80ms', 'D1') is None
    s, c = find_claims('Speed up parser', 'This makes parsing 2.5x faster and cuts memory from 120MB to 80MB.')
    assert s == 'quantified' and sorted(x['r_c'] for x in c) == [1.5, 2.5], c
    assert find_claims('Optimize render loop', 'Avoids re-renders.')[0] == 'unquantified'
    assert find_claims('Fix typo', 'Docs only.')[0] == 'none'
    print('ok')
