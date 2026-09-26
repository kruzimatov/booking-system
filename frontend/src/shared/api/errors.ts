interface ErrorBody {
  error?: { code?: string; message?: string; details?: { fields?: Record<string, string> } };
}

/** Every non-2xx response from the API has the same envelope; this is its client-side form. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;

  constructor(status: number, body: unknown) {
    const error = (body as ErrorBody | undefined)?.error;
    super(error?.message ?? "Something went wrong. Please try again.");
    this.status = status;
    this.code = error?.code ?? "UNKNOWN_ERROR";
    this.fields = error?.details?.fields ?? {};
  }

  /** Field errors keyed by form field name ("body.email" becomes "email"). */
  formErrors(): Record<string, string> {
    return Object.fromEntries(
      Object.entries(this.fields).map(([location, message]) => [location.split(".").pop() ?? location, message]),
    );
  }
}

/** Turns an openapi-fetch result into data or a thrown ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
