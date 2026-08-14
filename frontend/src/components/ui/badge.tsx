import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-badge font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-[#2563EB]/20 bg-[#2563EB]/10 text-[#2563EB]",
        secondary:
          "border-[#E5E7EB] bg-[#F3F4F6] text-text-secondary",
        destructive:
          "border-[#DC2626]/20 bg-[#DC2626]/10 text-[#DC2626]",
        danger:
          "border-[#DC2626]/20 bg-[#DC2626]/10 text-[#DC2626]",
        success:
          "border-[#16A34A]/20 bg-[#16A34A]/10 text-[#16A34A]",
        warning:
          "border-[#F59E0B]/20 bg-[#F59E0B]/10 text-[#D97706]",
        outline: "text-text-secondary border-[#E5E7EB] bg-white",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
