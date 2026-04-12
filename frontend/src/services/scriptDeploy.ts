import {
  type ScriptDeployRequest,
  type ScriptDeployResponse,
  ScriptDeployService,
  type ScriptDeployStatus,
} from "@/client"

export const ScriptDeployApi = {
  deploy(data: {
    requestBody: ScriptDeployRequest
  }): Promise<ScriptDeployResponse> {
    return ScriptDeployService.deployServiceTemplate({
      requestBody: data.requestBody,
    })
  },

  getStatus(data: { taskId: string }): Promise<ScriptDeployStatus> {
    return ScriptDeployService.getDeployStatus({
      taskId: data.taskId,
    })
  },

  register(data: { taskId: string }): Promise<Record<string, unknown>> {
    return ScriptDeployService.registerDeployedResource({
      taskId: data.taskId,
    }) as Promise<Record<string, unknown>>
  },
}
