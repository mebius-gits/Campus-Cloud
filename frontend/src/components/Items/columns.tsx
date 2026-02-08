import type { ColumnDef } from "@tanstack/react-table"
import { Activity, Clock, Cpu, HardDrive, Server } from "lucide-react"

import type { VMSchema } from "@/client"
import { VMActions } from "@/components/Items/VMActions"
import { cn } from "@/lib/utils"

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "N/A"
  const gb = bytes / (1024 * 1024 * 1024)
  return `${gb.toFixed(1)} GB`
}

function formatUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "N/A"
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatCpu(cpu: number | null | undefined): string {
  if (cpu === null || cpu === undefined) return "N/A"
  return `${(cpu * 100).toFixed(1)}%`
}

function StatusBadge({ status }: { status: string }) {
  const isRunning = status === "running"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
        isRunning
          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
          : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
      )}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          isRunning ? "bg-green-500" : "bg-gray-400",
        )}
      />
      {status}
    </span>
  )
}

export const createColumns = (
  onOpenConsole: (vmid: number, name: string, type: string) => void,
): ColumnDef<VMSchema>[] => [
  {
    accessorKey: "vmid",
    header: () => (
      <div className="flex items-center gap-1.5">
        <Server className="h-4 w-4" />
        VMID
      </div>
    ),
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">{row.original.vmid}</span>
    ),
  },
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "status",
    header: () => (
      <div className="flex items-center gap-1.5">
        <Activity className="h-4 w-4" />
        Status
      </div>
    ),
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    accessorKey: "node",
    header: "Node",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.node}</span>
    ),
  },
  {
    accessorKey: "cpu",
    header: () => (
      <div className="flex items-center gap-1.5">
        <Cpu className="h-4 w-4" />
        CPU
      </div>
    ),
    cell: ({ row }) => (
      <span className="font-mono text-sm">{formatCpu(row.original.cpu)}</span>
    ),
  },
  {
    accessorKey: "mem",
    header: () => (
      <div className="flex items-center gap-1.5">
        <HardDrive className="h-4 w-4" />
        Memory
      </div>
    ),
    cell: ({ row }) => (
      <div className="font-mono text-sm">
        <span>{formatBytes(row.original.mem)}</span>
        <span className="text-muted-foreground">
          {" "}
          / {formatBytes(row.original.maxmem)}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "uptime",
    header: () => (
      <div className="flex items-center gap-1.5">
        <Clock className="h-4 w-4" />
        Uptime
      </div>
    ),
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatUptime(row.original.uptime)}
      </span>
    ),
  },
  {
    id: "actions",
    header: "Actions",
    cell: ({ row }) => (
      <VMActions
        vmid={row.original.vmid}
        name={row.original.name}
        type={row.original.type}
        status={row.original.status}
        onOpenConsole={onOpenConsole}
      />
    ),
  },
]

export const columns: ColumnDef<VMSchema>[] = createColumns(() => {})
