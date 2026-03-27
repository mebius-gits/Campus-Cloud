import { Link } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

const CreateVMRequest = () => {
  const { t } = useTranslation("applications")

  return (
    <Button asChild>
      <Link to="/applications-create">
        <Plus className="h-4 w-4" />
        {t("create.title")}
      </Link>
    </Button>
  )
}

export default CreateVMRequest
