"use client"

import { Fragment, type MouseEvent, type ReactNode } from "react"
import { ChevronDown, MoreHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useHasPermission } from "@/hooks/use-has-permission"
import { cn } from "@/lib/utils"
import type { PermissionKey } from "@/lib/permissions"

export interface ActionMenuAction {
  readonly label: string
  readonly onSelect: () => void
  readonly icon?: ReactNode
  readonly variant?: "default" | "destructive"
  readonly permission?: PermissionKey
  readonly disabled?: boolean
}

interface ActionMenuProps {
  readonly actions: readonly ActionMenuAction[]
  readonly label?: string
  readonly menuLabel?: string
  readonly iconOnly?: boolean
  readonly align?: "start" | "center" | "end"
  readonly className?: string
  readonly contentClassName?: string
  readonly onTriggerClick?: (event: MouseEvent<HTMLButtonElement>) => void
}

export function ActionMenu({
  actions,
  label = "More actions",
  menuLabel,
  iconOnly = false,
  align = "end",
  className,
  contentClassName,
  onTriggerClick,
}: ActionMenuProps): React.JSX.Element | null {
  const { hasPermission } = useHasPermission()
  const visibleActions = actions.filter((action) => hasPermission(action.permission))

  if (visibleActions.length === 0) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size={iconOnly ? "icon-lg" : "default"}
          className={cn("gap-2", className)}
          aria-label={iconOnly ? label : undefined}
          onClick={onTriggerClick}
        >
          {iconOnly ? <MoreHorizontal className="size-4" /> : <><span>{label}</span><ChevronDown className="size-4" /></>}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className={cn("w-48", contentClassName)}>
        {menuLabel && (
          <>
            <DropdownMenuLabel>{menuLabel}</DropdownMenuLabel>
            <DropdownMenuSeparator />
          </>
        )}
        {visibleActions.map((action, index) => (
          <Fragment key={action.label}>
            {action.variant === "destructive" && index > 0 && visibleActions[index - 1]?.variant !== "destructive" && (
              <DropdownMenuSeparator />
            )}
            <DropdownMenuItem
              variant={action.variant}
              disabled={action.disabled}
              onSelect={(event) => {
                event.stopPropagation()
                action.onSelect()
              }}
            >
              {action.icon}
              <span>{action.label}</span>
            </DropdownMenuItem>
          </Fragment>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
