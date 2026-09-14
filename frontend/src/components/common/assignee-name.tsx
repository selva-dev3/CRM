'use client';

import { useUserQuery, type UserItem } from '@/lib/api/users';

interface AssigneeNameProps {
  userId?: string;
  knownUsers?: UserItem[];
}

export function AssigneeName({ userId, knownUsers = [] }: AssigneeNameProps) {
  const knownUser = userId
    ? knownUsers.find((user) => user.id === userId || user.email === userId || user.name === userId)
    : undefined;
  const shouldFetch = Boolean(userId) && !knownUser;
  const { data: fetchedUser, isLoading, isError } = useUserQuery(userId ?? '', {
    enabled: shouldFetch,
  });

  if (!userId) return <>Unassigned</>;
  if (knownUser) return <>{knownUser.name}</>;
  if (isLoading) return <>Loading assignee…</>;
  if (isError) return <>Unable to load assignee</>;
  return <>{fetchedUser?.name ?? 'Unknown user'}</>;
}
