import type { CSSProperties } from 'react';
import { cn, initials } from '@/lib/utils';
import { Avatar as UiAvatar, AvatarFallback } from '@/components/ui/avatar';

interface AvatarProps {
  readonly name: string;
  readonly color?: string;
  readonly size?: 'sm' | 'md' | 'lg';
  readonly className?: string;
}

export function Avatar({ name, color, size = 'md', className }: AvatarProps): React.JSX.Element {
  const sizeMap = {
    sm: 'size-6 text-[11px]',
    md: 'size-7 text-xs',
    lg: 'size-14 rounded-xl text-xl',
  } as const;

  return (
    <UiAvatar className={cn(sizeMap[size], className)}>
      <AvatarFallback
        className="bg-indigo-600 font-bold text-white"
        style={{ '--avatar-color': color ?? 'var(--muted-foreground)' } as CSSProperties}
      >
        {initials(name)}
      </AvatarFallback>
    </UiAvatar>
  );
}
