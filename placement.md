# Campus Cloud

Campus Cloud is a full-stack platform for requesting, approving, placing, and operating scheduled VM/LXC resources on a Proxmox cluster.

## What This Project Does

- Students submit VM or LXC requests with a required usage window.
- The system only accepts request windows that still have schedulable capacity.
- Admins review each request with a dedicated time-slot view:
  - current running resources in the pool
  - approved requests overlapping the same requested window
  - projected balanced placement if the current request is approved
- Approved requests are reserved first.
- When the requested `start_at` arrives, the scheduler rebalances the active cohort for that time slot.
- Resources are then created, started, or migrated so the slot runs on the best feasible balanced layout.
- At `end_at`, the scheduler automatically shuts the resource down.

## Core Workflow

### 1. Request submission

1. The user selects resource type, spec, and a usage window.
2. The frontend asks the availability API for selectable time slots.
3. The backend validates the final submitted window again before saving.
4. The request is stored as `pending`.

Relevant files:

- [backend/app/services/vm_request_service.py](backend/app/services/vm_request_service.py)
- [backend/app/services/vm_request_availability_service.py](backend/app/services/vm_request_availability_service.py)
- [frontend/src/components/Applications/ApplicationRequestPage.tsx](frontend/src/components/Applications/ApplicationRequestPage.tsx)

### 2. Admin review

1. The admin opens the request review page.
2. The backend returns a review context for that request window:
   - current running resources
   - overlapping approved requests
   - projected node assignments if this request is approved
3. When the admin approves, the system rebuilds reservations for all overlapping approved requests and writes the projected node as the request's `desired_node`.

Relevant files:

- [backend/app/services/vm_request_service.py](backend/app/services/vm_request_service.py)
- [backend/app/api/routes/vm_requests.py](backend/app/api/routes/vm_requests.py)
- [frontend/src/components/Applications/VMRequestReviewPage.tsx](frontend/src/components/Applications/VMRequestReviewPage.tsx)
- [frontend/src/services/vmRequestReview.ts](frontend/src/services/vmRequestReview.ts)

### 3. Time-slot rebalance at start time

When a scheduled window becomes active, the scheduler does not simply start the approved machine where it was originally reserved. Instead it:

1. finds all approved requests active in the current time slot
2. recomputes a balanced placement for the full active cohort
3. writes the new `desired_node` values
4. creates missing resources on the desired node
5. migrates already-provisioned resources if their `actual_node` differs from `desired_node`
6. ensures the final resource is running

This design lets the cluster rebalance at the actual start of use, not only at review time.

Relevant files:

- [backend/app/services/vm_request_schedule_service.py](backend/app/services/vm_request_schedule_service.py)
- [backend/app/services/vm_request_placement_service.py](backend/app/services/vm_request_placement_service.py)
- [backend/app/services/provisioning_service.py](backend/app/services/provisioning_service.py)
- [backend/app/services/proxmox_service.py](backend/app/services/proxmox_service.py)

### 4. Automatic stop

When `end_at` is reached, the scheduler triggers a shutdown for the approved resource.

Relevant file:

- [backend/app/services/vm_request_schedule_service.py](backend/app/services/vm_request_schedule_service.py)

## Placement Model

Each VM request now tracks both planning state and runtime state:

- `assigned_node`: the latest reserved or selected node recorded for the request
- `desired_node`: where the algorithm wants the request to run for the active slot
- `actual_node`: where the resource is currently running in Proxmox
- `migration_status`: whether the runtime is stable, pending migration, migrating, blocked, or failed
- `rebalance_epoch`: version number of the last active-slot rebalance
- `last_rebalanced_at`: when the current slot was last rebalanced

Relevant files:

- [backend/app/models/vm_request.py](backend/app/models/vm_request.py)
- [backend/app/alembic/versions/t2u3v4w5x6y7_add_rebalance_fields_to_vm_requests.py](backend/app/alembic/versions/t2u3v4w5x6y7_add_rebalance_fields_to_vm_requests.py)

### Placement inputs

The scheduler now uses two admin-managed configuration sources during placement:

- `Proxmox node priority`
  - lower number means higher priority
  - this is the primary node tie-break, matching the PVE simulator behavior
- `Proxmox storage settings`
  - `enabled`: disabled pools do not participate in VM/LXC placement
  - `speed_tier`: `nvme` is preferred over `ssd`, then `hdd`, then `unknown`
  - `user_priority`: lower number means more preferred within the same speed tier

Storage configuration affects both:

- placement feasibility
  - a node is not treated as a valid disk target if it has no enabled compatible storage pool for the request
- provisioning target storage
  - actual create/clone operations now prefer the best admin-managed storage pool on the selected node, rather than relying only on the request payload default

Relevant files:

- [backend/app/services/vm_request_placement_service.py](backend/app/services/vm_request_placement_service.py)
- [backend/app/services/provisioning_service.py](backend/app/services/provisioning_service.py)
- [backend/app/models/proxmox_storage.py](backend/app/models/proxmox_storage.py)

## Local Development

### Backend

```bash
cd backend
uv sync
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Full stack with Docker Compose

See [development.md](development.md) and [deployment.md](deployment.md).

## Important Notes

- Run Alembic migrations before using the latest scheduling flow:

```bash
cd backend
alembic upgrade head
```

- If backend API schemas change, regenerate or align frontend API usage as needed.
- The scheduler logic assumes the Campus Cloud Proxmox pool is the source of truth for runtime resources.

## Tests Used For This Workflow

The VM request workflow is covered in:

- [backend/tests/test_backend_workflows.py](backend/tests/test_backend_workflows.py)

Useful focused test commands:

```bash
pytest backend/tests/test_backend_workflows.py -k "vm_request or process_due_request_starts"
```

## Additional Docs

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [development.md](development.md)
- [deployment.md](deployment.md)
