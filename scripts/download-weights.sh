#!/bin/bash
# Downloads engine weights into the shared Hugging Face cache (~/.cache/huggingface).
#   scripts/download-weights.sh small   Laya, Decider 0.8B, Kev 0.8B          (~6 GB)
#   scripts/download-weights.sh all     every local engine                    (~37 GB)
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-small}"
SMALL=(convaiinnovations/laya Mapika/decider-0.8b jaredpalmer/kev-0.8b Qwen/Qwen3.5-0.8B-Base)
LARGE=(Mapika/decider-2b Mapika/decider-4b jaredpalmer/kev-4b Qwen/Qwen3.5-4B-Base Qwen/Qwen3.5-4B)
case "$PROFILE" in
  small) REPOS=("${SMALL[@]}") ;;
  all) REPOS=("${SMALL[@]}" "${LARGE[@]}") ;;
  *) echo "usage: $0 [small|all]"; exit 2 ;;
esac
HF=engines/laya/.venv/bin/hf
[ -x "$HF" ] || { echo "Run 'make setup' first."; exit 1; }
for repo in "${REPOS[@]}"; do
  echo "== $repo"
  for attempt in 1 2 3; do
    "$HF" download "$repo" --quiet >/dev/null && break
    [ "$attempt" = 3 ] && { echo "   could not download $repo"; exit 1; }
    echo "   retrying ($attempt)"; sleep 5
  done
done
echo "Weights ready ($PROFILE)."
