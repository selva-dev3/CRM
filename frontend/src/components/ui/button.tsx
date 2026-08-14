import * as React from "react";
import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-btn text-button transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]/30 disabled:pointer-events-none disabled:opacity-50 cursor-pointer active:scale-[0.99]",
  {
    variants: {
      variant: {
        default:
          "bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-saas-sm",
        primary:
          "bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-saas-sm",
        secondary:
          "bg-[#F3F4F6] text-text-secondary hover:bg-[#E5E7EB]",
        outline:
          "border border-[#E5E7EB] bg-white hover:bg-[#F9FAFB] text-text-secondary shadow-saas-sm",
        ghost:
          "hover:bg-[#F3F4F6] text-text-muted hover:text-text-primary",
        danger:
          "bg-[#DC2626] text-white hover:bg-[#B91C1C] shadow-saas-sm",
        destructive:
          "bg-[#DC2626] text-white hover:bg-[#B91C1C] shadow-saas-sm",
        link:
          "text-[#2563EB] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2 text-button",
        xs: "h-7 rounded-btn px-2 text-caption font-medium",
        sm: "h-8 rounded-btn px-3 text-caption font-medium",
        lg: "h-12 rounded-btn px-6 text-subheading font-medium",
        icon: "h-9 w-9 text-button",
        "icon-xs": "h-7 w-7 text-button",
        "icon-sm": "h-8 w-8 text-button",
        "icon-lg": "h-10 w-10 text-button",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot.Root : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
