/**
 * Polls every running VM the current user owns and surfaces the first one
 * whose backend reports ``should_warn=true``. Returns the SessionStatus +
 * dismiss callback so the layout can render a single shared dialog.
 *
 * Polling cadence is 30s (matches backend's ``practice_warning_minutes``
 * default of 30 — well within margin). The dismiss state is per-vmid so
 * snoozing one warning doesn't suppress others.
 */
import { useQueries, useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"

import { type ResourcePublic, ResourcesService } from "@/client"
import {
  type SessionStatus,
  SessionWarningService,
} from "@/services/sessionWarning"

const POLL_INTERVAL_MS = 30_000

export function useSessionWarning(): {
  active: SessionStatus | null
  dismiss: () => void
} {
  // Pull the current user's VMs so we know which vmids to poll.
  const { data: myResources = [] } = useQuery<ResourcePublic[]>({
    queryKey: ["sessionStatus", "myResources"],
    queryFn: () => ResourcesService.listMyResources(),
    refetchInterval: POLL_INTERVAL_MS * 4, // less frequent than per-VM poll
  })

  const runningVmids = useMemo(
    () => myResources.filter((r) => r.status === "running").map((r) => r.vmid),
    [myResources],
  )

  const sessionQueries = useQueries({
    queries: runningVmids.map((vmid) => ({
      queryKey: ["sessionStatus", vmid],
      queryFn: () => SessionWarningService.getStatus(vmid),
      refetchInterval: POLL_INTERVAL_MS,
    })),
  })

  const [dismissed, setDismissed] = useState<Set<number>>(new Set())

  // Reset dismissals only when the corresponding query has a fresh response
  // explicitly saying ``should_warn=false``. Loading/error states leave the
  // entry alone so a transient blip doesn't re-pop the dialog.
  //
  // ``warnByVmid`` is a stable lookup that only changes when warn flags do —
  // letting the effect avoid re-running on every render.
  const warnByVmid = useMemo(() => {
    const map = new Map<number, boolean>()
    for (const q of sessionQueries) {
      if (q.data) map.set(q.data.vmid, q.data.should_warn)
    }
    return map
  }, [sessionQueries])

  useEffect(() => {
    setDismissed((prev) => {
      if (prev.size === 0) return prev
      const next = new Set(prev)
      for (const vmid of prev) {
        // Only clear when we have a confirmed should_warn === false.
        if (warnByVmid.get(vmid) === false) {
          next.delete(vmid)
        }
      }
      return next.size === prev.size ? prev : next
    })
  }, [warnByVmid])

  const active =
    sessionQueries.find(
      (q) =>
        q.data?.should_warn === true &&
        q.data.can_extend &&
        !dismissed.has(q.data.vmid),
    )?.data ?? null

  return {
    active,
    dismiss: () => {
      if (active) {
        setDismissed((prev) => new Set(prev).add(active.vmid))
      }
    },
  }
}
