import type {
  BatchSpecAccepted,
  BatchSpecRequest,
  BatchSpecStatusPublic,
  CancelablePromise,
  ConfigPushAccepted,
  ConfigPushStatusPublic,
  HeatmapEntry,
} from "@/client"
import { OpenAPI } from "@/client"
import { request as __request } from "@/client/core/request"

const BASE = "/api/v1/teaching"

export const TeachingAPI = {
  getHeatmap(groupId: string): CancelablePromise<HeatmapEntry[]> {
    return __request(OpenAPI, {
      method: "GET",
      url: `${BASE}/heatmap`,
      query: { group_id: groupId },
    })
  },

  startConfigPush(opts: {
    file: File
    targetPath: string
    vmids: number[]
  }): CancelablePromise<ConfigPushAccepted> {
    return __request(OpenAPI, {
      method: "POST",
      url: `${BASE}/config-push`,
      formData: {
        file: opts.file,
        target_path: opts.targetPath,
        vmids: opts.vmids,
      },
    })
  },

  getConfigPushStatus(
    taskId: string,
  ): CancelablePromise<ConfigPushStatusPublic> {
    return __request(OpenAPI, {
      method: "GET",
      url: `${BASE}/config-push/{task_id}`,
      path: { task_id: taskId },
    })
  },

  startBatchSpec(body: BatchSpecRequest): CancelablePromise<BatchSpecAccepted> {
    return __request(OpenAPI, {
      method: "POST",
      url: `${BASE}/batch-spec`,
      body,
      mediaType: "application/json",
    })
  },

  getBatchSpecStatus(taskId: string): CancelablePromise<BatchSpecStatusPublic> {
    return __request(OpenAPI, {
      method: "GET",
      url: `${BASE}/batch-spec/{task_id}`,
      path: { task_id: taskId },
    })
  },
}
