#!/usr/bin/env bash
# 安装 ai-hotspot-pipeline 到各 Agent skills 目录
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="copy"
TARGETS=()

usage() {
  cat <<'U'
Usage: bash install.sh [--symlink|--copy] [--grok] [--claude] [--codex] [--all]
  default: --copy --all
U
}

for arg in "$@"; do
  case "$arg" in
    --symlink) MODE=symlink ;;
    --copy) MODE=copy ;;
    --grok) TARGETS+=("$HOME/.grok/skills/ai-hotspot-pipeline") ;;
    --claude) TARGETS+=("$HOME/.claude/skills/ai-hotspot-pipeline") ;;
    --codex) TARGETS+=("$HOME/.codex/skills/ai-hotspot-pipeline") ;;
    --all) TARGETS+=("$HOME/.grok/skills/ai-hotspot-pipeline" "$HOME/.claude/skills/ai-hotspot-pipeline" "$HOME/.codex/skills/ai-hotspot-pipeline") ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown: $arg"; usage; exit 1 ;;
  esac
done
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS+=("$HOME/.grok/skills/ai-hotspot-pipeline" "$HOME/.claude/skills/ai-hotspot-pipeline" "$HOME/.codex/skills/ai-hotspot-pipeline")
fi

for dst in "${TARGETS[@]}"; do
  mkdir -p "$(dirname "$dst")"
  rm -rf "$dst"
  if [[ "$MODE" == "symlink" ]]; then
    ln -s "$SCRIPT_DIR" "$dst"
    echo "✓ symlink $dst → $SCRIPT_DIR"
  else
    mkdir -p "$dst"
    # skill-compatible layout: SKILL.md + scripts/config as needed
    cp -R "$SCRIPT_DIR/SKILL.md" "$dst/"
    cp -R "$SCRIPT_DIR/scripts" "$dst/" 2>/dev/null || true
    cp -R "$SCRIPT_DIR/config" "$dst/" 2>/dev/null || true
    cp -R "$SCRIPT_DIR/references" "$dst/" 2>/dev/null || true
    cp -R "$SCRIPT_DIR/README.md" "$dst/" 2>/dev/null || true
    echo "✓ copied $dst"
  fi
done
echo ""
echo "Next:"
echo "  1. 安装并配置 TrendRadar: https://github.com/sansan0/TrendRadar"
echo "  2. export TRENDRADAR_ROOT=~/tools/TrendRadar"
echo "  3. cd 到内容工作区，说：/ai-hotspot-pipeline 或 跑热点流水线"
echo "  4. 或 bash scripts/run_pipeline.sh"
