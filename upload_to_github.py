"""
GitHub Upload Utility for Cafe POS Backend & Dashboard
Uploads the project to a GitHub repository using a GitHub Personal Access Token (PAT).
"""

import os
import sys
import json
import time
import base64
import urllib.request
import urllib.error
import argparse

EXCLUDED_DIRS = {'.pytest_cache', '__pycache__', '.git', '.idea', '.vscode'}
EXCLUDED_EXTENSIONS = {'.pyc', '.pyo', '.pyd'}
EXCLUDED_FILES = {'cafe_pos.db-shm', 'cafe_pos.db-wal', 'temp_script.js'}

def github_request(url, token, data=None, method=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Cafe-POS-Uploader",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
        except Exception:
            err_json = {"message": err_msg}
        return e.code, err_json

def get_authenticated_user(token):
    status, res = github_request("https://api.github.com/user", token)
    if status != 200:
        raise RuntimeError(f"Authentication failed ({status}): {res.get('message', 'Invalid token')}")
    return res["login"]

def ensure_repository(token, owner, repo_name, private=False):
    status, res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}", token)
    if status == 200:
        print(f"Repository '{owner}/{repo_name}' already exists.")
        return res
    elif status == 404:
        print(f"Creating new repository '{repo_name}' on GitHub (private={private})...")
        payload = {
            "name": repo_name,
            "private": private,
            "description": "Velvet Roast Cafe POS, Kitchen Display System & Real-Time Dashboard",
            "auto_init": True
        }
        create_status, create_res = github_request("https://api.github.com/user/repos", token, data=payload, method="POST")
        if create_status not in (200, 201):
            raise RuntimeError(f"Failed to create repo: {create_res.get('message', '')}")
        print(f"Repository '{owner}/{repo_name}' created successfully on GitHub.")
        time.sleep(2)  # Wait for GitHub git repo initialization
        return create_res
    else:
        raise RuntimeError(f"Error checking repo ({status}): {res.get('message', '')}")

def collect_project_files(project_dir):
    files_to_upload = []
    for root, dirs, files in os.walk(project_dir):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            if f in EXCLUDED_FILES:
                continue
            ext = os.path.splitext(f)[1]
            if ext in EXCLUDED_EXTENSIONS:
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
            files_to_upload.append((full_path, rel_path))
    return files_to_upload

def upload_project(token, repo_name, private=False, branch="main", commit_message="Initial commit: Velvet Roast Cafe POS System"):
    owner = get_authenticated_user(token)
    print(f"Authenticated as GitHub user: @{owner}")
    
    ensure_repository(token, owner, repo_name, private=private)
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    files = collect_project_files(project_dir)
    print(f"Found {len(files)} files to upload from '{project_dir}'.")
    
    tree_items = []
    for full_path, rel_path in files:
        with open(full_path, "rb") as f:
            raw_bytes = f.read()
        b64_content = base64.b64encode(raw_bytes).decode("ascii")
        
        # Create blob
        blob_payload = {"content": b64_content, "encoding": "base64"}
        status, blob_res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/blobs", token, data=blob_payload, method="POST")
        if status not in (200, 201):
            print(f"Failed to create blob for {rel_path}: {blob_res}")
            continue
            
        tree_items.append({
            "path": rel_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_res["sha"]
        })
        print(f"  + Uploaded: {rel_path}")
        
    # Check if branch already exists
    parent_commits = []
    ref_status, ref_data = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/refs/heads/{branch}", token)
    if ref_status == 200:
        parent_commits.append(ref_data["object"]["sha"])
        base_tree = ref_data["object"]["sha"]
    else:
        base_tree = None

    # Create Tree
    tree_payload = {"tree": tree_items}
    tree_status, tree_res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/trees", token, data=tree_payload, method="POST")
    if tree_status not in (200, 201):
        raise RuntimeError(f"Failed to create tree: {tree_res}")
    tree_sha = tree_res["sha"]

    # Create Commit
    commit_payload = {
        "message": commit_message,
        "tree": tree_sha,
        "parents": parent_commits
    }
    commit_status, commit_res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/commits", token, data=commit_payload, method="POST")
    if commit_status not in (200, 201):
        raise RuntimeError(f"Failed to create commit: {commit_res}")
    commit_sha = commit_res["sha"]

    # Update or Create Ref
    if parent_commits:
        update_status, update_res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/refs/heads/{branch}", token, data={"sha": commit_sha, "force": True}, method="PATCH")
    else:
        update_status, update_res = github_request(f"https://api.github.com/repos/{owner}/{repo_name}/git/refs", token, data={"ref": f"refs/heads/{branch}", "sha": commit_sha}, method="POST")

    if update_status not in (200, 201):
        raise RuntimeError(f"Failed to update branch ref: {update_res}")

    repo_url = f"https://github.com/{owner}/{repo_name}"
    print(f"\nSuccessfully uploaded to: {repo_url}")
    return repo_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload project to GitHub via Personal Access Token")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token (classic or fine-grained)")
    parser.add_argument("--repo", default="cafe-pos-dashboard", help="Repository name (default: cafe-pos-dashboard)")
    parser.add_argument("--private", action="store_true", help="Set repository to private")
    parser.add_argument("--branch", default="main", help="Target branch name (default: main)")
    parser.add_argument("--message", default="Initial commit: Velvet Roast Cafe POS System", help="Commit message")
    
    args = parser.parse_args()
    try:
        url = upload_project(
            token=args.token.strip(),
            repo_name=args.repo.strip(),
            private=args.private,
            branch=args.branch,
            commit_message=args.message
        )
        print(f"DONE: {url}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
