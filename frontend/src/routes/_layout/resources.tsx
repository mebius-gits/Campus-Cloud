import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Monitor, RefreshCw } from "lucide-react"
import { Suspense, useMemo, useState } from "react"
import { ResourcesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { createColumns } from "@/components/Items/columns"
import PendingItems from "@/components/Pending/PendingItems"
import { TerminalConsoleDialog } from "@/components/Terminal"
import { Button } from "@/components/ui/button"
import { VNCConsoleDialog } from "@/components/VNC"

function getVMsQueryOptions() {
  return {
    queryFn: () => ResourcesService.listResources({}),
    queryKey: ["resources"],
  }
}

export const Route = createFileRoute("/_layout/resources")({
  component: VirtualMachines,
  head: () => ({
    meta: [
      {
        title: "Virtual Machines - Campus Cloud",
      },
    ],
  }),
})

function VMsTableContent({
  onOpenConsole,
}: {
  onOpenConsole: (vmid: number, name: string, type: string) => void
}) {
  const { data: resources } = useSuspenseQuery(getVMsQueryOptions())

  const columns = useMemo(() => createColumns(onOpenConsole), [onOpenConsole])

  if (resources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Monitor className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No virtual machines found</h3>
        <p className="text-muted-foreground">
          Virtual machines will appear here once they are created in Proxmox
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={resources} />
}

function VMsTable({
  onOpenConsole,
}: {
  onOpenConsole: (vmid: number, name: string, type: string) => void
}) {
  return (
    <Suspense fallback={<PendingItems />}>
      <VMsTableContent onOpenConsole={onOpenConsole} />
    </Suspense>
  )
}

function RefreshButton() {
  const queryClient = useQueryClient()

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["resources"] })
  }

  return (
    <Button variant="outline" onClick={handleRefresh}>
      <RefreshCw className="mr-2 h-4 w-4" />
      Refresh
    </Button>
  )
}

function VirtualMachines() {
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
          <h1 className="text-2xl font-bold tracking-tight">
            Virtual Machines & Containers
          </h1>
          <p className="text-muted-foreground">
            View and manage your virtual machines and LXC containers from
            Proxmox
          </p>
        </div>
        <RefreshButton />
      </div>
      <VMsTable onOpenConsole={handleOpenConsole} />
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
