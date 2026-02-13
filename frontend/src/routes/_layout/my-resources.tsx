import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Monitor, RefreshCw } from "lucide-react"
import { Suspense, useMemo, useState } from "react"

import { ResourcesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import { createColumns } from "@/components/Resources/columns"
import { TerminalConsoleDialog } from "@/components/Terminal"
import { Button } from "@/components/ui/button"
import { VNCConsoleDialog } from "@/components/VNC"

function getMyResourcesQueryOptions() {
  return {
    queryFn: () => ResourcesService.listMyResources(),
    queryKey: ["my-resources"],
  }
}

export const Route = createFileRoute("/_layout/my-resources")({
  component: MyResources,
  head: () => ({
    meta: [
      {
        title: "My Resources - Campus Cloud",
      },
    ],
  }),
})

function MyResourcesTableContent({
  onOpenConsole,
}: {
  onOpenConsole: (vmid: number, name: string, type: string) => void
}) {
  const { data: resources } = useSuspenseQuery(getMyResourcesQueryOptions())

  const columns = useMemo(() => createColumns(onOpenConsole), [onOpenConsole])

  if (resources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Monitor className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">尚無資源</h3>
        <p className="text-muted-foreground">
          您申請通過的虛擬機/容器將會顯示在這裡
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={resources} />
}

function MyResourcesTable({
  onOpenConsole,
}: {
  onOpenConsole: (vmid: number, name: string, type: string) => void
}) {
  return (
    <Suspense fallback={<PendingItems />}>
      <MyResourcesTableContent onOpenConsole={onOpenConsole} />
    </Suspense>
  )
}

function RefreshButton() {
  const queryClient = useQueryClient()

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["my-resources"] })
  }

  return (
    <Button variant="outline" onClick={handleRefresh}>
      <RefreshCw className="mr-2 h-4 w-4" />
      重新整理
    </Button>
  )
}

function MyResources() {
  const [vncConsoleOpen, setVncConsoleOpen] = useState(false)
  const [terminalConsoleOpen, setTerminalConsoleOpen] = useState(false)
  const [selectedVM, setSelectedVM] = useState<{
    vmid: number
    name: string
    type: string
  } | null>(null)

  const handleOpenConsole = (vmid: number, name: string, type: string) => {
    setSelectedVM({ vmid, name, type })
    if (type === "lxc") {
      setTerminalConsoleOpen(true)
    } else {
      setVncConsoleOpen(true)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">我的資源</h1>
          <p className="text-muted-foreground">
            查看與管理您申請通過的虛擬機和容器
          </p>
        </div>
        <RefreshButton />
      </div>
      <MyResourcesTable onOpenConsole={handleOpenConsole} />
      <VNCConsoleDialog
        vmid={selectedVM?.type === "qemu" ? selectedVM.vmid : null}
        vmName={selectedVM?.name}
        open={vncConsoleOpen}
        onOpenChange={setVncConsoleOpen}
      />
      <TerminalConsoleDialog
        vmid={selectedVM?.type === "lxc" ? selectedVM.vmid : null}
        vmName={selectedVM?.name}
        open={terminalConsoleOpen}
        onOpenChange={setTerminalConsoleOpen}
      />
    </div>
  )
}
