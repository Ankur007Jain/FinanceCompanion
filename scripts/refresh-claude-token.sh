#!/bin/zsh
# Generates a fresh Claude CI token and pushes it to GitHub Actions secrets.
# Run manually, or let launchd run it every 25 days automatically.

set -euo pipefail

REPO="Ankur007Jain/FinanceCompanion"
CLAUDE="/Users/home/Library/Application Support/Claude/claude-code"
CLAUDE_BIN="$(ls -d "$CLAUDE"/*/claude.app/Contents/MacOS/claude 2>/dev/null | sort -V | tail -1)"

if [[ -z "$CLAUDE_BIN" ]]; then
  echo "Claude CLI not found" >&2
  exit 1
fi

TOKEN=$("$CLAUDE_BIN" setup-token 2>/dev/null | grep -o '[A-Za-z0-9_\-\.]\{20,\}' | tail -1)

if [[ -z "$TOKEN" ]]; then
  echo "setup-token produced no output — may need browser auth. Run manually:" >&2
  echo "  source ~/.zshrc && claude setup-token" >&2
  exit 1
fi

echo "$TOKEN" | gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo "$REPO"
echo "$(date): CLAUDE_CODE_OAUTH_TOKEN refreshed for $REPO"
