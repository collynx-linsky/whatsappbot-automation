// WABA AI — Centralized error-message extraction
//
// The pattern `err instanceof ApiError ? err.message : "some fallback"`
// was repeated ~49 times across every page's catch block — correct and
// consistent every time, but mechanical duplication that's easy to get
// subtly wrong once (e.g. forgetting the `instanceof` check and rendering
// "[object Object]"). One helper, one place to get it right.
//
// Deliberately does NOT change what's shown: a real ApiError still shows
// its real server message (already human-readable — see the backend's
// exception handler), anything else still falls back to the caller's own
// fallback text. Never exposes a raw stack trace or error.toString().
import { ApiError } from "./api";

export function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}
