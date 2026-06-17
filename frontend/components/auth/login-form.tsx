"use client"

import { useState, type FormEvent } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AlertCircle, Eye, EyeOff, Loader2 } from "lucide-react"
import { useAuth } from "@/components/auth/auth-provider"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface FieldErrors {
  email?: string
  password?: string
}

export function LoginForm() {
  const router = useRouter()
  const { signIn } = useAuth()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [rememberMe, setRememberMe] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(): boolean {
    const next: FieldErrors = {}
    if (!email.trim()) next.email = "Email is required."
    else if (!EMAIL_RE.test(email)) next.email = "Enter a valid email address."
    if (!password) next.password = "Password is required."
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setIsSubmitting(true)
    try {
      // TODO(FastAPI): signIn calls POST /auth/login via lib/mock-api.ts.
      await signIn({ email, password })
      router.replace("/dashboard")
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message)
      } else {
        setFormError("Unable to sign in right now. Please try again.")
      }
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      {formError && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Sign in failed</AlertTitle>
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}

      <FieldGroup>
        <Field data-invalid={errors.email ? true : undefined}>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Input
            id="email"
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
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Enter your password"
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
          {errors.password && <FieldError>{errors.password}</FieldError>}
        </Field>

        <div className="flex items-center gap-2">
          <Checkbox
            id="remember"
            checked={rememberMe}
            onCheckedChange={(checked) => setRememberMe(checked === true)}
            disabled={isSubmitting}
          />
          <Label htmlFor="remember" className="text-sm font-normal">
            Remember me on this device
          </Label>
        </div>
      </FieldGroup>

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting && <Loader2 data-icon="inline-start" className="animate-spin" />}
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Create one
        </Link>
      </p>
    </form>
  )
}
