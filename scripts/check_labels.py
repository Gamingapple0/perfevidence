"""Check that every quoted span in eval_labels.csv's evidence column appears in the PR title or body.
Whitespace is collapsed before matching, so line breaks and table padding do not matter; every
other character (dashes, x vs ×, µ, backticks) must match the PR text exactly.
Usage: python scripts/check_labels.py data/eval_prs.jsonl data/eval_labels.csv"""
import csv, json, re, sys

ws = lambda s: re.sub(r'\s+', ' ', s)

def missing(text, evidence):
    return [q for q in re.findall(r'"([^"]+)"', evidence) if ws(q) not in ws(text)]

if __name__ == '__main__':
    prs = {(p['repo'], str(p['number'])): p for p in map(json.loads, open(sys.argv[1], encoding='utf-8'))}
    bad = 0
    for l in csv.DictReader(open(sys.argv[2], encoding='utf-8')):
        p = prs[l['repo'], l['number']]
        m = missing(f"{p['title'] or ''}\n{p['body'] or ''}", l['evidence'])
        if m:
            bad += 1; print(l['repo'], l['number'], m)
    print(f'{bad} rows with evidence not found verbatim'); sys.exit(1 if bad else 0)
