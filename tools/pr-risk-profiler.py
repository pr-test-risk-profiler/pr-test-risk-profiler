import os
import subprocess
import yaml
from github import Github
import lizard

# --------------------------
# Config & Constants
# --------------------------
CRITICAL_MODULES_FILE = ".critical_modules.yml"
TESTMAP_FILE = ".testmap.yml"
DEFAULT_WEIGHTS = {
    "file_changed": 2,
    "lines_changed": 0.1,
    "critical_module": 15,
    "bug_commit": 3,
    "complexity_increase": 10,
    "test_file_penalty": -5
}

# --------------------------
# Helper Functions
# --------------------------

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    return {}

def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-status", "origin/main...HEAD"],
        capture_output=True, text=True
    )
    files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            status, path = line.split("\t", 1)
            files.append(path)
    return files

def get_lines_changed():
    result = subprocess.run(
        ["git", "diff", "--numstat", "origin/main...HEAD"],
        capture_output=True, text=True
    )
    added, deleted = 0, 0
    for line in result.stdout.strip().split("\n"):
        if line:
            a, d, _ = line.split("\t")
            added += int(a)
            deleted += int(d)
    return added, deleted

def count_bug_commits(file_path):
    result = subprocess.run(
        ["git", "log", "--follow", "--pretty=%s", "--", file_path],
        capture_output=True, text=True
    )
    keywords = ["fix", "bug", "issue", "hotfix"]
    return sum(1 for line in result.stdout.lower().split("\n") if any(k in line for k in keywords))

def get_complexity(file_path):
    try:
        analysis = lizard.analyze_file(file_path)
        avg_complexity = sum(func.cyclomatic_complexity for func in analysis.function_list) / max(1, len(analysis.function_list))
        return avg_complexity
    except Exception:
        return None

# --------------------------
# Main Risk Scoring
# --------------------------
def calculate_risk(changed_files, added, deleted, critical_modules):
    score = 0
    for f in changed_files:
        score += DEFAULT_WEIGHTS["file_changed"]

        # Lines changed
        total_lines = added + deleted
        score += total_lines * DEFAULT_WEIGHTS["lines_changed"]

        # Critical modules
        if any(f.startswith(cm) for cm in critical_modules):
            score += DEFAULT_WEIGHTS["critical_module"]

        # Bug history
        bug_commits = count_bug_commits(f)
        score += bug_commits * DEFAULT_WEIGHTS["bug_commit"]

        # Complexity change (optional in MVP)
        complexity = get_complexity(f)
        if complexity and complexity > 10:  # arbitrary threshold
            score += DEFAULT_WEIGHTS["complexity_increase"]

        # Test file penalty
        if "test" in f.lower():
            score += DEFAULT_WEIGHTS["test_file_penalty"]

    return max(0, min(100, score))

# --------------------------
# GitHub Comment Posting
# --------------------------
def get_github_context():
    # Get environment variables or fail with helpful message
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    # These are automatically set by GitHub Actions
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("This action must be run in a GitHub Actions environment")
    
    # Read the event payload
    with open(event_path, 'r') as f:
        import json
        event = json.load(f)
    
    # Extract PR info from the event
    try:
        pr_number = event['pull_request']['number']
        repo_name = event['repository']['full_name']
        return token, repo_name, pr_number
    except KeyError as e:
        raise ValueError(f"Missing required information in GitHub event: {e}")

def post_github_comment(body):
    token, repo_name, pr_number = get_github_context()
    gh = Github(token)
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)

# --------------------------
# Main Entry
# --------------------------
if __name__ == "__main__":
    critical_modules = load_yaml(CRITICAL_MODULES_FILE).get("critical_modules", [])
    testmap = load_yaml(TESTMAP_FILE).get("mappings", {})

    changed_files = get_changed_files()
    added, deleted = get_lines_changed()

    risk_score = calculate_risk(changed_files, added, deleted, critical_modules)

    # Risk level
    if risk_score <= 30:
        risk_level = "Low"
    elif risk_score <= 70:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # Suggested tests
    suggested_tests = set()
    for f in changed_files:
        for pattern, tests in testmap.items():
            if f.startswith(pattern):
                suggested_tests.update(tests)

    report = f"""
🛡 **PR Test Risk Profiler**
Risk Score: **{risk_score}/100** → **{risk_level} Risk**

**Changed Files:**
**Suggested Tests:** {", ".join(suggested_tests) if suggested_tests else "No mapping found"}

---

_This analysis is automated by PR Test Risk Profiler._
"""

    post_github_comment(report)
    print(report)