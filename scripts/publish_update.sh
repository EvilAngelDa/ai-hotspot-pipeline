#!/usr/bin/env bash
# 从本仓库 push 更新到 GitHub（维护者用）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MSG="${1:-chore: update ai-hotspot-pipeline}"
git status -sb
git add -A
if git diff --cached --quiet; then
  echo "无变更可提交"
  exit 0
fi
git commit -m "$MSG"
git push origin HEAD
echo "已推送: https://github.com/EvilAngelDa/ai-hotspot-pipeline"
