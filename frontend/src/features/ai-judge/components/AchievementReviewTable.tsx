/**
 * AchievementReviewTable - Read-only review table for achievement status
 */

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

import type { RubricItem } from "../api"
import { getCheckedInfo, getDetectableInfo } from "../api"

type AchievementReviewTableProps = {
  items: RubricItem[]
}

export function AchievementReviewTable({ items }: AchievementReviewTableProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
        尚無可顯示的審核項目
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-14">#</TableHead>
          <TableHead>項目</TableHead>
          <TableHead className="w-28">達成狀態</TableHead>
          <TableHead className="w-32">偵測性</TableHead>
          <TableHead>偵測方式</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item, index) => {
          const checkedInfo = getCheckedInfo(item.checked)
          const detectableInfo = getDetectableInfo(item.detectable)

          return (
            <TableRow key={item.id}>
              <TableCell className="text-muted-foreground">{index + 1}</TableCell>
              <TableCell className="whitespace-normal">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{item.title}</p>
                  {item.description && (
                    <p className="text-xs text-muted-foreground">{item.description}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <span
                  className={cn(
                    "rounded-md border px-2 py-1 text-xs font-medium",
                    checkedInfo.className,
                  )}
                >
                  {checkedInfo.label}
                </span>
              </TableCell>
              <TableCell>
                <span
                  className={cn(
                    "rounded-md px-2 py-1 text-xs font-medium",
                    detectableInfo.className,
                  )}
                >
                  {detectableInfo.label}
                </span>
              </TableCell>
              <TableCell className="whitespace-normal text-xs text-muted-foreground">
                {item.detection_method || "-"}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
