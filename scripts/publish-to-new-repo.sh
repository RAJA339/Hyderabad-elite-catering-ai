#!/usr/bin/env bash
# Publish this folder as its own GitHub repository with a clean history.
# Usage: scripts/publish-to-new-repo.sh git@github.com:RAJA339/hyderabad-elite-catering-ai.git
set -euo pipefail
REMOTE="${1:?usage: $0 <new-repo-git-url>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
rsync -a --exclude node_modules --exclude .next --exclude __pycache__ --exclude .venv "$HERE/" "$TMP/"
cd "$TMP"
git init -q -b main
git add -A
git commit -q -m "feat: HEC-AI — Hyderabad Elite Catering AI platform (initial import)"
git remote add origin "$REMOTE"
git push -u origin main
echo "Published to $REMOTE"
