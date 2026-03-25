#!/usr/bin/env bash
# Patches Orchestrate Docker containers to inject environment variables
# needed by MCP toolkits (e.g. LINEAR_API_KEY for the Linear MCP server).
#
# Run this after `orchestrate server start`:
#   ./scripts/patch_containers.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/../.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  echo "Usage: $0 [path/to/.env]"
  exit 1
fi

# Load LINEAR_API_KEY from .env
LINEAR_API_KEY=$(grep '^LINEAR_API_KEY=' "$ENV_FILE" | cut -d'=' -f2-)
if [[ -z "$LINEAR_API_KEY" ]]; then
  echo "ERROR: LINEAR_API_KEY not found in $ENV_FILE"
  exit 1
fi

# Containers that need the key (tools-runtime runs npx linear-mcp-server)
CONTAINERS=("dev-edition-tools-runtime-1" "dev-edition-tools-runtime-manager-1")

for CONTAINER in "${CONTAINERS[@]}"; do
  # Check if already set
  EXISTING=$(docker exec "$CONTAINER" env 2>/dev/null | grep '^LINEAR_API_KEY=' | cut -d'=' -f2- || true)
  if [[ "$EXISTING" == "$LINEAR_API_KEY" ]]; then
    echo "$CONTAINER: LINEAR_API_KEY already set, skipping"
    continue
  fi

  echo "$CONTAINER: injecting LINEAR_API_KEY..."

  # Get current config
  IMAGE=$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')
  NETWORK=$(docker inspect "$CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')
  PORTS=$(docker inspect "$CONTAINER" --format '{{range $p,$c := .HostConfig.PortBindings}}{{$p}}={{(index $c 0).HostPort}}{{end}}')
  RESTART=$(docker inspect "$CONTAINER" --format '{{.HostConfig.RestartPolicy.Name}}')

  # Build env flags from existing env vars
  ENV_FLAGS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && ENV_FLAGS+=(-e "$line")
  done < <(docker inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed '/^$/d')
  ENV_FLAGS+=(-e "LINEAR_API_KEY=$LINEAR_API_KEY")

  # Build volume flags
  VOL_FLAGS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && VOL_FLAGS+=(-v "$line")
  done < <(docker inspect "$CONTAINER" --format '{{range .HostConfig.Binds}}{{println .}}{{end}}' | sed '/^$/d')

  # Get network aliases
  ALIASES=()
  while IFS= read -r alias; do
    # Skip container ID and full container name aliases
    if [[ -n "$alias" && "$alias" != "$CONTAINER" && ${#alias} -lt 20 ]]; then
      ALIASES+=(--network-alias "$alias")
    fi
  done < <(docker inspect "$CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{range $v.Aliases}}{{println .}}{{end}}{{end}}')

  # Parse port mapping
  PORT_FLAGS=()
  if [[ -n "$PORTS" ]]; then
    CONTAINER_PORT=$(echo "$PORTS" | cut -d'=' -f1)
    HOST_PORT=$(echo "$PORTS" | cut -d'=' -f2)
    PORT_FLAGS+=(-p "$HOST_PORT:${CONTAINER_PORT%/*}")
  fi

  # Stop, remove, recreate
  docker stop "$CONTAINER" >/dev/null 2>&1
  docker rm "$CONTAINER" >/dev/null 2>&1
  docker run -d \
    --name "$CONTAINER" \
    --network "$NETWORK" \
    "${ALIASES[@]}" \
    "${PORT_FLAGS[@]}" \
    --restart "$RESTART" \
    "${VOL_FLAGS[@]}" \
    "${ENV_FLAGS[@]}" \
    "$IMAGE" >/dev/null 2>&1

  echo "$CONTAINER: patched successfully"
done

echo "Done. Verify with: docker exec dev-edition-tools-runtime-1 env | grep LINEAR"
