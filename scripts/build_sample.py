"""Sample agentic TS perf PRs from repos with benchmarks; at most 3 per repo, fixed seed.
Usage: build_sample.py TS_PRS_CSV BENCH_REPOS_CSV OUT_CSV"""
import csv, random, sys
from collections import defaultdict

SEED, CAP = 20261010, 3

def tier(repo):
    """adapter = what the Action can run (npm bench script or vitest *.bench files); tree = any bench-like file."""
    if repo['npm_bench_scripts'] or int(repo['vitest_bench_files']):
        return 'adapter'
    return 'tree' if repo['has_bench'] == 'True' else None

def main(prs_csv, bench_csv, out_csv):
    tiers = {r['repo']: tier(r) for r in csv.DictReader(open(bench_csv))}
    by_repo = defaultdict(list)
    for pr in csv.DictReader(open(prs_csv)):
        if tiers.get(pr['repo_full_name']):
            by_repo[pr['repo_full_name']].append(pr)
    rng = random.Random(SEED)
    rows = []
    for repo in sorted(by_repo):  # sorted so the seed gives the same draw every time
        prs = sorted(by_repo[repo], key=lambda p: int(p['number']))
        for pr in rng.sample(prs, min(CAP, len(prs))):
            rows.append({'repo': repo, 'number': pr['number'], 'html_url': pr['html_url'],
                         'bench_tier': tiers[repo], 'repo_prs_available': len(prs)})
    with open(out_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    for t in ('adapter', 'tree'):
        rs = {r for r, v in tiers.items() if v == t and r in by_repo}
        print(f"{t}: {len(rs)} repos, {sum(len(by_repo[r]) for r in rs)} PRs available, "
              f"{sum(1 for x in rows if x['bench_tier'] == t)} sampled")

if __name__ == '__main__':
    assert tier({'npm_bench_scripts': '', 'vitest_bench_files': '2', 'has_bench': 'True'}) == 'adapter'
    assert tier({'npm_bench_scripts': '', 'vitest_bench_files': '0', 'has_bench': 'True'}) == 'tree'
    main(*sys.argv[1:4])
