"""Random extractor-evaluation set: N agentic perf PRs from the Purdue study (any language), fixed seed.
Drawn without looking at any extractor output, so recall is not inflated.
Usage: build_eval_set.py PURDUE_RQ1_LABELS_CSV OUT_CSV [N] [SEED] [EXCLUDE_CSV]
  dev set (13 Oct 2026 and earlier):  build_eval_set.py rq1_labels.csv data/eval_set.csv 100
  held-out set:  build_eval_set.py rq1_labels.csv data/holdout_set.csv 50 20261013 data/eval_set.csv"""
import sys
import pandas as pd

SEED = 20261011  # differs from the sample seed so the two draws are independent

def main(labels, out, n=100, seed=SEED, exclude=None):
    l = pd.read_csv(labels)
    a = l[(l.sample_arm == 'agentic') & l.included_in_analysis]
    if exclude:
        a = a[~a.html_url.isin(set(pd.read_csv(exclude).html_url))]
    e = a.sample(n=int(n), random_state=int(seed)).sort_values(['repo_full_name', 'number'])
    e.rename(columns={'repo_full_name': 'repo'})[['repo', 'number', 'html_url']].to_csv(out, index=False)
    print(f'{len(e)} PRs from {e.repo_full_name.nunique()} repos')

if __name__ == '__main__':
    main(*sys.argv[1:6])
