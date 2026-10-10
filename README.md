# perfevidence

Checks performance claims in AI-agent pull requests. Finds claims like "2x faster" in a PR description, runs the repo's own benchmarks that reach the changed code on base and head, and posts a verdict with numbers.

Status: week 1, building the evaluation sample. The GitHub Action does not exist yet.

## Evaluation sample (reproduce)

Inputs, pinned:
- Purdue replication package `PurdueDualityLab/EMSE-perf-pr-study` at `64432e0b6ed7791bbfa929c6c183fc76c75b5d58`, file `analysis/classification_labels/rq1_labels.csv`
- AIDev `hao-li/AIDev` on Hugging Face, file `all_repository.parquet` (repo language)

```sh
pip install pandas pyarrow
python scripts/ts_prs.py rq1_labels.csv all_repository.parquet data/ts_prs.csv

# blobless clone of each TS repo, file list at default-branch HEAD
mkdir trees && cut -d, -f3 data/ts_prs.csv | tail -n +2 | sort -u | while read r; do
  d=trees/$(echo $r | tr / _); git clone -q --filter=blob:none --no-checkout --depth 1 https://github.com/$r.git $d
  git -C $d ls-tree -r --name-only HEAD > $d.files; done
python scripts/bench_scan.py trees > data/bench_repos.csv

python scripts/build_sample.py data/ts_prs.csv data/bench_repos.csv data/sample.csv   # seed 20261010, cap 3 per repo
GITHUB_TOKEN=... python scripts/fetch_bodies.py data/sample.csv data/sample_prs.jsonl
```

Bench tiers: `adapter` = repo has a `bench`/`benchmark` npm script or vitest `*.bench.*` files (what the Action will run); `tree` = only bench-like files or folders. Both are upper bounds: detection runs on today's default branch, not the PR's base commit.

## Claim extraction

`src/claims.py` finds performance claims in a PR's title and description and parses the claimed gain ratio (`r_c`, e.g. 2.0 for "2x faster", 1.67 for "40% less memory"). Dimension detection is the deterministic extractor from the Purdue study, vendored unchanged in `src/metric_patterns.py` and `src/purdue_extract.py` (MIT, source commit in the file headers). Self-check: `cd src && python claims.py`.

## License

MIT
