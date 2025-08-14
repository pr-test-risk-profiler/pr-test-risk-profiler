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
    # Print debug info about the environment
    print("Debug: Getting changed files")
    print(f"PWD: {os.getcwd()}")
    print(f"List directory: {os.listdir('.')}")
    
    # Configure git to trust the workspace
    subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', '*'], capture_output=True)
    
    # Try to get PR information from environment
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    print(f"GITHUB_EVENT_PATH: {event_path}")
    
    if event_path and os.path.exists(event_path):
        try:
            with open(event_path, 'r') as f:
                import json
                event = json.load(f)
                print(f"GitHub Event: {json.dumps(event, indent=2)}")
                
                # Get the PR number from the event
                pr_number = event['pull_request']['number']
                print(f"PR Number: {pr_number}")
                
                # Configure the repository
                subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'], capture_output=True)
                
                # Fetch PR refs
                fetch_result = subprocess.run(
                    ['git', 'fetch', 'origin', f'pull/{pr_number}/head:pr-head'],
                    capture_output=True,
                    text=True
                )
                print(f"Fetch result: {fetch_result.stdout}\n{fetch_result.stderr}")
                
                # Get changed files using GitHub API
                if 'pull_request' in event:
                    files = []
                    for file in event['pull_request']['files']:
                        files.append(file['filename'])
                    if files:
                        print(f"Found {len(files)} changed files from GitHub API")
                        return files
                
                # If GitHub API didn't work, try git commands
                print("\nTrying git commands...")
                # Try to get changes between PR head and base
                result = subprocess.run(
                    ['git', 'diff', '--name-only', 'origin/main...pr-head'],
                    capture_output=True,
                    text=True
                )
                
        except Exception as e:
            print(f"Warning: Failed to get PR diff: {e}")
            # Fallback to git status
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True
            )
    else:
        print("No event path found, using git status")
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
    
    print(f"\nCommand output:\n{result.stdout}")
    print(f"Command stderr:\n{result.stderr}")
    
    files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                # Handle git status --porcelain format
                if result.args[1] == '--porcelain':
                    if line[3:]:  # Skip the status codes
                        files.append(line[3:].strip())
                else:
                    # Handle git diff format
                    parts = line.split(None, 1)  # Split on whitespace
                    if len(parts) > 1:
                        files.append(parts[-1].strip())
                    else:
                        files.append(parts[0].strip())  # For --name-only format
            except Exception as e:
                print(f"Warning: Failed to parse line '{line}': {e}")
                continue
    
    # Debug output
    print(f"\nFound {len(files)} changed files: {files}")
    return files
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
        # Fallback to environment variables if event path is not available
        repo = os.environ.get("GITHUB_REPOSITORY")
        pr_num = os.environ.get("GITHUB_REF", "").split('/')[-2]
        if repo and pr_num and pr_num.isdigit():
            return token, repo, int(pr_num)
        raise ValueError("This action must be run in a GitHub Actions environment")
    
    # Read the event payload
    try:
        with open(event_path, 'r') as f:
            import json
            event = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to read GitHub event file: {e}")
    
    # Extract PR info from the event
    try:
        if 'pull_request' in event:
            pr_number = event['pull_request']['number']
            repo_name = event['repository']['full_name']
        else:
            # Fallback to environment variables
            repo_name = os.environ.get("GITHUB_REPOSITORY")
            ref = os.environ.get("GITHUB_REF", "")
            pr_number = ref.split('/')[-2] if '/pull/' in ref else None
            
            if not (repo_name and pr_number and pr_number.isdigit()):
                raise ValueError("Could not determine PR number from environment")
            pr_number = int(pr_number)
            
        return token, repo_name, pr_number
    except Exception as e:
        raise ValueError(f"Failed to get PR context: {e}")

def post_github_comment(body):
    try:
        token, repo_name, pr_number = get_github_context()
        gh = Github(token)
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # First try to post the comment
        try:
            pr.create_issue_comment(body)
        except Exception as e:
            # If comment creation fails, print the report to stdout
            print("Failed to post comment to PR. Error:", str(e))
            print("\nReport content:")
            print(body)
    except Exception as e:
        # If we can't even get the context, just print everything
        print("Failed to interact with GitHub API. Error:", str(e))
        print("\nReport content:")
        print(body)

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

    # Build the changed files section
    changed_files_text = ""
    if changed_files:
        for f in changed_files:
            changed_files_text += f"- {f}\n"
    else:
        changed_files_text = "No files changed\n"

    # Build the suggested tests section
    suggested_tests_text = ", ".join(suggested_tests) if suggested_tests else "No mapping found"

    report = f"""
🛡 **PR Test Risk Profiler**
Risk Score: **{risk_score}/100** → **{risk_level} Risk**

**Changed Files:**
{changed_files_text}
**Suggested Tests:** 
{suggested_tests_text}

---

_This analysis is automated by PR Test Risk Profiler._
"""

    post_github_comment(report)
    print(report)