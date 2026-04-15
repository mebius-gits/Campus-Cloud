import { FormEvent, useMemo, useState } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Bot, MessageSquare, Send, Wrench } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { requireGroupManagerUser } from "@/features/auth/guards"
import {
  AiPveLogService,
  type ToolCallRecord,
} from "@/features/ai-pve-log/api"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/groups_/$groupId_/ai-pve-message")({
  component: AiPveMessagePage,
  beforeLoad: () => requireGroupManagerUser(),
  head: () => ({
    meta: [{ title: "AI-PVE 訊息 - Campus Cloud" }],
  }),
})

type LocalMessage = {
  role: "user" | "assistant"
  content: string
  tools?: ToolCallRecord[]
}

function AiPveMessagePage() {
  const { groupId } = Route.useParams()
  const { showErrorToast } = useCustomToast()

  const [input, setInput] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [messages, setMessages] = useState<LocalMessage[]>([
    {
      role: "assistant",
      content:
        "我是 AI-PVE 助手。你可以詢問節點資源、VM/LXC 狀態、儲存空間使用率等資訊。",
    },
  ])

  const canSend = useMemo(
    () => input.trim().length > 0 && !isSending,
    [input, isSending],
  )

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const message = input.trim()
    if (!message || isSending) return

    setInput("")
    setIsSending(true)
    setMessages((prev) => [...prev, { role: "user", content: message }])

    try {
      const response = await AiPveLogService.chat({ message })
      if (response.error) {
        showErrorToast(response.error)
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.reply || response.error || "AI-PVE 沒有回傳內容",
          tools: response.tools_called,
        },
      ])
    } catch (err: any) {
      const detail = err?.body?.detail ?? err?.message ?? "AI-PVE 對話失敗"
      showErrorToast(detail)
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `發生錯誤：${detail}`,
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Link
          to="/groups/$groupId"
          params={{ groupId }}
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI-PVE 訊息</h1>
          <p className="text-sm text-muted-foreground">
            針對當前 PVE 環境快速提問，取得 VM/LXC 與節點運行建議
          </p>
        </div>
      </div>

      <Card className="flex h-[calc(100vh-240px)] min-h-[540px] flex-col">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" />
            對話記錄
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col gap-4 p-4">
          <div className="flex-1 space-y-3 overflow-y-auto rounded-md border bg-muted/20 p-3">
            {messages.map((msg, index) => (
              <div
                key={`${msg.role}-${index}`}
                className={`rounded-md p-3 text-sm ${
                  msg.role === "user"
                    ? "ml-8 bg-primary/10"
                    : "mr-8 border bg-background"
                }`}
              >
                <div className="mb-1 flex items-center gap-2 font-medium">
                  {msg.role === "assistant" ? (
                    <Bot className="h-4 w-4" />
                  ) : (
                    <MessageSquare className="h-4 w-4" />
                  )}
                  {msg.role === "assistant" ? "AI-PVE" : "你"}
                </div>
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                {msg.tools && msg.tools.length > 0 && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Wrench className="h-3.5 w-3.5" />
                      本次工具呼叫
                    </span>
                    {msg.tools.map((tool, toolIndex) => (
                      <Badge key={`${tool.name}-${toolIndex}`} variant="secondary">
                        {tool.name}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {isSending && (
              <div className="mr-8 rounded-md border bg-background p-3 text-sm text-muted-foreground">
                AI-PVE 思考中...
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-2">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="例如：幫我列出目前 CPU 使用率最高的 5 台 VM，並附上節點名稱"
              className="min-h-[90px]"
              disabled={isSending}
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={!canSend}>
                <Send className="mr-2 h-4 w-4" />
                發送訊息
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
