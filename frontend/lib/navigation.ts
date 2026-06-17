import { Activity, Bot, CalendarRange, Dumbbell, History, LayoutDashboard, LineChart, UserCircle, type LucideIcon } from "lucide-react"

export interface NavItem {
  label: string
  href: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Training Plans", href: "/plans", icon: CalendarRange },
  { label: "Current Workout", href: "/workouts/current", icon: Dumbbell },
  { label: "Workout History", href: "/workouts/history", icon: History },
  { label: "Analytics", href: "/analytics", icon: LineChart },
  { label: "Weekly Reports", href: "/reports", icon: Activity },
  { label: "AI Coach", href: "/coach", icon: Bot },
  { label: "Fitness Profile", href: "/profile", icon: UserCircle },
]
