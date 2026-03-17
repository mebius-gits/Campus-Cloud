# AI Template Recommendation

Standalone layered backend for AI-driven template recommendation.

Current behavior:

- reads available templates from `frontend/src/json`
- exposes its own unauthenticated `GET /api/v1/resources/nodes`
- reads live node capacity from internal `NODES_SNAPSHOT_JSON`
- sends user demand + live capacity + template catalog to vLLM
- lets AI directly propose templates, machine split, and sizing
- normalizes AI output so template slugs must exist in the frontend catalog
- uses template `install_methods[].resources` as the minimum baseline

## AI Architecture

Current AI flow:

1. frontend sends user intent to `POST /recommend` or `POST /api/v1/recommend`
2. service reads node data from its own `GET /api/v1/resources/nodes`
3. service loads available templates from `frontend/src/json`
4. service sends:
   - user demand
   - live node summary
   - template catalog summary
   to vLLM
5. AI directly outputs:
   - recommended templates
   - machine split
   - CPU / memory / disk
   - preferred assigned node
   - risks and upgrade timing
6. backend normalizes the result:
   - template slug must exist in frontend catalog
   - deployment type is aligned with template type
   - CPU / RAM / disk cannot be lower than template default resources

This means:

- AI is the planner
- template catalog is the allowed template source
- backend only does validation and normalization

## Layer Responsibilities

- `app/api/routes/recommendation.py`
  Receives recommendation requests and returns the final AI plan.
- `app/api/routes/resources.py`
  Exposes internal node data at `/api/v1/resources/nodes` without inbound auth.
- `app/services/backend_nodes_service.py`
  Reads `NODES_SNAPSHOT_JSON`, converts it into node schemas, and builds capacity summaries.
- `app/services/catalog_service.py`
  Loads and serializes available templates from `frontend/src/json`.
- `app/services/recommendation_service.py`
  Builds the AI prompt, calls vLLM, and normalizes AI output.
- `app/core/config.py`
  Centralizes all environment-based settings.

## Structure

- `main.py`: compatibility entrypoint
- `app/main.py`: FastAPI app
- `app/core/config.py`: settings
- `app/api/routes/resources.py`: internal node API
- `app/api/routes/recommendation.py`: recommendation API
- `app/services/backend_nodes_service.py`: backend node fetch + normalization
- `app/services/catalog_service.py`: template catalog loading
- `app/services/recommendation_service.py`: AI planning + output normalization
- `app/schemas/`: request and response schemas

## Quick Start

```bash
cd ai-template-recommendation
copy .env.example .env
pip install -r requirements.txt
python main.py
```

Default address:

```text
http://localhost:8010
```

UI:

```text
http://localhost:8010/
```

Docs:

```text
http://localhost:8010/docs
```

## Main Endpoints

- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/resources/nodes`
- `POST /recommend`
- `POST /api/v1/recommend`

## Notes

- `GET /api/v1/resources/nodes` is implemented directly inside this service.
- Node data comes from `NODES_SNAPSHOT_JSON` in `.env`.
- AI can only choose templates that exist in `frontend/src/json`.
- AI-proposed CPU / RAM / disk will be clamped so they do not go below the template default resources.
