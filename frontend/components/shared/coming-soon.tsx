import type { LucideIcon } from "lucide-react"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"

export function ComingSoon({
  title,
  description,
  icon,
  feature,
}: {
  title: string
  description: string
  icon: LucideIcon
  feature: string
}) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={icon}
        title={`${feature} are coming soon`}
        description={`We're putting the finishing touches on ${feature.toLowerCase()}. Check back shortly to see this part of FitPilot come to life.`}
      />
    </div>
  )
}
