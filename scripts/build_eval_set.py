"""Random extractor-evaluation set: N agentic perf PRs from the Purdue study (any language), fixed seed.
Drawn without looking at any extractor output, so recall is not inflated.
Usage: build_eval_set.py PURDUE_RQ1_LABELS_CSV OUT_CSV [N]"""
import sys
import pandas as pd

SEED = 20261011  # differs from the sample seed so the two draws are independent

def main(labels, out, n=100):
    l = pd.read_csv(labels)
    a = l[(l.sample_arm == 'agentic') & l.included_in_analysis]
    e = a.sample(n=int(n), random_state=SEED).sort_values(['repo_full_name', 'number'])
    e.rename(columns={'repo_full_name': 'repo'})[['repo', 'number', 'html_url']].to_csv(out, index=False)
    print(f'{len(e)} PRs from {e.repo_full_name.nunique()} repos')

if __name__ == '__main__':
    main(*sys.argv[1:4])
