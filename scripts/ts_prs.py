"""List agentic perf PRs (Purdue study, included in analysis) whose repo language is TypeScript (AIDev metadata).
Usage: ts_prs.py PURDUE_RQ1_LABELS_CSV AIDEV_ALL_REPOSITORY_PARQUET OUT_CSV"""
import sys
import pandas as pd

def main(labels, repos, out):
    l = pd.read_csv(labels)
    a = l[(l.sample_arm == 'agentic') & l.included_in_analysis]
    r = pd.read_parquet(repos, columns=['full_name', 'language', 'stars']).drop_duplicates('full_name')
    m = a.merge(r, left_on='repo_full_name', right_on='full_name', how='left', validate='many_to_one')
    print(len(a), 'agentic PRs;', m.language.value_counts().head(6).to_dict())
    m[m.language == 'TypeScript'][['repo_id', 'number', 'repo_full_name', 'html_url', 'stars']].to_csv(out, index=False)

if __name__ == '__main__':
    main(*sys.argv[1:4])
