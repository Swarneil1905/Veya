export function reviewTiming(expiresAt: number, now = Date.now()): string {
  const remaining = expiresAt * 1000 - now;
  if (remaining <= 0) return 'Expired — request a fresh review';
  if (remaining < 3600000) return `Expires in ${Math.max(1, Math.ceil(remaining / 60000))} min`;
  return `Expires ${new Date(expiresAt * 1000).toLocaleString()}`;
}
