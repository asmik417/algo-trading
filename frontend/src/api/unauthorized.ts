// "The session is gone" signal. The axios client and the mock layer call notify; the auth store listens.
// Kept in its own file so the mock layer does not depend on the axios client.
let handler: (() => void) | null = null;

export function setUnauthorizedHandler(next: (() => void) | null): void {
  handler = next;
}

export function notifyUnauthorized(): void {
  handler?.();
}
