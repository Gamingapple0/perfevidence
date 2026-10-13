"""Score src/claims.py against the hand labels.
Usage: python scripts/score_extractor.py data/eval_prs.jsonl data/eval_labels.csv [out.csv]
Reports precision/recall for "any perf claim" (quantified or unquantified) and for "quantified",
plus r_c recall: the labelled headline r_c matched (within 5%) by any r_c the extractor returns."""
import csv, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from claims import find_claims

def pr(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float('nan')
    r = tp / (tp + fn) if tp + fn else float('nan')
    return f'precision {p:.2f} ({tp}/{tp + fp})  recall {r:.2f} ({tp}/{tp + fn})'

def score(rows, labels):
    out, conf = [], {}
    for r in rows:
        gold = labels[(r['repo'], str(r['number']))]
        status, claims = find_claims(r['title'], r['body'])
        rcs = [c['r_c'] for c in claims if c['r_c']]
        hit = bool(gold['r_c']) and any(abs(x / float(gold['r_c']) - 1) <= 0.05 for x in rcs)
        conf[gold['status'], status] = conf.get((gold['status'], status), 0) + 1
        out.append({'repo': r['repo'], 'number': r['number'], 'gold': gold['status'], 'pred': status,
                    'gold_r_c': gold['r_c'], 'pred_r_c': ';'.join(map(str, rcs)), 'r_c_hit': hit,
                    'quants': ' | '.join(c['quant'] for c in claims)})
    return out, conf

def report(out, conf):
    n = lambda f: sum(1 for o in out if f(o))
    lines = ['gold \\ pred: ' + ', '.join(f'{g}->{p}: {c}' for (g, p), c in sorted(conf.items()))]
    for name, pos in (('any claim', {'quantified', 'unquantified'}), ('quantified', {'quantified'})):
        tp = n(lambda o: o['gold'] in pos and o['pred'] in pos)
        fp = n(lambda o: o['gold'] not in pos and o['pred'] in pos)
        fn = n(lambda o: o['gold'] in pos and o['pred'] not in pos)
        lines.append(f'{name:11s} {pr(tp, fp, fn)}')
    g = [o for o in out if o['gold_r_c']]
    lines.append(f'r_c recall  {sum(o["r_c_hit"] for o in g)}/{len(g)} headline ratios recovered within 5%')
    extra = [o for o in out if o['pred_r_c'] and not o['gold_r_c']]
    lines.append(f'r_c extra   {len(extra)} PRs get a ratio where the label has none')
    return '\n'.join(lines)

if __name__ == '__main__':
    if len(sys.argv) == 1:  # self-check
        rows = [{'repo': 'a/b', 'number': 1, 'title': 'Speed up parser', 'body': '2.5x faster'},
                {'repo': 'a/b', 'number': 2, 'title': 'Fix typo', 'body': 'Docs only.'}]
        labels = {('a/b', '1'): {'status': 'quantified', 'r_c': '2.5'}, ('a/b', '2'): {'status': 'unquantified', 'r_c': ''}}
        out, conf = score(rows, labels)
        assert out[0]['r_c_hit'] and conf == {('quantified', 'quantified'): 1, ('unquantified', 'none'): 1}, (out, conf)
        assert 'recall 0.50 (1/2)' in report(out, conf).splitlines()[1]
        print('ok'); sys.exit()
    rows = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8')]
    labels = {(l['repo'], l['number']): l for l in csv.DictReader(open(sys.argv[2], encoding='utf-8'))}
    out, conf = score(rows, labels)
    print(report(out, conf))
    if len(sys.argv) > 3:
        with open(sys.argv[3], 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
