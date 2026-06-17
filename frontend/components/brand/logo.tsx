import { Dumbbell } from "lucide-react"
import { cn } from "@/lib/utils"

interface LogoProps {
  /** Hide the wordmark and show only the mark. */
  iconOnly?: boolean
  className?: string
}

/** FitPilot brand mark + wordmark. */
export function Logo({ iconOnly = false, className }: LogoProps) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Dumbbell className="size-5" aria-hidden="true" />
      </span>
      {!iconOnly && (
        <span className="text-lg font-semibold tracking-tight text-foreground">
          FitPilot
        </span>
      )}
    </span>
  )
}
