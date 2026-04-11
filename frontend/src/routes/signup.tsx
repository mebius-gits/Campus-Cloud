import {
  createFileRoute,
  redirect,
} from "@tanstack/react-router"
import { isLoggedIn } from "@/hooks/useAuth"
import { SignUpPage } from "@/components/Auth/SignUpPage"

export const Route = createFileRoute("/signup")({
  component: SignUpPage,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Sign Up - Campus Cloud",
      },
    ],
  }),
})
