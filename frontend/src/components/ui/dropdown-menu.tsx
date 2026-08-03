'use client';

import * as React from "react";
import { cn } from "@/lib/utils";

interface DropdownContextType {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  value?: string;
  onValueChange?: (val: string) => void;
}

const DropdownContext = React.createContext<DropdownContextType>({
  open: false,
  setOpen: () => {},
});

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <DropdownContext.Provider value={{ open, setOpen }}>
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
  const { open, setOpen } = React.useContext(DropdownContext);
  return (
    <button
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
}: {
  children: React.ReactNode;
  className?: string;
  align?: "start" | "end" | "center";
}) {
  const { open } = React.useContext(DropdownContext);
  if (!open) return null;

  const alignClass =
    align === "start" ? "left-0" : align === "center" ? "left-1/2 -translate-x-1/2" : "right-0";

  return (
    <div
      className={cn(
        "absolute z-50 mt-1 min-w-[8rem] overflow-hidden rounded-xl border border-slate-200 bg-white p-1 text-slate-900 shadow-lg animate-in fade-in-50",
        alignClass,
        className
      )}
    >
      {children}
    </div>
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
        "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-900 hover:bg-slate-100 transition",
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
  return <div className={cn("px-2.5 py-1.5 text-xs font-black text-slate-700", className)}>{children}</div>;
}

export function DropdownMenuSeparator({ className }: { className?: string }) {
  return <div className={cn("-mx-1 my-1 h-px bg-slate-200", className)} />;
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
