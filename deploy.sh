#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-hvac-ai-agent}"
GITHUB_USER="${GITHUB_USER:-}"

if ! command -v git >/dev/null 2>&1; then
  echo "Git is required." >&2
  exit 1
fi

if [ ! -d .git ]; then
  git init
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "Deploy HVAC AI prospecting agent"
fi
git branch -M main

if command -v gh >/dev/null 2>&1; then
  if gh repo view "$REPO_NAME" >/dev/null 2>&1; then
    echo "GitHub repository already exists."
  else
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
  fi
  git push -u origin main
  echo "GitHub push complete. In Render, create a Blueprint from this repository."
elif [ -n "$GITHUB_USER" ]; then
  REMOTE="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
  git remote remove origin >/dev/null 2>&1 || true
  git remote add origin "$REMOTE"
  git push -u origin main
  echo "GitHub push complete. In Render, create a Blueprint from $REMOTE"
else
  echo "Install GitHub CLI and run 'gh auth login', or set GITHUB_USER before running this script." >&2
  echo "Example: GITHUB_USER=yourusername ./deploy.sh $REPO_NAME" >&2
  exit 1
fi
