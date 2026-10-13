"""Find performance claims in a PR's title + description and parse the claimed gain ratio r_c.

status: 'quantified' (a number tied to a perf claim, before or after values included),
'unquantified' (perf words, no numbers) or 'none'.
Dimension detection is Purdue's extractor (purdue_extract.py). Ratios come from ratios.py,
which scans the whole text; each ratio is returned as its own claim with dim None.
r_c > 1 means the claim says "better" (see ratios.py)."""
import re
import ratios  # first: patches Purdue's SHA filter before purdue_extract normalizes anything
from purdue_extract import extract_dimensions

PERF_WORDS = re.compile(r'\b(perf(ormance)?|faster|speed[- ]?up|optimi[sz]\w*|latency|throughput|'
                        r'memory|allocation|efficien\w*|overhead|bottleneck|slow\w*)\b', re.I)

# A number describing the problem or the before state ("freezing the UI for 7-8 seconds",
# "a >100x slowdown") still makes the PR's claim quantified, though it gives no r_c.
BASE_NUM = re.compile(rf'(?<![\w.])~?{ratios.NUM}\s?(?:x\b|%|(?:ns|us|ms|s|min|hr|b|kb|mb|gb|tb)\b)')
BASE_CTX = re.compile(r'slow\w*|bottleneck\w*|freez\w*|\blag\w*|regress\w*|overhead|latenc\w*|block\w*|'
                      r'hang\w*|stall\w*|took|takes?|taking|cost\w*')

def baseline_numbers(title, body):
    t = ratios.normalize(f"{title or ''}\n\n{body or ''}")
    return [s.strip() for s in re.split(r'(?<=[.!?])\s|\n', t) if BASE_CTX.search(s) and BASE_NUM.search(s)]

def find_claims(title, body):
    raw = f"{title or ''}\n\n{body or ''}"
    out = [{'dim': dim, 'kind': m['quant_kind'], 'quant': m['quant'], 'r_c': None, 'snippet': m['snippet']}
           for dim, ms in extract_dimensions(raw, include_positions=True).items() for m in ms]
    out += [{'dim': None, 'kind': rule, 'quant': q, 'r_c': r, 'snippet': q}
            for r, q, rule in ratios.find_ratios(title, body)]
    out += [{'dim': None, 'kind': 'baseline', 'quant': q[:80], 'r_c': None, 'snippet': q[:200]}
            for q in baseline_numbers(title, body)]
    status = 'quantified' if out else 'unquantified' if PERF_WORDS.search(raw) else 'none'
    return status, out

if __name__ == '__main__':
    s, c = find_claims('Speed up parser', 'This makes parsing 2.5x faster and cuts memory from 120MB to 80MB.')
    assert s == 'quantified' and sorted({x['r_c'] for x in c if x['r_c']}) == [1.5, 2.5], c
    assert find_claims('Optimize render loop', 'Avoids re-renders.')[0] == 'unquantified'
    assert find_claims('Fix typo', 'Docs only.')[0] == 'none'
    assert find_claims('Fix freeze', 'It was freezing the UI for 7-8 seconds.')[0] == 'quantified'
    print('ok')
