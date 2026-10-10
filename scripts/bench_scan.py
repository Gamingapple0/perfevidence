"""Flag repos that ship benchmarks: bench files/dirs in the tree, or a `bench*` npm script.
Usage: bench_scan.py TREES_DIR > bench_repos.csv  (TREES_DIR holds owner_repo/ blobless clones + owner_repo.files)"""
import csv, json, re, subprocess, sys
from pathlib import Path

# "bench" must be its own token: excludes workbench, harmbench, benchByteIndex.
BENCH_FILE = re.compile(r'(^|/)(benchmarks?|bench|perf)/|(^|/)([^/]*[._-])?bench(mark)?s?([._-][^/]*)?\.(m?[jt]sx?)$', re.I)
BENCH_SCRIPT = re.compile(r'(^|[:_-])bench(mark)?s?($|[:_-])', re.I)
SKIP = re.compile(r'(^|/)(node_modules|vendor|third_party|dist)/')

def npm_bench_scripts(clone, pkgs):
    out = []
    for p in pkgs:
        r = subprocess.run(['git', '-C', str(clone), 'show', f'HEAD:{p}'], capture_output=True, text=True)
        try:
            scripts = json.loads(r.stdout).get('scripts') or {}
        except (json.JSONDecodeError, AttributeError):
            continue
        out += [f'{p}:{k}' for k in scripts if BENCH_SCRIPT.search(k)]
    return out

def scan(trees):
    w = csv.writer(sys.stdout)
    w.writerow(['repo', 'bench_files', 'vitest_bench_files', 'npm_bench_scripts', 'has_bench', 'examples'])
    for f in sorted(trees.glob('*.files')):
        files = [x for x in f.read_text().splitlines() if not SKIP.search(x)]
        bench = [x for x in files if BENCH_FILE.search(x)]
        pkgs = [x for x in files if x.endswith('package.json') and x.count('/') <= 2]
        scripts = npm_bench_scripts(trees / f.stem, pkgs)
        w.writerow([f.stem.replace('_', '/', 1), len(bench), sum('.bench.' in x for x in bench), ';'.join(scripts), bool(bench or scripts), ';'.join(bench[:3])])

if __name__ == '__main__':
    assert BENCH_FILE.search('src/foo.bench.ts') and BENCH_FILE.search('benchmarks/a.js') and BENCH_FILE.search('src/micro-bench.js')
    assert not any(BENCH_FILE.search(x) for x in ['src/Workbench.tsx', 'src/harmbench.ts', 'lazy/benchByteJsonIndex.ts'])
    assert BENCH_SCRIPT.search('test:bench') and not BENCH_SCRIPT.search('watch:tsc-simulation-workbench')
    scan(Path(sys.argv[1]))
