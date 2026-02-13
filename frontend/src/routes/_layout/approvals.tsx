import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { ClipboardCheck } from "lucide-react"
import { Suspense, useState } from "react"

import { type VMRequestStatus, UsersService, VmRequestsService } from "@/client"
import { adminRequestColumns } from "@/components/Applications/adminColumns"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function getAdminRequestsQueryOptions(status?: VMRequestStatus | null) {
  return {
    queryFn: () =>
      VmRequestsService.listAllVmRequests({
        status: status || undefined,
        limit: 100,
      }),
    queryKey: ["vm-requests-admin", status || "all"],
  }
}

export const Route = createFileRoute("/_layout/approvals")({
  component: Approvals,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Approvals - Campus Cloud",
      },
    ],
  }),
})

function AdminRequestsTableContent({
  status,
}: {
  status: VMRequestStatus | null
}) {
  const { data } = useSuspenseQuery(
    getAdminRequestsQueryOptions(status),
  )

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ClipboardCheck className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">沒有申請紀錄</h3>
        <p className="text-muted-foreground">
          {status === "pending"
            ? "目前沒有待審核的申請"
            : "目前沒有符合篩選條件的申請"}
        </p>
      </div>
    )
  }

  return <DataTable columns={adminRequestColumns} data={data.data} />
}

function AdminRequestsTable({
  status,
}: {
  status: VMRequestStatus | null
}) {
  return (
    <Suspense fallback={<PendingItems />}>
      <AdminRequestsTableContent status={status} />
    </Suspense>
  )
}

function PendingCountBadge() {
  const { data } = useQuery({
    queryFn: () =>
      VmRequestsService.listAllVmRequests({
        status: "pending" as VMRequestStatus,
        limit: 100,
      }),
    queryKey: ["vm-requests-admin", "pending-count"],
  })

  const count = data?.count ?? 0
  if (count === 0) return null

  return (
    <Badge variant="outline" className="ml-1.5 text-xs">
      {count}
    </Badge>
  )
}

function Approvals() {
  const [statusFilter, setStatusFilter] = useState<VMRequestStatus | null>(
    "pending",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">申請審核</h1>
          <p className="text-muted-foreground">
            審核使用者的虛擬機/容器申請
          </p>
        </div>
      </div>

      <Tabs
        value={statusFilter || "all"}
        onValueChange={(v) =>
          setStatusFilter(v === "all" ? null : (v as VMRequestStatus))
        }
      >
        <TabsList>
          <TabsTrigger value="pending">
            待審核
            <PendingCountBadge />
          </TabsTrigger>
          <TabsTrigger value="approved">已通過</TabsTrigger>
          <TabsTrigger value="rejected">已拒絕</TabsTrigger>
          <TabsTrigger value="all">全部</TabsTrigger>
        </TabsList>
      </Tabs>

      <AdminRequestsTable status={statusFilter} />
    </div>
  )
}
