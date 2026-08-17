import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function hasPermission(permissions: string[] | undefined, required?: string): boolean {
  if (!required) return true;
  if (!permissions || permissions.length === 0) return false;
  if (permissions.includes('all')) return true;
  return permissions.includes(required);
}

export function initials(name: string): string {
  if (!name) return 'U';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
