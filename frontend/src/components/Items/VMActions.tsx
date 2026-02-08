import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  MonitorPlay,
  MoreVertical,
  Play,
  Power,
  RotateCcw,
  Square,
  Terminal,
  XCircle,
} from "lucide-react"
import { ResourcesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"

interface VMActionsProps {
  vmid: number
  name: string
  type: string
  status: string
  onOpenConsole: (vmid: number, name: string, type: string) => void
}

export function VMActions({
  vmid,
  name,
  type,
  status,
  onOpenConsole,
}: VMActionsProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const isRunning = status === "running"
  const isStopped = status === "stopped"
  const isLXC = type === "lxc"

  const startMutation = useMutation({
    mutationFn: () => ResourcesService.startResource({ vmid }),
    onSuccess: () => {
      showSuccessToast(`${name} is starting...`)
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ["resources"] })
    },
    onError: (error: Error) => {
      showErrorToast(`Failed to start ${name}: ${error.message}`)
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => ResourcesService.stopResource({ vmid }),
    onSuccess: () => {
      showSuccessToast(`${name} is stopping...`)
      queryClient.invalidateQueries({ queryKey: ["resources"] })
    },
    onError: (error: Error) => {
      showErrorToast(`Failed to stop ${name}: ${error.message}`)
    },
  })

  const rebootMutation = useMutation({
    mutationFn: () => ResourcesService.rebootResource({ vmid }),
    onSuccess: () => {
      showSuccessToast(`${name} is rebooting...`)
      queryClient.invalidateQueries({ queryKey: ["resources"] })
    },
    onError: (error: Error) => {
      showErrorToast(`Failed to reboot ${name}: ${error.message}`)
    },
  })

  const shutdownMutation = useMutation({
    mutationFn: () => ResourcesService.shutdownResource({ vmid }),
    onSuccess: () => {
      showSuccessToast(`${name} is shutting down...`)
      queryClient.invalidateQueries({ queryKey: ["resources"] })
    },
    onError: (error: Error) => {
      showErrorToast(`Failed to shutdown ${name}: ${error.message}`)
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => ResourcesService.resetResource({ vmid }),
    onSuccess: () => {
      showSuccessToast(`${name} is resetting...`)
      queryClient.invalidateQueries({ queryKey: ["resources"] })
    },
    onError: (error: Error) => {
      showErrorToast(`Failed to reset ${name}: ${error.message}`)
    },
  })

  const isLoading =
    startMutation.isPending ||
    stopMutation.isPending ||
    rebootMutation.isPending ||
    shutdownMutation.isPending ||
    resetMutation.isPending

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!isRunning}
        onClick={() => onOpenConsole(vmid, name, type)}
      >
        {isLXC ? (
          <Terminal className="h-4 w-4 mr-1" />
        ) : (
          <MonitorPlay className="h-4 w-4 mr-1" />
        )}
        {isLXC ? "Terminal" : "Console"}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" disabled={isLoading}>
            <MoreVertical className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuLabel>Power Control</DropdownMenuLabel>
          <DropdownMenuSeparator />

          <DropdownMenuItem
            onClick={() => startMutation.mutate()}
            disabled={isRunning || isLoading}
            className="cursor-pointer"
          >
            <Play className="mr-2 h-4 w-4 text-green-600" />
            <span>Start</span>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={() => shutdownMutation.mutate()}
            disabled={!isRunning || isLoading}
            className="cursor-pointer"
          >
            <Power className="mr-2 h-4 w-4 text-blue-600" />
            <span>Shutdown</span>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={() => rebootMutation.mutate()}
            disabled={!isRunning || isLoading}
            className="cursor-pointer"
          >
            <RotateCcw className="mr-2 h-4 w-4 text-orange-600" />
            <span>Reboot</span>
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem
            onClick={() => stopMutation.mutate()}
            disabled={isStopped || isLoading}
            className="cursor-pointer"
          >
            <Square className="mr-2 h-4 w-4 text-amber-600" />
            <span>Stop (Force)</span>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={() => resetMutation.mutate()}
            disabled={!isRunning || isLoading}
            className="cursor-pointer"
          >
            <XCircle className="mr-2 h-4 w-4 text-red-600" />
            <span>Reset (Force)</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
