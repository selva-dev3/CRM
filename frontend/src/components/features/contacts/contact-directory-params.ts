export function updateContactDirectoryParams(
  current: string,
  changes: Record<string, string | null>,
): string {
  const params = new URLSearchParams(current);
  Object.entries(changes).forEach(([key, value]) => {
    if (!value || (key === 'page' && value === '1')) params.delete(key);
    else params.set(key, value);
  });
  return params.toString();
}
