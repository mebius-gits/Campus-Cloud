# LiteLLM staging (Phase 2)

This directory contains the static policy only.  The deployment list is
always generated from `../models.json`, so alias, served model name, vLLM port
and RPM cannot drift between the launcher and LiteLLM.

## Start staging

On the multi-model host, start the host vLLM processes first:

```bash
cd vllm-service
./start_multi_model_cluster.sh
./.venv/bin/python tools/generate_litellm_config.py --mode integration
cd ..
./scripts/record-litellm-image.sh
```

Copy the variables in `.env.example` into the root deployment `.env` and
replace every placeholder. `VLLM_UPSTREAM_API_KEY` must match the `API_KEY`
that the two vLLM instances use. These keys are for isolated staging only;
they are not Campus user keys and must never be reused in production.

```bash
docker compose --profile ai-api up -d litellm
docker compose --profile ai-api ps litellm
```

The service deliberately has no `DATABASE_URL`, no LiteLLM PostgreSQL role,
and no Virtual Key in this phase. Its host-network listener on `:4000` must be
restricted by the host firewall to the Campus backend, monitoring and admin
sources. Do not publish `8103` or `8104`.

For a host using UFW, add the explicit allow rules for the real private source
CIDRs first, then deny all other sources. Replace the placeholders; do not use
`0.0.0.0/0`.

```bash
sudo ufw allow from <campus-backend-private-cidr> to any port 4000 proto tcp
sudo ufw allow from <monitoring-private-cidr> to any port 4000 proto tcp
sudo ufw allow from <admin-vpn-cidr> to any port 4000 proto tcp
sudo ufw deny 4000/tcp
```

Use equivalent ordered rules when the host uses nftables, firewalld, or a
cloud security group. This is intentionally an operator step: the repository
cannot infer the permitted private CIDRs safely.

## Staging checks

Use the isolated staging key, never a `ccai_*` credential:

```bash
curl -fsS http://127.0.0.1:4000/health/liveliness
curl -fsS http://127.0.0.1:4000/health/readiness
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  http://127.0.0.1:4000/health
curl -fsS -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  http://127.0.0.1:4000/v1/models
```

`/health` invokes upstream checks, so use it for a deliberate smoke test, not
as a high-frequency container probe. The Compose health check only calls
`/health/liveliness`.

After exporting the isolated `LITELLM_MASTER_KEY`, use the repeatable full
check below. It proves both deployments are healthy, the `/v1/models` allowlist
has not drifted, and the backend container can reach the host gateway.

```bash
./scripts/verify-litellm-staging.sh
```

To prove a normal Compose startup is unchanged, run `docker compose config`
and `docker compose up -d` without `--profile ai-api`; `litellm` must remain
absent. To stop only the staging gateway, run
`docker compose --profile ai-api stop litellm`.
