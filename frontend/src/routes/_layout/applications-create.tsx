import { createFileRoute } from "@tanstack/react-router"

import { ApplicationRequestPage } from "@/components/Applications/ApplicationRequestPage"

export const Route = createFileRoute("/_layout/applications-create")({
  component: ApplicationsCreateRoute,
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
