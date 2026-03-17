from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.recommendation import DeviceNode, RecommendationRequest
from app.services.backend_nodes_service import summarize_device_nodes
from app.services.catalog_service import (
    TemplateCatalog,
    TemplateItem,
    build_catalog_prompt_bundle,
    catalog_lookup,
    find_explicit_template_matches,
    suggest_support_templates,
)


async def generate_ai_plan(
    request: RecommendationRequest,
    nodes: list[DeviceNode],
    template_catalog: TemplateCatalog,
) -> dict[str, Any]:
    if not settings.vllm_model_name:
        raise HTTPException(status_code=503, detail="VLLM_MODEL_NAME is required for AI planning.")

    prompt_bundle = build_catalog_prompt_bundle(
        template_catalog,
        request.goal,
        request.top_k,
        needs_public_web=request.needs_public_web,
        needs_database=request.needs_database,
    )
    user_context = {
        "goal": request.goal,
        "role": request.role,
        "course_context": request.course_context,
        "budget_mode": request.budget_mode,
    }
    plan_schema = {
        "summary": "Traditional Chinese summary",
        "workload_profile": "string",
        "recommended_templates": [
            {"slug": "template-slug", "name": "template-name", "why": "Traditional Chinese reason"}
        ],
        "possible_needed_templates": [
            {"slug": "template-slug", "name": "template-name", "why": "Traditional Chinese reason"}
        ],
        "machines": [
            {
                "name": "string",
                "purpose": "Traditional Chinese short phrase",
                "template_slug": "string",
                "deployment_type": "lxc|vm",
                "cpu": "integer",
                "memory_mb": "integer",
                "disk_gb": "integer",
                "assigned_node": "node-name-or-null",
                "why": "Traditional Chinese reason",
            }
        ],
        "overall_config": {
            "deployment_strategy": "Traditional Chinese short sentence",
            "machine_count": "integer",
            "total_cpu": "integer",
            "total_memory_mb": "integer",
            "total_disk_gb": "integer",
        },
        "decision_factors": ["Traditional Chinese short bullet"],
        "upgrade_when": "Traditional Chinese upgrade timing",
    }

    prompt = (
        "You are an infrastructure planning AI for a campus cloud platform.\n"
        "You must directly produce a deployment recommendation in JSON.\n"
        "Use only templates from the provided catalog. Do not invent templates.\n"
        "All natural-language fields must be written in Traditional Chinese used in Taiwan.\n"
        "Do not use Simplified Chinese. Return valid JSON only.\n"
        "Infer the likely workload, support services, and scaling needs from the user goal, node capacity, and template catalog.\n"
        "recommended_templates should contain the main templates to deploy first.\n"
        "possible_needed_templates should contain likely support templates such as database, proxy, storage, or expansion-related services.\n"
        "Use template default_resources as the baseline, then adjust them for the workload you infer.\n"
        "If the user clearly names a tool and a matching template exists, prefer it unless there is a concrete capacity or compatibility reason not to.\n"
        "Keep decision_factors short and useful.\n"
        f"Output schema: {json.dumps(plan_schema, ensure_ascii=False)}\n"
        f"User context: {json.dumps(user_context, ensure_ascii=False)}\n"
        f"Node capacity summary: {json.dumps(summarize_device_nodes(nodes), ensure_ascii=False)}\n"
        f"Template analysis bundle: {json.dumps(prompt_bundle, ensure_ascii=False)}\n"
        "If capacity is insufficient, reflect that in summary, machine why, overall_config.deployment_strategy, or upgrade_when."
    )

    payload = {
        "model": settings.vllm_model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1100,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.vllm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.vllm_timeout) as client:
            response = await client.post(
                f"{settings.vllm_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return json.loads(data["choices"][0]["message"]["content"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI planning failed: {exc}") from exc


def normalize_ai_result(
    ai_result: dict[str, Any],
    request: RecommendationRequest,
    nodes: list[DeviceNode],
    template_catalog: TemplateCatalog,
) -> dict[str, Any]:
    lookup = catalog_lookup(template_catalog)
    explicit_matches = find_explicit_template_matches(template_catalog, request.goal)
    machines: list[dict[str, Any]] = []
    recommended_templates: list[dict[str, Any]] = []
    possible_needed_templates: list[dict[str, Any]] = []
    decision_factors = [
        str(item).strip()
        for item in list(ai_result.get("decision_factors") or [])
        if str(item).strip()
    ]

    for item in list(ai_result.get("recommended_templates") or []):
        normalized = _normalize_template_choice(item, lookup)
        if normalized and not any(existing["slug"] == normalized["slug"] for existing in recommended_templates):
            recommended_templates.append(normalized)

    for item in list(ai_result.get("possible_needed_templates") or []):
        normalized = _normalize_template_choice(item, lookup, fallback_why="AI 判斷這是後續擴充或公開服務常見的支援模板。")
        if not normalized:
            continue
        if any(existing["slug"] == normalized["slug"] for existing in recommended_templates):
            continue
        if any(existing["slug"] == normalized["slug"] for existing in possible_needed_templates):
            continue
        possible_needed_templates.append(normalized)

    for machine in list(ai_result.get("machines") or []):
        slug = str(machine.get("template_slug") or "").strip().lower()
        template = lookup.get(slug)
        if not template:
            continue
        machines.append(_normalize_machine(machine, template))

    _promote_explicit_templates(
        recommended_templates,
        possible_needed_templates,
        explicit_matches,
    )
    _align_machine_templates_with_explicit_matches(machines, explicit_matches, lookup)

    if not recommended_templates:
        for machine in machines:
            template = lookup.get(str(machine.get("template_slug") or "").strip().lower())
            if not template:
                continue
            if any(existing["slug"] == template.slug for existing in recommended_templates):
                continue
            recommended_templates.append(
                {
                    "slug": template.slug,
                    "name": template.name,
                    "why": "AI 在最終配置中實際使用此模板。",
                }
            )

    _append_support_template_fallbacks(
        possible_needed_templates,
        recommended_templates,
        request,
        template_catalog,
    )

    computed_summary = {
        "machine_count": len(machines),
        "total_cpu": sum(int(machine.get("cpu") or 0) for machine in machines),
        "total_memory_mb": sum(int(machine.get("memory_mb") or 0) for machine in machines),
        "total_disk_gb": sum(int(machine.get("disk_gb") or 0) for machine in machines),
        "public_endpoints": sum(
            1 for machine in machines if str(machine.get("purpose", "")).lower() in {"edge", "proxy", "gateway"}
        ),
    }
    overall_config = dict(ai_result.get("overall_config") or {})
    overall_config = {
        "deployment_strategy": overall_config.get("deployment_strategy") or "由 AI 根據需求、節點容量與模板能力整理的整體部署策略。",
        "machine_count": int(overall_config.get("machine_count") or computed_summary["machine_count"]),
        "total_cpu": int(overall_config.get("total_cpu") or computed_summary["total_cpu"]),
        "total_memory_mb": int(overall_config.get("total_memory_mb") or computed_summary["total_memory_mb"]),
        "total_disk_gb": int(overall_config.get("total_disk_gb") or computed_summary["total_disk_gb"]),
    }

    final_plan = {
        "summary": computed_summary,
        "machines": machines,
        "recommended_templates": recommended_templates,
        "possible_needed_templates": possible_needed_templates,
        "overall_config": overall_config,
    }

    return {
        "persona": {
            "role": request.role,
            "course_context": request.course_context,
            "sharing_scope": request.sharing_scope,
            "budget_mode": request.budget_mode,
        },
        "workload_profile": ai_result.get("workload_profile") or "ai-planned",
        "scenario_label": (
            "research-grade"
            if request.course_context == "research"
            else "teaching-service"
            if request.course_context == "teaching"
            else "student-project"
        ),
        "device_profile": summarize_device_nodes(nodes),
        "final_plan": final_plan,
        "recommended_path": {
            "fit": "ai-generated plan",
            "why": [item.get("why") for item in recommended_templates if item.get("why")] or ["AI 依據需求、設備與模板資訊直接規劃。"],
            "upgrade_when": ai_result.get("upgrade_when") or "",
        },
        "rule_basis": {
            "reasons": decision_factors or ["AI 直接根據需求、節點容量與模板清單做整體規劃。"],
            "capacity_checks": [
                {
                    "machine": machine.get("name"),
                    "assigned_node": machine.get("assigned_node"),
                    "status": "ai-assigned",
                }
                for machine in machines
            ],
        },
        "summary": ai_result.get("summary") or "",
    }


def _normalize_machine(machine: dict[str, Any], template: TemplateItem) -> dict[str, Any]:
    install_methods = template.raw.get("install_methods") or []
    default_resources = dict((install_methods[0].get("resources") or {})) if install_methods else {}
    default_cpu = int(default_resources.get("cpu") or 1)
    default_ram_mb = int(default_resources.get("ram") or 1024)
    default_disk_gb = int(default_resources.get("hdd") or 10)

    cpu = max(int(machine.get("cpu") or default_cpu), default_cpu)
    memory_mb = max(int(machine.get("memory_mb") or default_ram_mb), default_ram_mb)
    disk_gb = max(int(machine.get("disk_gb") or default_disk_gb), default_disk_gb)

    return {
        "name": machine.get("name") or f"{template.slug}-node",
        "purpose": machine.get("purpose") or "應用服務",
        "template_slug": template.slug,
        "deployment_type": "lxc" if template.template_type in {"ct", "lxc"} else "vm",
        "cpu": cpu,
        "memory_mb": memory_mb,
        "disk_gb": disk_gb,
        "assigned_node": machine.get("assigned_node"),
        "why": machine.get("why") or "AI 依需求與設備容量規劃此部署單位。",
        "default_resources": {
            "cpu": default_cpu,
            "memory_mb": default_ram_mb,
            "disk_gb": default_disk_gb,
        },
    }


def _normalize_template_choice(
    item: dict[str, Any],
    lookup: dict[str, TemplateItem],
    *,
    fallback_why: str = "AI 依需求選擇此核心模板。",
) -> dict[str, Any] | None:
    slug = str(item.get("slug") or "").strip().lower()
    template = lookup.get(slug)
    if not template:
        return None
    return {
        "slug": template.slug,
        "name": template.name,
        "why": item.get("why") or fallback_why,
    }


def _append_support_template_fallbacks(
    possible_needed_templates: list[dict[str, Any]],
    recommended_templates: list[dict[str, Any]],
    request: RecommendationRequest,
    template_catalog: TemplateCatalog,
) -> None:
    used_slugs = {item["slug"] for item in recommended_templates} | {item["slug"] for item in possible_needed_templates}

    if request.needs_database:
        database_candidates = suggest_support_templates(
            template_catalog,
            needs_public_web=False,
            needs_database=True,
        )
        _append_first_unused_template(
            possible_needed_templates,
            database_candidates,
            used_slugs,
            "因已勾選需要資料庫，補列一個資料庫支援模板供部署時參考。",
        )

    if request.needs_public_web:
        edge_candidates = suggest_support_templates(
            template_catalog,
            needs_public_web=True,
            needs_database=False,
        )
        _append_first_unused_template(
            possible_needed_templates,
            edge_candidates,
            used_slugs,
            "因服務需對外開放，補列一個公開入口或代理模板供部署時參考。",
        )


def _append_first_unused_template(
    target: list[dict[str, Any]],
    candidates: list[TemplateItem],
    used_slugs: set[str],
    why: str,
) -> None:
    for template in candidates:
        if template.slug in used_slugs:
            continue
        target.append(
            {
                "slug": template.slug,
                "name": template.name,
                "why": why,
            }
        )
        used_slugs.add(template.slug)
        return


def _promote_explicit_templates(
    recommended_templates: list[dict[str, Any]],
    possible_needed_templates: list[dict[str, Any]],
    explicit_matches: list[TemplateItem],
) -> None:
    if not explicit_matches:
        return

    existing_core_slugs = {item["slug"] for item in recommended_templates}
    existing_support_slugs = {item["slug"] for item in possible_needed_templates}
    explicit_core_items: list[dict[str, Any]] = []

    for template in explicit_matches:
        if template.slug in existing_core_slugs:
            explicit_core_items.append(next(item for item in recommended_templates if item["slug"] == template.slug))
            continue

        if template.slug in existing_support_slugs:
            moved_item = next(item for item in possible_needed_templates if item["slug"] == template.slug)
            possible_needed_templates[:] = [item for item in possible_needed_templates if item["slug"] != template.slug]
            moved_item["why"] = "使用者需求中明確提到此工具，已提升為核心模板。"
            explicit_core_items.append(moved_item)
            continue

        explicit_core_items.append(
            {
                "slug": template.slug,
                "name": template.name,
                "why": "使用者需求中明確提到此工具，已提升為核心模板。",
            }
        )

    if explicit_core_items:
        explicit_slugs = {item["slug"] for item in explicit_core_items}
        remaining_core = [item for item in recommended_templates if item["slug"] not in explicit_slugs]
        recommended_templates[:] = explicit_core_items + remaining_core


def _align_machine_templates_with_explicit_matches(
    machines: list[dict[str, Any]],
    explicit_matches: list[TemplateItem],
    lookup: dict[str, TemplateItem],
) -> None:
    if not machines or not explicit_matches:
        return

    machine_template_slugs = {str(machine.get("template_slug") or "").strip().lower() for machine in machines}
    if machine_template_slugs & {template.slug for template in explicit_matches}:
        return

    primary_template = explicit_matches[0]
    primary_machine = machines[0]
    normalized = _normalize_machine(primary_machine, lookup[primary_template.slug.lower()])
    normalized["name"] = primary_machine.get("name") or f"{primary_template.slug}-node"
    normalized["purpose"] = primary_machine.get("purpose") or normalized["purpose"]
    normalized["assigned_node"] = primary_machine.get("assigned_node")
    normalized["why"] = "使用者需求中明確指定此工具，已將主要部署單位對齊為對應模板。"
    machines[0] = normalized
