import {
  ClipboardCheck,
  FileText,
  Home,
  Monitor,
  ServerCog,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: ServerCog, title: "My Resources", path: "/my-resources" },
  { icon: FileText, title: "Applications", path: "/applications" },
]

const adminItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: ServerCog, title: "My Resources", path: "/my-resources" },
  { icon: Monitor, title: "Resources", path: "/resources" },
  { icon: ClipboardCheck, title: "Approvals", path: "/approvals" },
  { icon: Users, title: "Admin", path: "/admin" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser ? adminItems : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
