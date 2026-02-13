import { standardSchemaResolver } from "@hookform/resolvers/standard-schema"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { LxcService, VmRequestsService, VmService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  resource_type: z.enum(["lxc", "vm"]),
  reason: z
    .string()
    .min(1, { message: "申請原因為必填項" })
    .min(10, { message: "申請原因至少需要 10 個字符" }),
  hostname: z
    .string()
    .min(1, { message: "名稱為必填項" })
    .regex(/^[a-z0-9-]+$/, {
      message: "僅允許小寫字母、數字和連字符",
    }),
  ostemplate: z.string().optional(),
  rootfs_size: z.number().min(8).max(500).optional(),
  template_id: z.number().optional(),
  disk_size: z.number().min(20).max(500).optional(),
  username: z.string().optional(),
  cores: z.number().min(1).max(8),
  memory: z.number().min(512).max(32768),
  password: z
    .string()
    .min(1, { message: "密碼為必填項" })
    .min(8, { message: "密碼至少需要 8 個字符" }),
  storage: z.string().default("local-lvm"),
  os_info: z.string().optional(),
  expiry_date: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

const CreateVMRequest = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [resourceType, setResourceType] = useState<"lxc" | "vm">("lxc")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: standardSchemaResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      resource_type: "lxc",
      reason: "",
      hostname: "",
      ostemplate: "",
      template_id: undefined,
      username: "",
      cores: 2,
      memory: 2048,
      disk_size: 20,
      rootfs_size: 8,
      password: "",
      os_info: "",
      expiry_date: "",
    },
  })

  const { data: lxcTemplates, isLoading: lxcTemplatesLoading } = useQuery({
    queryKey: ["lxc-templates"],
    queryFn: () => LxcService.getTemplates(),
    enabled: isOpen && resourceType === "lxc",
  })

  const { data: vmTemplates, isLoading: vmTemplatesLoading } = useQuery({
    queryKey: ["vm-templates"],
    queryFn: () => VmService.getVmTemplates(),
    enabled: isOpen && resourceType === "vm",
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) => {
      if (data.resource_type === "lxc") {
        if (!data.ostemplate || !data.rootfs_size) {
          throw new Error("LXC容器需要選擇作業系統模板和磁碟大小")
        }
        return VmRequestsService.createVmRequest({
          requestBody: {
            reason: data.reason,
            resource_type: "lxc",
            hostname: data.hostname,
            ostemplate: data.ostemplate,
            rootfs_size: data.rootfs_size,
            cores: data.cores,
            memory: data.memory,
            password: data.password,
            storage: data.storage,
            os_info: data.os_info || null,
            expiry_date: data.expiry_date || null,
          },
        })
      }
      if (!data.template_id || !data.disk_size || !data.username) {
        throw new Error("VM需要選擇作業系統、使用者名稱和磁碟大小")
      }
      return VmRequestsService.createVmRequest({
        requestBody: {
          reason: data.reason,
          resource_type: "vm",
          hostname: data.hostname,
          template_id: data.template_id,
          username: data.username,
          password: data.password,
          cores: data.cores,
          memory: data.memory,
          disk_size: data.disk_size,
          os_info: data.os_info || null,
          expiry_date: data.expiry_date || null,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("申請已提交，等待管理員審核")
      form.reset()
      setResourceType("lxc")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["vm-requests"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      setIsOpen(open)
      if (!open) {
        form.reset()
        setResourceType("lxc")
      }
    }}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          申請資源
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>申請虛擬機 / 容器</DialogTitle>
          <DialogDescription>
            填寫申請表單，提交後需等待管理員審核通過後自動建立
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <Tabs defaultValue="custom" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="quick">快速範本</TabsTrigger>
                <TabsTrigger value="custom">自訂規格</TabsTrigger>
              </TabsList>

              <TabsContent value="quick" className="space-y-4">
                <div className="text-center py-8 text-muted-foreground">
                  快速範本功能即將推出
                </div>
              </TabsContent>

              <TabsContent value="custom" className="space-y-4 py-4">
                <Tabs
                  defaultValue="lxc"
                  onValueChange={(value) => {
                    setResourceType(value as "lxc" | "vm")
                    form.setValue("resource_type", value as "lxc" | "vm")
                  }}
                  className="w-full"
                >
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="lxc">LXC 容器</TabsTrigger>
                    <TabsTrigger value="vm">QEMU 虛擬機</TabsTrigger>
                  </TabsList>

                  {/* LXC Container Form */}
                  <TabsContent value="lxc" className="space-y-4 mt-4">
                    <div className="grid gap-4">
                      <FormField
                        control={form.control}
                        name="hostname"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              容器名稱{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：project-alpha-web"
                                {...field}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="ostemplate"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              作業系統映像檔{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <Select
                              onValueChange={field.onChange}
                              defaultValue={field.value}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="選擇作業系統" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {lxcTemplatesLoading ? (
                                  <SelectItem value="loading" disabled>
                                    載入中...
                                  </SelectItem>
                                ) : lxcTemplates && lxcTemplates.length > 0 ? (
                                  lxcTemplates.map((template) => (
                                    <SelectItem
                                      key={template.volid}
                                      value={template.volid}
                                    >
                                      {template.volid
                                        .split("/")
                                        .pop()
                                        ?.replace(".tar.zst", "")}
                                    </SelectItem>
                                  ))
                                ) : (
                                  <SelectItem value="none" disabled>
                                    無可用模板
                                  </SelectItem>
                                )}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="os_info"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>作業系統資訊（選填）</FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：Ubuntu 22.04 LTS"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="password"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              Root 密碼{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="設置 root 使用者密碼"
                                type="password"
                                {...field}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="expiry_date"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              到期日（選填，留空表示無期限）
                            </FormLabel>
                            <FormControl>
                              <Input type="date" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <div className="space-y-6 border rounded-lg p-4">
                        <h3 className="font-medium">硬體資源配置</h3>

                        <FormField
                          control={form.control}
                          name="cores"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>CPU 核心數</FormLabel>
                                <span className="text-sm font-semibold text-primary">
                                  {field.value} Cores
                                </span>
                              </div>
                              <FormControl>
                                <Slider
                                  min={1}
                                  max={8}
                                  step={1}
                                  value={[field.value]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <div className="flex justify-between text-xs text-muted-foreground">
                                <span>1</span>
                                <span>2</span>
                                <span>4</span>
                                <span>8</span>
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="memory"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>記憶體 (RAM)</FormLabel>
                                <span className="text-sm font-semibold text-primary">
                                  {(field.value / 1024).toFixed(1)} GB
                                </span>
                              </div>
                              <FormControl>
                                <Slider
                                  min={512}
                                  max={32768}
                                  step={512}
                                  value={[field.value]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <div className="flex justify-between text-xs text-muted-foreground">
                                <span>1GB</span>
                                <span>8GB</span>
                                <span>16GB</span>
                                <span>32GB</span>
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="rootfs_size"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>硬碟空間 (Disk)</FormLabel>
                                <div className="flex items-center gap-2">
                                  <Input
                                    type="number"
                                    min={8}
                                    max={500}
                                    value={field.value}
                                    onChange={(e) =>
                                      field.onChange(
                                        Number.parseInt(e.target.value, 10) ||
                                          20,
                                      )
                                    }
                                    className="w-20 h-8 text-right"
                                  />
                                  <span className="text-sm font-semibold text-primary">
                                    GB
                                  </span>
                                </div>
                              </div>
                              <FormControl>
                                <Slider
                                  min={8}
                                  max={500}
                                  step={1}
                                  value={[field.value || 20]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>
                    </div>
                  </TabsContent>

                  {/* VM Form */}
                  <TabsContent value="vm" className="space-y-4 mt-4">
                    <div className="grid gap-4">
                      <FormField
                        control={form.control}
                        name="hostname"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              虛擬機名稱{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：web-server-01"
                                {...field}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="template_id"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              作業系統{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <Select
                              onValueChange={(value) =>
                                field.onChange(Number.parseInt(value, 10))
                              }
                              value={field.value?.toString()}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="選擇作業系統" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {vmTemplatesLoading ? (
                                  <SelectItem value="loading" disabled>
                                    載入中...
                                  </SelectItem>
                                ) : vmTemplates && vmTemplates.length > 0 ? (
                                  vmTemplates.map((template) => (
                                    <SelectItem
                                      key={template.vmid}
                                      value={template.vmid.toString()}
                                    >
                                      {template.name}
                                    </SelectItem>
                                  ))
                                ) : (
                                  <SelectItem value="none" disabled>
                                    無可用作業系統
                                  </SelectItem>
                                )}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="os_info"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>作業系統資訊（選填）</FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：Ubuntu 22.04 LTS"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="username"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              使用者名稱{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：admin"
                                {...field}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="password"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              密碼 <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="設置使用者密碼"
                                type="password"
                                {...field}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="expiry_date"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              到期日（選填，留空表示無期限）
                            </FormLabel>
                            <FormControl>
                              <Input type="date" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <div className="space-y-6 border rounded-lg p-4">
                        <h3 className="font-medium">硬體資源配置</h3>

                        <FormField
                          control={form.control}
                          name="cores"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>CPU 核心數</FormLabel>
                                <span className="text-sm font-semibold text-primary">
                                  {field.value} Cores
                                </span>
                              </div>
                              <FormControl>
                                <Slider
                                  min={1}
                                  max={8}
                                  step={1}
                                  value={[field.value]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <div className="flex justify-between text-xs text-muted-foreground">
                                <span>1</span>
                                <span>2</span>
                                <span>4</span>
                                <span>8</span>
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="memory"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>記憶體 (RAM)</FormLabel>
                                <span className="text-sm font-semibold text-primary">
                                  {(field.value / 1024).toFixed(1)} GB
                                </span>
                              </div>
                              <FormControl>
                                <Slider
                                  min={512}
                                  max={32768}
                                  step={512}
                                  value={[field.value]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <div className="flex justify-between text-xs text-muted-foreground">
                                <span>1GB</span>
                                <span>8GB</span>
                                <span>16GB</span>
                                <span>32GB</span>
                              </div>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="disk_size"
                          render={({ field }) => (
                            <FormItem>
                              <div className="flex items-center justify-between">
                                <FormLabel>硬碟空間 (Disk)</FormLabel>
                                <div className="flex items-center gap-2">
                                  <Input
                                    type="number"
                                    min={20}
                                    max={500}
                                    value={field.value}
                                    onChange={(e) =>
                                      field.onChange(
                                        Number.parseInt(e.target.value, 10) ||
                                          20,
                                      )
                                    }
                                    className="w-20 h-8 text-right"
                                  />
                                  <span className="text-sm font-semibold text-primary">
                                    GB
                                  </span>
                                </div>
                              </div>
                              <FormControl>
                                <Slider
                                  min={20}
                                  max={500}
                                  step={1}
                                  value={[field.value || 20]}
                                  onValueChange={(vals) =>
                                    field.onChange(vals[0])
                                  }
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </TabsContent>
            </Tabs>

            <div className="mt-4">
              <FormField
                control={form.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      申請原因 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="請詳細說明申請此虛擬機/容器的用途與原因..."
                        className="min-h-[100px]"
                        {...field}
                        required
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter className="mt-6">
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                提交申請
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default CreateVMRequest
