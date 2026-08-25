import * as React from "react"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"
import { Separator } from "@/components/ui/separator"

function ButtonGroup({ className, orientation = "horizontal", ...props }: React.ComponentProps<"div"> & { orientation?: "horizontal" | "vertical" }) {
  return (
    <div
      role="group"
      data-slot="button-group"
      data-orientation={orientation}
      className={cn(
        "flex w-fit items-stretch [&>*]:focus-visible:relative [&>*]:focus-visible:z-10",
        "data-[orientation=horizontal]:[&>*:not(:first-child)]:rounded-l-none data-[orientation=horizontal]:[&>*:not(:first-child)]:border-l-0 data-[orientation=horizontal]:[&>*:not(:last-child)]:rounded-r-none",
        "data-[orientation=vertical]:flex-col data-[orientation=vertical]:[&>*:not(:first-child)]:rounded-t-none data-[orientation=vertical]:[&>*:not(:first-child)]:border-t-0 data-[orientation=vertical]:[&>*:not(:last-child)]:rounded-b-none",
        className,
      )}
      {...props}
    />
  )
}

function ButtonGroupText({ className, asChild = false, ...props }: React.ComponentProps<"div"> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "div"
  return <Comp data-slot="button-group-text" className={cn("flex items-center gap-2 border border-[#E5E7EB] bg-white px-4 text-button font-medium text-text-secondary", className)} {...props} />
}

function ButtonGroupSeparator({ className, orientation = "vertical", ...props }: React.ComponentProps<typeof Separator>) {
  return <Separator data-slot="button-group-separator" orientation={orientation} className={cn("relative z-10 self-stretch bg-[#E5E7EB] data-[orientation=vertical]:h-auto", className)} {...props} />
}

export { ButtonGroup, ButtonGroupSeparator, ButtonGroupText }
