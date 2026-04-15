import type { CancelablePromise } from "@/client"
import { OpenAPI } from "@/client"
import { request as __request } from "@/client/core/request"

export type ToolCallRecord = {
  name: string
  args: Record<string, unknown>
}

export type ChatResponse = {
  reply: string
  tools_called: ToolCallRecord[]
  error: string | null
}

export const AiPveLogService = {
  chat(data: { message: string }): CancelablePromise<ChatResponse> {
    return __request(OpenAPI, {
      method: "POST",
      url: "/api/v1/ai/pve-log/chat",
      body: data,
      mediaType: "application/json",
    })
  },
}
