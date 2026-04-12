import {
  AiTemplateRecommendationService,
  type ChatRequest,
  type ChatResponse,
} from "@/client"

export type AiChatMessage = {
  role: "user" | "assistant" | "system"
  content: string
}

export type AiMetrics = {
  total_tokens?: number
  elapsed_seconds?: number
  tokens_per_second?: number
}

export type FormPrefill = {
  resource_type?: string
  hostname?: string
  service_template_slug?: string
  lxc_template_slug?: string
  lxc_os_image?: string
  vm_os_choice?: string
  vm_template_id?: number
  cores?: number
  memory_mb?: number
  disk_gb?: number
  username?: string
  reason?: string
}

export type AiPlanResult = {
  summary?: string
  final_plan?: {
    form_prefill?: FormPrefill
    recommended_templates?: Array<{
      slug: string
      name: string
      why: string
    }>
    machines?: Array<{
      name: string
      deployment_type: string
      cpu: number
      memory_mb: number
      disk_gb: number
      template_slug?: string
    }>
    application_target?: {
      service_name?: string
      execution_environment?: string
      environment_reason?: string
    }
  }
  ai_metrics?: AiMetrics
}

export type AiTemplateRecommendationRequest = Pick<
  ChatRequest,
  "messages" | "top_k" | "device_nodes"
>

export const AiTemplateRecommendationApi = {
  chat(data: {
    requestBody: AiTemplateRecommendationRequest
  }): Promise<ChatResponse> {
    return AiTemplateRecommendationService.chat({
      requestBody: data.requestBody,
    })
  },

  recommend(data: {
    requestBody: AiTemplateRecommendationRequest
  }): Promise<AiPlanResult> {
    return AiTemplateRecommendationService.recommend({
      requestBody: data.requestBody,
    }) as Promise<AiPlanResult>
  },
}
