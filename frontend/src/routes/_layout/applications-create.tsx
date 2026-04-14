import { createFileRoute } from "@tanstack/react-router"

import { ApplicationRequestPage } from "@/components/Applications/ApplicationRequestPage"
import { requireApplicationUser } from "@/features/auth/guards"

export const Route = createFileRoute("/_layout/applications-create")({
  component: ApplicationsCreateRoute,
  beforeLoad: () => requireApplicationUser({ redirectTo: "/applications" }),
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
