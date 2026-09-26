/** Only same-site paths are allowed as redirect targets (prevents open redirects). */
export function safeNext(value: string | null, fallback: string): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : fallback;
}
