'use client';

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface DropdownContextType {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
  value?: string;
  onValueChange?: (val: string) => void;
}

const DropdownContext = React.createContext<DropdownContextType>({
  open: false,
  setOpen: () => {},
  triggerRef: { current: null },
});

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        !(target instanceof Element && target.closest('[data-dropdown-content]'))
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <DropdownContext.Provider value={{ open, setOpen, triggerRef }}>
      <div ref={containerRef} className="relative inline-block text-left">
        {children}
      </div>
    </DropdownContext.Provider>
  );
}

export function DropdownMenuTrigger({
  children,
  className,
  onClick,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { open, setOpen, triggerRef } = React.useContext(DropdownContext);
  return (
    <button
      ref={triggerRef}
      type="button"
      onClick={(e) => {
        setOpen(!open);
        onClick?.(e);
      }}
      className={cn("inline-flex items-center justify-center font-bold transition focus:outline-none", className)}
      {...props}
    >
      {children}
    </button>
  );
}

export function DropdownMenuContent({
  children,
  className,
  align = "end",
  side = "auto",
}: {
  children: React.ReactNode;
  className?: string;
  align?: "start" | "end" | "center";
  side?: "top" | "bottom" | "auto";
}) {
  const { open, triggerRef } = React.useContext(DropdownContext);
  const contentRef = React.useRef<HTMLDivElement>(null);
  const [coords, setCoords] = React.useState<{ top: number; left?: number; right?: number; isTop?: boolean } | null>(null);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;

    const updatePosition = () => {
      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;

      const spaceBelow = viewportHeight - rect.bottom;
      const isTop = side === "top" || (side === "auto" && spaceBelow < 180 && rect.top > spaceBelow);
      const top = isTop ? rect.top - 4 : rect.bottom + 4;

      if (align === "end") {
        const right = Math.max(10, viewportWidth - rect.right);
        setCoords({ top, right, isTop });
      } else if (align === "center") {
        const left = Math.max(10, rect.left + rect.width / 2);
        setCoords({ top, left, isTop });
      } else {
        const left = Math.max(10, rect.left);
        setCoords({ top, left, isTop });
      }
    };

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [open, align, side, triggerRef]);

  if (!open || !mounted || !coords) return null;

  return createPortal(
    <div
      ref={contentRef}
      data-dropdown-content="true"
      style={{
        position: "fixed",
        top: `${coords.top}px`,
        ...(coords.isTop ? { transform: "translateY(-100%)" } : {}),
        ...(coords.right !== undefined ? { right: `${coords.right}px` } : {}),
        ...(coords.left !== undefined ? { left: `${coords.left}px` } : {}),
        zIndex: 99999,
      }}
      className={cn(
        "min-w-[9.5rem] rounded-dropdown border border-[#E5E7EB] bg-white p-1 text-text-primary shadow-saas-lg animate-in fade-in-50",
        align === "center" ? "-translate-x-1/2" : undefined,
        className
      )}
    >
      {children}
    </div>,
    document.body
  );
}

export function DropdownMenuItem({
  children,
  className,
  onClick,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { setOpen } = React.useContext(DropdownContext);
  return (
    <button
      type="button"
      onClick={(e) => {
        onClick?.(e);
        setOpen(false);
      }}
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-btn px-3 py-2 text-button font-medium text-text-secondary hover:bg-[#F3F4F6] hover:text-text-primary transition-all",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function DropdownMenuLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("px-3 py-1.5 text-badge font-semibold", className)}>{children}</div>;
}

export function DropdownMenuSeparator({ className }: { className?: string }) {
  return <div className={cn("-mx-1 my-1 h-px bg-[#E5E7EB]", className)} />;
}

export function DropdownMenuCheckboxItem({
  children,
  checked,
  onCheckedChange,
  onClick,
  className,
}: {
  children: React.ReactNode;
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  className?: string;
}) {
  const { setOpen } = React.useContext(DropdownContext);
  return (
    <button
      type="button"
      onClick={(e) => {
        onCheckedChange?.(!checked);
        onClick?.(e);
        setOpen(false);
      }}
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-900 hover:bg-slate-100 transition",
        className
      )}
    >
      <input type="checkbox" checked={!!checked} readOnly className="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
      <span>{children}</span>
    </button>
  );
}

export function DropdownMenuRadioGroup({
  children,
  value,
  onValueChange,
}: {
  children: React.ReactNode;
  value?: string;
  onValueChange?: (val: string) => void;
}) {
  const parent = React.useContext(DropdownContext);
  return (
    <DropdownContext.Provider value={{ ...parent, value, onValueChange }}>
      <div className="space-y-0.5">{children}</div>
    </DropdownContext.Provider>
  );
}

export function DropdownMenuRadioItem({
  children,
  value,
  className,
}: {
  children: React.ReactNode;
  value: string;
  className?: string;
}) {
  const { value: selectedValue, onValueChange, setOpen } = React.useContext(DropdownContext);
  const isSelected = selectedValue === value;
  return (
    <button
      type="button"
      onClick={() => {
        onValueChange?.(value);
        setOpen(false);
      }}
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-900 hover:bg-slate-100 transition",
        isSelected && "bg-slate-100 font-black text-indigo-600",
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full bg-current", isSelected ? "opacity-100" : "opacity-0")} />
      <span>{children}</span>
    </button>
  );
}
