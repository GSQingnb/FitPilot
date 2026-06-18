import Link from "next/link"

export default function NotFoundPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-muted-foreground">Page not found</p>
      <Link href="/dashboard" className="text-lime-600 hover:underline">
        Go to Dashboard
      </Link>
    </div>
  )
}
