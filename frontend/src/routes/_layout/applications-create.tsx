import { createFileRoute } from "@tanstack/react-router"

import { ApplicationRequestPage } from "@/components/Applications/ApplicationRequestPage"
import { requireStudentUser } from "@/features/auth/guards"

export const Route = createFileRoute("/_layout/applications-create")({
  component: ApplicationsCreateRoute,
  beforeLoad: () => requireStudentUser({ redirectTo: "/applications" }),
  head: () => ({
    meta: [
      {
        title: "Request Resource - Campus Cloud",
      },
    ],
  }),
})

function ApplicationsCreateRoute() {
  return <ApplicationRequestPage />
}
