import { queryOptions } from "@tanstack/react-query"

import { type VMRequestStatus, VmRequestsService } from "@/client"
import { queryKeys } from "@/lib/queryKeys"

export function myVmRequestsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.vmRequests.all,
    queryFn: () => VmRequestsService.listMyVmRequests({}),
  })
}

export function adminVmRequestsQueryOptions(status?: VMRequestStatus | null) {
  return queryOptions({
    queryKey: queryKeys.vmRequests.adminList(status || "all"),
    queryFn: () =>
      VmRequestsService.listAllVmRequests({
        status: status || undefined,
        limit: 100,
      }),
  })
}
