import type { Metadata } from "next"
import { AuthShell } from "@/components/auth/auth-shell"
import { RegisterForm } from "@/components/auth/register-form"

export const metadata: Metadata = {
  title: "Create account — FitPilot",
}

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create your account"
      subtitle="Start building AI-powered training plans in minutes."
    >
      <RegisterForm />
    </AuthShell>
  )
}
