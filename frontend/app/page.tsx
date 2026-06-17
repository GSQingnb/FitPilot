import { redirect } from "next/navigation"

export default function HomePage() {
  // The app shell handles auth; unauthenticated users are bounced to /login.
  redirect("/dashboard")
}
