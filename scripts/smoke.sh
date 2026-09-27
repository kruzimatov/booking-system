#!/usr/bin/env bash
set -euo pipefail

base_url="${BASE_URL%/}"

check_json() {
  local path="$1"
  local expected="$2"
  local response
  response="$(curl --fail --silent --show-error "$base_url$path")"
  if [[ "$response" != *"$expected"* ]]; then
    printf 'Smoke check failed for %s: %s\n' "$path" "$response" >&2
    exit 1
  fi
  printf 'ok %s\n' "$path"
}

check_json "/api/v1/health" '"status":"ok"'
check_json "/api/v1/meta" '"timezone"'
check_json "/api/v1/services" '"name"'
