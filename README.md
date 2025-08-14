# pr-test-risk-profiler
Analyze pull requests and suggest tests based on changed files and risk score.

## Usage as a GitHub Action

Add to your workflow:

```yaml
name: PR Risk Analysis
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write  # Required to post comments

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Required for git history analysis
      
      - name: PR Test Risk Profiler
        uses: pr-test-risk-profiler/pr-test-risk-profiler@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
