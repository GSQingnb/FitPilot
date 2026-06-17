"use client"

import { useMemo, useState, type FormEvent } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AlertCircle, Check, Eye, EyeOff, Loader2, X } from "lucide-react"
import { useAuth } from "@/components/auth/auth-provider"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface FieldErrors {
  displayName?: string
  email?: string
  password?: string
  confirmPassword?: string
}

function passwordChecks(password: string) {
  return [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "One uppercase letter", met: /[A-Z]/.test(password) },
    { label: "One lowercase letter", met: /[a-z]/.test(password) },
    { label: "One number", met: /\d/.test(password) },
  ]
}

export function RegisterForm() {
  const router = useRouter()
  const { signUp } = useAuth()

  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const checks = useMemo(() => passwordChecks(password), [password])
  const passwordValid = checks.every((c) => c.met)

  function validate(): boolean {
    const next: FieldErrors = {}
    if (!displayName.trim()) next.displayName = "Display name is required."
    else if (displayName.trim().length < 2)
      next.displayName = "Display name is too short."
    if (!email.trim()) next.email = "Email is required."
    else if (!EMAIL_RE.test(email)) next.email = "Enter a valid email address."
    if (!password) next.password = "Password is required."
    else if (!passwordValid)
      next.password = "Password does not meet the requirements."
    if (!confirmPassword) next.confirmPassword = "Please confirm your password."
    else if (confirmPassword !== password)
      next.confirmPassword = "Passwords do not match."
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setIsSubmitting(true)
    try {
      // TODO(FastAPI): signUp calls POST /auth/register via lib/mock-api.ts.
      await signUp({ displayName: displayName.trim(), email, password })
      router.replace("/dashboard")
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setErrors((prev) => ({ ...prev, email: err.message }))
        } else {
          setFormError(err.message)
        }
      } else {
        setFormError("Unable to create your account. Please try again.")
      }
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      {formError && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Registration failed</AlertTitle>
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}

      <FieldGroup>
        <Field data-invalid={errors.displayName ? true : undefined}>
          <FieldLabel htmlFor="displayName">Display name</FieldLabel>
          <Input
            id="displayName"
            autoComplete="name"
            placeholder="Jordan Hayes"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            aria-invalid={errors.displayName ? true : undefined}
            disabled={isSubmitting}
          />
          {errors.displayName && <FieldError>{errors.displayName}</FieldError>}
        </Field>

        <Field data-invalid={errors.email ? true : undefined}>
          <FieldLabel htmlFor="register-email">Email</FieldLabel>
          <Input
            id="register-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={errors.email ? true : undefined}
            disabled={isSubmitting}
          />
          {errors.email && <FieldError>{errors.email}</FieldError>}
        </Field>

        <Field data-invalid={errors.password ? true : undefined}>
          <FieldLabel htmlFor="register-password">Password</FieldLabel>
          <div className="relative">
            <Input
              id="register-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Create a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={errors.password ? true : undefined}
              disabled={isSubmitting}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? (
                <EyeOff className="size-4" />
              ) : (
                <Eye className="size-4" />
              )}
            </button>
          </div>
          <ul className="mt-1 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {checks.map((check) => (
              <li
                key={check.label}
                className={cn(
                  "flex items-center gap-1.5 text-xs",
                  check.met ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {check.met ? (
                  <Check className="size-3.5 text-primary" aria-hidden="true" />
                ) : (
                  <X className="size-3.5" aria-hidden="true" />
                )}
                {check.label}
              </li>
            ))}
          </ul>
          {errors.password && <FieldError>{errors.password}</FieldError>}
        </Field>

        <Field data-invalid={errors.confirmPassword ? true : undefined}>
          <FieldLabel htmlFor="confirmPassword">Confirm password</FieldLabel>
          <Input
            id="confirmPassword"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            aria-invalid={errors.confirmPassword ? true : undefined}
            disabled={isSubmitting}
          />
          {errors.confirmPassword && (
            <FieldError>{errors.confirmPassword}</FieldError>
          )}
        </Field>
      </FieldGroup>

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting && (
          <Loader2 data-icon="inline-start" className="animate-spin" />
        )}
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </form>
  )
}
