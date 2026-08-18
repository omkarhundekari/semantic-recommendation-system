import {
  INTERNAL_LOGIN_SECRET_HEADER,
  InternalLoginConfigurationError,
  loadInternalLoginServerConfig,
} from "@/lib/auth/internalLoginCompletion";

import {
  MAX_SESSION_TOKEN_BYTES,
  MIN_SESSION_TOKEN_BYTES,
} from "@/lib/auth/sessionCookie";


export const
  INTERNAL_SESSION_REVOKE_PATH =
    "/internal/v1/auth/session/revoke";


export class BrowserLogoutError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserLogoutError";
  }
}


export class BrowserLogoutUnavailableError
  extends BrowserLogoutError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserLogoutUnavailableError";
  }
}


export type BrowserLogoutResult = {
  // true means the browser credential is definitively
  // unusable and may safely be removed.
  clearCookie: true;
};


function isValidBrowserSessionToken(
  token: string,
): boolean {
  if (
    typeof token !== "string"
    || !token
    || token !== token.trim()
  ) {
    return false;
  }

  const bytes =
    Buffer.byteLength(
      token,
      "utf8",
    );

  return (
    bytes
      >= MIN_SESSION_TOKEN_BYTES
    && bytes
      <= MAX_SESSION_TOKEN_BYTES
  );
}


export async function revokeBrowserSessionToken({
  sessionToken,
  fetchImpl = fetch,
}: {
  sessionToken: string;
  fetchImpl?: typeof fetch;
}): Promise<BrowserLogoutResult> {
  // A malformed credential cannot represent a usable
  // Solvyn login session.
  //
  // It is therefore already equivalent to logged out and may
  // be cleared locally without sending attacker-controlled or
  // malformed credential material across the internal boundary.
  if (
    !isValidBrowserSessionToken(
      sessionToken,
    )
  ) {
    return {
      clearCookie: true,
    };
  }

  let config;

  try {
    config =
      loadInternalLoginServerConfig();
  } catch (
    error
  ) {
    if (
      error
      instanceof InternalLoginConfigurationError
    ) {
      throw new BrowserLogoutUnavailableError(
        "Browser logout is temporarily unavailable.",
      );
    }

    throw error;
  }

  const endpoint =
    new URL(
      INTERNAL_SESSION_REVOKE_PATH,
      `${config.apiBaseUrl}/`,
    );

  let response: Response;

  try {
    response =
      await fetchImpl(
        endpoint,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            Accept:
              "application/json",
            [INTERNAL_LOGIN_SECRET_HEADER]:
              config.internalSecret,
          },
          body:
            JSON.stringify({
              session_token:
                sessionToken,
            }),
          cache:
            "no-store",
        },
      );
  } catch {
    // Network/DNS/TLS failures are indeterminate.
    //
    // Never destroy the browser credential when the backend
    // cannot tell us whether revocation committed.
    throw new BrowserLogoutUnavailableError(
      "Browser logout is temporarily unavailable.",
    );
  }

  // The internal revocation API has exactly one definitive
  // successful contract: 204.
  //
  // Its 204 is intentionally idempotent for:
  // - active session successfully revoked;
  // - missing session;
  // - malformed session;
  // - already-revoked session.
  //
  // Anything else is indeterminate from the BFF's perspective
  // and therefore MUST preserve the browser cookie.
  if (
    response.status
    !== 204
  ) {
    throw new BrowserLogoutUnavailableError(
      "Browser logout is temporarily unavailable.",
    );
  }

  return {
    clearCookie: true,
  };
}
