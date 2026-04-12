import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError } from "@/client"
import { AuthSessionService } from "@/services/authSession"

const handleApiError = async (error: Error) => {
  if (error instanceof ApiError && error.status === 401) {
    const refreshed = await AuthSessionService.refreshAccessToken()
    if (refreshed) {
      await queryClient.invalidateQueries({ refetchType: "active" })
    } else {
      AuthSessionService.clearTokens()
      toast.error("登入已失效，請重新登入")
      window.location.href = "/login"
    }
    return
  }

  if (error instanceof ApiError && error.status === 403) {
    const detail =
      (error.body as { detail?: string } | undefined)?.detail ??
      "你沒有操作權限"
    toast.error(detail)
  }
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (
          error instanceof ApiError &&
          (error.status === 401 || error.status === 403)
        ) {
          return false
        }
        return failureCount < 3
      },
    },
    mutations: {
      retry: false,
    },
  },
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})
