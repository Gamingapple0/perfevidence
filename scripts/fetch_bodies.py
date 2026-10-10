"""Fetch title/body/state and base/head SHAs for every sampled PR from the GitHub API.
Usage: GITHUB_TOKEN=<fine-grained read-only> python fetch_bodies.py data/sample.csv data/sample_prs.jsonl
Re-running skips PRs already in the output file."""
import csv, json, os, sys, time, urllib.request
from pathlib import Path

def get(url, token):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}',
                                               'Accept': 'application/vnd.github+json',
                                               'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main(sample_csv, out):
    token = os.environ['GITHUB_TOKEN']
    done = {json.loads(l)['html_url'] for l in Path(out).read_text().splitlines()} if Path(out).exists() else set()
    with open(out, 'a') as f:
        for row in csv.DictReader(open(sample_csv)):
            if row['html_url'] in done:
                continue
            pr = get(f"https://api.github.com/repos/{row['repo']}/pulls/{row['number']}", token)
            f.write(json.dumps({**row,
                'title': pr['title'], 'body': pr['body'], 'state': pr['state'],
                'created_at': pr['created_at'], 'merged_at': pr['merged_at'], 'user': pr['user']['login'],
                # SHAs drive the base/head benchmark runs in week 3
                'base_sha': pr['base']['sha'], 'head_sha': pr['head']['sha'],
            }) + '\n')
            f.flush()
            time.sleep(0.2)
    print(f'{sum(1 for _ in open(out))} PRs in {out}')

if __name__ == '__main__':
    main(*sys.argv[1:3])
