#!/usr/bin/env bash
# Starts the spec-workflow approval dashboard (http://localhost:5000 by default).
#
# Usage: scripts/spec_dashboard.sh [--port N] [--no-open]
#
# The package version is read from .mcp.json so the dashboard always matches the MCP server Claude Code runs.
# Only one dashboard may run at a time; if one is already up on the port, this just opens it in the browser.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

package="$(node -e '
const args = require(process.argv[1]).mcpServers["spec-workflow"].args;
const pkg = args.find((a) => a.startsWith("@pimzino/spec-workflow-mcp@"));
if (!pkg) { console.error("no pinned @pimzino/spec-workflow-mcp in .mcp.json"); process.exit(1); }
console.log(pkg);
' "$root/.mcp.json")"

port=5000
open_browser=1
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[i]}" in
    --port) port="${args[i + 1]:-}" ;;
    --port=*) port="${args[i]#--port=}" ;;
    --no-open) open_browser=0 ;;
  esac
done

url="http://localhost:$port"

if curl -fs -o /dev/null --max-time 2 "$url"; then
  echo "Dashboard already running at $url"
  if ((open_browser)) && command -v xdg-open >/dev/null; then
    xdg-open "$url" >/dev/null 2>&1 &
  fi
  exit 0
fi

echo "Starting $package dashboard at $url (Ctrl+C to stop)"
cd "$root"
exec npx -y "$package" --dashboard "$@"
