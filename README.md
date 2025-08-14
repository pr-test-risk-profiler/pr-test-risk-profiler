# pr-test-risk-profiler
Analyze pull requests and suggest tests based on changed files and risk score.

## Usage as a GitHub Action

Add to your workflow:

```yaml
jobs:
  pr-risk-profiler:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: PR Test Risk Profiler
        uses: pr-test-risk-profiler/pr-test-risk-profiler@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

### Required Environment Variables
- `GITHUB_TOKEN`: GitHub token for API access
- `GITHUB_REPO`: Repository name (e.g., owner/repo)
- `GITHUB_PR_NUMBER`: Pull request number

### Optional Config Files
- `.critical_modules.yml`: List of critical modules
- `.testmap.yml`: Mapping of files to tests

### Output
The action will post a comment on the PR with the risk score and suggested tests.
