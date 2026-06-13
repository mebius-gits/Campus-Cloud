from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.multi_model import build_gateway_routes, load_model_instances


def _write_env(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "API_HOST=127.0.0.1",
                "API_KEY=test-key",
                "HF_CACHE_DIR=/tmp/nonexistent-hf-cache",
                "TRUST_REMOTE_CODE=false",
                "ENABLE_PREFIX_CACHING=false",
                "ALLOWED_LOCAL_MEDIA_PATH=",
            ]
        ),
        encoding="utf-8",
    )


def test_build_gateway_routes_loads_admission_and_capabilities(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    models_path = tmp_path / "models.json"
    _write_env(env_path)
    models_path.write_text(
        json.dumps(
            [
                {
                    "alias": "qwen",
                    "model_name": "./AImodels/Qwen3-14B-FP8",
                    "api_port": 8104,
                    "max_num_seqs": 24,
                    "scheduling_policy": "priority",
                    "enable_chunked_prefill": True,
                    "long_prefill_token_threshold": 4096,
                    "gateway_max_inflight": 6,
                    "gateway_queue_timeout": 12.5,
                    "capabilities": {
                        "reasoning": True,
                        "priority_scheduling": True,
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    instances = load_model_instances(base_env_file=env_path, models_json_file=models_path)
    routes = build_gateway_routes(instances, default_max_inflight=16, default_queue_timeout=30)

    args = instances[0].settings.build_vllm_serve_args()
    route = routes["qwen"]
    assert route.max_inflight == 6
    assert route.queue_timeout == 12.5
    assert route.scheduling_policy == "priority"
    assert route.capabilities["reasoning"] is True
    assert route.capabilities["priority_scheduling"] is True
    assert "--enable-chunked-prefill" in args
    assert "--long-prefill-token-threshold" in args
    assert "--max-num-partial-prefills" not in args
    assert "--max-long-partial-prefills" not in args


def test_capabilities_must_be_an_object(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    models_path = tmp_path / "models.json"
    _write_env(env_path)
    models_path.write_text(
        json.dumps(
            [
                {
                    "alias": "bad",
                    "model_name": "bad-model",
                    "api_port": 8105,
                    "capabilities": ["not", "an", "object"],
                }
            ]
        ),
        encoding="utf-8",
    )

    instances = load_model_instances(base_env_file=env_path, models_json_file=models_path)
    with pytest.raises(ValueError, match="capabilities"):
        build_gateway_routes(instances)
