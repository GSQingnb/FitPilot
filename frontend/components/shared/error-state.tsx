import { AlertTriangle, RotateCcw } from "lucide-react"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  title?: string
  description?: string
  /** When provided, renders a retry button. */
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  title = "Something went wrong",
  description = "We couldn't load this content. Please try again.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <Empty className={className}>
      <EmptyHeader>
        <EmptyMedia variant="icon" className="text-destructive">
          <AlertTriangle aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {onRetry && (
        <EmptyContent>
          <Button variant="outline" onClick={onRetry}>
            <RotateCcw data-icon="inline-start" />
            Try again
          </Button>
        </EmptyContent>
      )}
    </Empty>
  )
}
