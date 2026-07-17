#!/usr/bin/env bash
set -euo pipefail

image="${1:-litellm/litellm:latest}"
output="${2:-vllm-service/litellm/image.json}"

mkdir -p "$(dirname "$output")"
docker image inspect "$image" --format '{{json .}}' \
  | jq '{
      image: .RepoTags[0],
      image_id: .Id,
      digest: (.RepoDigests[0] // null),
      created: .Created,
      recorded_at_utc: (now | todateiso8601)
    }' > "$output"

printf 'Recorded LiteLLM image metadata: %s\n' "$output"
