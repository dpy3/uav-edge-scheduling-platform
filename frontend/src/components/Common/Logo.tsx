import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <span className={cn("font-semibold group-data-[collapsible=icon]:hidden", className)}>UAV Edge Lab</span>
        <span className={cn("hidden size-6 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground group-data-[collapsible=icon]:flex", className)}>U</span>
      </>
    ) : (
      <span className={cn(variant === "full" ? "font-semibold" : "inline-flex size-6 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground", className)}>{variant === "full" ? "UAV Edge Lab" : "U"}</span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
