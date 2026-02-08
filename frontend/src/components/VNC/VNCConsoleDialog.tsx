import {
  Clipboard,
  Keyboard,
  Loader2,
  Maximize,
  Minimize2,
  Monitor,
  Power,
  X,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { VncScreen } from "react-vnc"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"

interface VNCConsoleDialogProps {
  vmid: number | null
  vmName?: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function VNCConsoleDialog({
  vmid,
  vmName,
  open,
  onOpenChange,
}: VNCConsoleDialogProps) {
  const vncRef = useRef<React.ElementRef<typeof VncScreen>>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [vncTicket, setVncTicket] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    if (open && vmid) {
      setIsLoading(true)
      setError(null)
      setVncTicket(null)

      const token = localStorage.getItem("access_token")
      const apiBase = import.meta.env.VITE_API_URL || ""
      fetch(`${apiBase}/api/v1/vm/${vmid}/console`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
        .then((res) => {
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}`)
          }
          return res.json()
        })
        .then((data) => {
          if (data.ticket) {
            setVncTicket(data.ticket)
          } else {
            setError("無法取得 VNC ticket")
          }
        })
        .catch((err) => {
          setError(`取得 VNC 資訊失敗: ${err.message}`)
        })
        .finally(() => {
          setIsLoading(false)
        })
    } else {
      setVncTicket(null)
      setError(null)
    }
  }, [open, vmid])

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener("fullscreenchange", handleFullscreenChange)
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange)
  }, [])

  const handleConnect = useCallback(() => {
    setIsConnected(true)
    console.log("✅ VNC connected")
  }, [])

  const handleDisconnect = useCallback(() => {
    setIsConnected(false)
    console.log("VNC disconnected")
  }, [])

  const handleClose = () => {
    if (vncRef.current) {
      vncRef.current.disconnect?.()
    }
    onOpenChange(false)
    setIsConnected(false)
    setVncTicket(null)
  }

  const sendCtrlAltDel = () => {
    vncRef.current?.sendCtrlAltDel?.()
  }

  const handleClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText()
      vncRef.current?.clipboardPaste?.(text)
    } catch (err) {
      console.error("無法讀取剪貼簿:", err)
    }
  }

  const toggleFullscreen = () => {
    const container = document.querySelector(".vnc-dialog-container")
    if (!container) return

    if (!document.fullscreenElement) {
      container.requestFullscreen?.()
    } else {
      document.exitFullscreen?.()
    }
  }

  const protocol =
    typeof window !== "undefined"
      ? window.location.protocol === "https:"
        ? "wss:"
        : "ws:"
      : "ws:"
  const wsUrl = vmid
    ? `${protocol}//${typeof window !== "undefined" ? window.location.hostname : "localhost"}:8090/ws/vnc/${vmid}`
    : ""

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className={cn(
          "vnc-dialog-container w-[98vw] h-[95vh] max-w-[98vw] sm:max-w-[98vw] flex flex-col p-0 gap-0",
          "bg-zinc-900 border-zinc-700 overflow-hidden",
          "[&>button]:hidden",
        )}
      >
        <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-zinc-800 to-zinc-900 border-b border-zinc-700 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/20">
              <Monitor className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                {vmName || `VM ${vmid}`}
              </h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-400">VMID: {vmid}</span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium",
                    isConnected
                      ? "bg-emerald-500/20 text-emerald-400"
                      : isLoading
                        ? "bg-amber-500/20 text-amber-400"
                        : "bg-zinc-500/20 text-zinc-400",
                  )}
                >
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      isConnected
                        ? "bg-emerald-400"
                        : isLoading
                          ? "bg-amber-400 animate-pulse"
                          : "bg-zinc-400",
                    )}
                  />
                  {isConnected ? "已連線" : isLoading ? "連線中..." : "未連線"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={sendCtrlAltDel}
              disabled={!isConnected}
              className="h-8 px-3 text-xs text-zinc-300 hover:text-white hover:bg-zinc-700/50 disabled:opacity-40"
            >
              <Keyboard className="h-3.5 w-3.5 mr-1.5" />
              Ctrl+Alt+Del
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClipboard}
              disabled={!isConnected}
              className="h-8 px-3 text-xs text-zinc-300 hover:text-white hover:bg-zinc-700/50 disabled:opacity-40"
            >
              <Clipboard className="h-3.5 w-3.5 mr-1.5" />
              貼上
            </Button>
            <div className="w-px h-6 bg-zinc-700 mx-1" />
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleFullscreen}
              disabled={!isConnected}
              className="h-8 w-8 text-zinc-300 hover:text-white hover:bg-zinc-700/50 disabled:opacity-40"
              title={isFullscreen ? "退出全螢幕" : "全螢幕"}
            >
              {isFullscreen ? (
                <Minimize2 className="h-4 w-4" />
              ) : (
                <Maximize className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClose}
              className="h-8 w-8 text-zinc-400 hover:text-red-400 hover:bg-red-500/10"
              title="關閉"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden bg-black relative">
          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 z-20">
              <div className="flex flex-col items-center text-center p-8 max-w-md">
                <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                  <Power className="h-8 w-8 text-red-400" />
                </div>
                <h3 className="text-lg font-medium text-white mb-2">
                  連線失敗
                </h3>
                <p className="text-sm text-zinc-400 mb-6">{error}</p>
                <Button
                  onClick={handleClose}
                  variant="outline"
                  className="border-zinc-600 text-zinc-300 hover:bg-zinc-800"
                >
                  關閉
                </Button>
              </div>
            </div>
          )}

          {!error && (isLoading || (!isConnected && vncTicket)) && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 z-20">
              <div className="flex flex-col items-center">
                <div className="relative mb-6">
                  <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center">
                    <Monitor className="h-10 w-10 text-zinc-600" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center border-2 border-zinc-900">
                    <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
                  </div>
                </div>
                <h3 className="text-lg font-medium text-white mb-2">
                  正在連接
                </h3>
                <p className="text-sm text-zinc-400">
                  正在建立 VNC 連線至 {vmName || `VM ${vmid}`}...
                </p>
              </div>
            </div>
          )}

          {vmid && open && wsUrl && vncTicket && (
            <VncScreen
              url={wsUrl}
              scaleViewport
              ref={vncRef}
              rfbOptions={{
                credentials: {
                  username: "",
                  password: vncTicket,
                  target: "",
                },
              }}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
              style={{
                width: "100%",
                height: "100%",
                background: "#000",
              }}
            />
          )}
        </div>

        <div className="flex items-center justify-between px-4 py-1.5 bg-zinc-800/50 border-t border-zinc-700/50 shrink-0">
          <div className="flex items-center gap-4 text-[11px] text-zinc-500">
            <span>WebSocket: {wsUrl ? "已連接" : "未連接"}</span>
            <span>•</span>
            <span>VNC Protocol v3.8</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClose}
              className="h-7 px-3 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
            >
              <Power className="h-3 w-3 mr-1.5" />
              中斷連線
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
