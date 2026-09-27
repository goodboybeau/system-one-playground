#!/bin/bash
# Checks this machine can run System One Playground. Exits non-zero on a hard failure.
set -u
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; FAILED=1; }
FAILED=0
echo "Checking your machine…"

[ "$(uname -s)" = "Darwin" ] && ok "macOS $(sw_vers -productVersion)" || fail "macOS is required (engines use Metal and macOS sandboxing)"
[ "$(uname -m)" = "arm64" ] && ok "Apple Silicon ($(sysctl -n machdep.cpu.brand_string 2>/dev/null))" || fail "Apple Silicon (arm64) is required"

if command -v uv >/dev/null; then ok "uv $(uv --version | awk '{print $2}')"; else fail "uv is missing: curl -LsSf https://astral.sh/uv/install.sh | sh"; fi
if command -v node >/dev/null; then
  major=$(node -p 'process.versions.node.split(".")[0]')
  [ "$major" -ge 20 ] && ok "Node $(node --version)" || fail "Node 20+ is required (found $(node --version))"
else
  fail "Node 20+ is missing: https://nodejs.org or brew install node"
fi
command -v sandbox-exec >/dev/null && ok "sandbox-exec available" || warn "sandbox-exec missing; run the lab with --no-sandbox"

mem_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if [ "$mem_gb" -ge 32 ]; then ok "${mem_gb} GB memory: every engine fits (one 4B model at a time)"
elif [ "$mem_gb" -ge 16 ]; then warn "${mem_gb} GB memory: small engines are fine; 4B models will be tight"
else warn "${mem_gb} GB memory: stick to Laya and the 0.8B models"; fi

free_gb=$(df -g "$HOME" | awk 'NR==2 {print $4}')
if [ "$free_gb" -ge 45 ]; then ok "${free_gb} GB free disk (all weights need ~37 GB)"
elif [ "$free_gb" -ge 8 ]; then warn "${free_gb} GB free disk: enough for the small engines (~6 GB), not all (~37 GB)"
else fail "${free_gb} GB free disk: the small engines alone need ~6 GB"; fi

[ "$FAILED" = 0 ] && echo "Ready." || { echo "Fix the ✗ items above, then run this again."; exit 1; }
