import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query"

import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import { ArrowLeft, Plus, UserMinus } from "lucide-react"
import { Suspense, useState } from "react"
import { useForm } from "react-hook-form"

import { GroupsService, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/groups_/$groupId")({
  component: GroupDetailPage,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!(user.role === "admin" || user.is_superuser)) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "群組詳情 - Campus Cloud" }],
  }),
})

function AddMembersDialog({ groupId }: { groupId: string }) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { register, handleSubmit, reset } = useForm<{ emailsText: string }>()

  const mutation = useMutation({
    mutationFn: (emails: string[]) =>
      GroupsService.addMembers({ groupId, requestBody: { emails } }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["group", groupId] })
      if (data.message.includes("Not found:")) {
        showErrorToast(data.message)
      } else {
        showSuccessToast(data.message)
        reset()
        setOpen(false)
      }
    },
    onError: (err: any) =>
      showErrorToast(err?.body?.detail ?? "加入成員失敗"),
  })

  const onSubmit = ({ emailsText }: { emailsText: string }) => {
    const emails = emailsText
      .split(/[\n,]/)
      .map((e) => e.trim())
      .filter(Boolean)
    mutation.mutate(emails)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="mr-1 h-4 w-4" />
          加入成員
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>加入成員</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Email 列表（每行一個或逗號分隔）</Label>
              <Textarea
                {...register("emailsText", { required: true })}
                placeholder={"student1@example.com\nstudent2@example.com"}
                rows={6}
              />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>取消</Button>
            </DialogClose>
            <LoadingButton type="submit" loading={mutation.isPending}>加入</LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}


function GroupDetailContent({ groupId }: { groupId: string }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: group } = useSuspenseQuery({
    queryKey: ["group", groupId],
    queryFn: () => GroupsService.getGroup({ groupId }),
  })
  const members = group.members ?? []

  const removeMutation = useMutation({
    mutationFn: (userId: string) =>
      GroupsService.removeMember({ groupId, userId }),
    onSuccess: () => {
      showSuccessToast("成員已移除")
      queryClient.invalidateQueries({ queryKey: ["group", groupId] })
    },
    onError: (err: any) =>
      showErrorToast(err?.body?.detail ?? "移除失敗"),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/groups" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <h1 className="text-2xl font-bold tracking-tight">{group.name}</h1>
          </div>
          {group.description && (
            <p className="text-muted-foreground">{group.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <AddMembersDialog groupId={groupId} />
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">成員列表（{members.length} 人）</h2>
        {members.length === 0 ? (
          <p className="text-muted-foreground text-sm">尚無成員，點擊「加入成員」開始新增</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>姓名</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>加入時間</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.user_id}>
                  <TableCell>{member.full_name ?? "-"}</TableCell>
                  <TableCell>{member.email}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {member.added_at ? new Date(member.added_at).toLocaleDateString("zh-TW") : "-"}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:text-destructive"
                      onClick={() => removeMutation.mutate(member.user_id)}
                      disabled={removeMutation.isPending}
                    >
                      <UserMinus className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

function GroupDetailPage() {
  const { groupId } = Route.useParams()
  return (
    <Suspense fallback={<div className="text-muted-foreground">載入中…</div>}>
      <GroupDetailContent groupId={groupId} />
    </Suspense>
  )
}
