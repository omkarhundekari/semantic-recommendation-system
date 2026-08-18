import {
  type NextRequest,
} from "next/server";


export class AuthCsrfRejectedError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "AuthCsrfRejectedError";
  }
}


function normalizeOrigin(
  value: string,
): string {
  let parsed: URL;

  try {
    parsed =
      new URL(value);
  } catch {
    throw new AuthCsrfRejectedError(
      "Request origin is invalid.",
    );
  }

  if (
    parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || parsed.search
    || parsed.hash
  ) {
    throw new AuthCsrfRejectedError(
      "Request origin is invalid.",
    );
  }

  return parsed.origin;
}


function requireSameOrigin({
  request,
}: {
  request: NextRequest;
}): void {
  const origin =
    request.headers.get(
      "origin",
    );

  if (!origin) {
    throw new AuthCsrfRejectedError(
      "Request origin is required.",
    );
  }

  const requestOrigin =
    request.nextUrl.origin;

  const normalizedOrigin =
    normalizeOrigin(
      origin,
    );

  if (
    normalizedOrigin
    !== requestOrigin
  ) {
    throw new AuthCsrfRejectedError(
      "Cross-origin request rejected.",
    );
  }
}


function requireFetchMetadata({
  request,
}: {
  request: NextRequest;
}): void {
  const fetchSite =
    request.headers.get(
      "sec-fetch-site",
    );

  // Modern browsers should identify a normal same-origin
  // application request as same-origin.
  //
  // "none" is allowed for browser-driven top-level actions
  // such as explicitly entering a URL, but state-changing
  // auth routes remain POST-only so such navigation cannot
  // invoke logout.
  //
  // Missing Fetch Metadata is tolerated only after the
  // mandatory Origin check succeeds, preserving compatibility
  // with clients that do not emit Sec-Fetch-Site.
  if (
    fetchSite === null
    || fetchSite === "same-origin"
    || fetchSite === "none"
  ) {
    return;
  }

  throw new AuthCsrfRejectedError(
    "Cross-site request rejected.",
  );
}


export function requireAuthWriteRequest(
  request: NextRequest,
): void {
  if (
    request.method !== "POST"
  ) {
    throw new AuthCsrfRejectedError(
      "Authentication writes require POST.",
    );
  }

  requireSameOrigin({
    request,
  });

  requireFetchMetadata({
    request,
  });
}
