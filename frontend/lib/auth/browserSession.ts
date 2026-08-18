import {
  cookies,
} from "next/headers";

import {
  INTERNAL_LOGIN_SECRET_HEADER,
  InternalLoginConfigurationError,
  loadInternalLoginServerConfig,
} from "@/lib/auth/internalLoginCompletion";

import {
  getSessionCookieName,
} from "@/lib/auth/sessionCookie";


export const
  INTERNAL_SESSION_RESOLVE_PATH =
    "/internal/v1/auth/session/resolve";

export const
  MAX_INTERNAL_SESSION_RESOLUTION_RESPONSE_BYTES =
    16 * 1024;


const SESSION_EXPIRY_WITH_TIMEZONE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;


export class BrowserSessionError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserSessionError";
  }
}


export class BrowserSessionUnavailableError
  extends BrowserSessionError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserSessionUnavailableError";
  }
}


export type AuthenticatedBrowserSession = {
  authenticated: true;
  principalId: string;
  identityLinkId: string;
  sessionId: string;
  sessionExpiresAt: string;
};


export type UnauthenticatedBrowserSession = {
  authenticated: false;

  // When true, the caller should remove the browser session
  // cookie before redirecting or returning an unauthenticated
  // response.
  //
  // Missing cookie -> false.
  // Rejected/stale cookie -> true.
  clearCookie: boolean;
};


export type BrowserSessionResolution =
  | AuthenticatedBrowserSession
  | UnauthenticatedBrowserSession;


function requireExactIdentifier(
  value: unknown,
  prefix: string,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
    || !value.startsWith(prefix)
  ) {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "is invalid.",
    );
  }

  return value;
}


function requireSessionExpiry(
  value: unknown,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
    || !SESSION_EXPIRY_WITH_TIMEZONE.test(
      value,
    )
    || !Number.isFinite(
      Date.parse(value),
    )
  ) {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "contains an invalid expiry.",
    );
  }

  return value;
}


function parseResolutionSuccess(
  payload: unknown,
): AuthenticatedBrowserSession {
  if (
    typeof payload !== "object"
    || payload === null
  ) {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "is invalid.",
    );
  }

  const candidate =
    payload as {
      principal_id?: unknown;
      identity_link_id?: unknown;
      session_id?: unknown;
      session_expires_at?: unknown;
    };

  return {
    authenticated: true,

    principalId:
      requireExactIdentifier(
        candidate.principal_id,
        "prn_",
      ),

    identityLinkId:
      requireExactIdentifier(
        candidate.identity_link_id,
        "pil_",
      ),

    sessionId:
      requireExactIdentifier(
        candidate.session_id,
        "ses_",
      ),

    sessionExpiresAt:
      requireSessionExpiry(
        candidate.session_expires_at,
      ),
  };
}


async function readBoundedText(
  response: Response,
): Promise<string> {
  const contentLength =
    response.headers.get(
      "content-length",
    );

  if (contentLength !== null) {
    const declared =
      Number(contentLength);

    if (
      !Number.isSafeInteger(declared)
      || declared < 0
      || declared
        > MAX_INTERNAL_SESSION_RESOLUTION_RESPONSE_BYTES
    ) {
      throw new BrowserSessionUnavailableError(
        "Internal session resolution response "
        + "is invalid.",
      );
    }
  }

  let text: string;

  try {
    text =
      await response.text();
  } catch {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "could not be read.",
    );
  }

  if (
    Buffer.byteLength(
      text,
      "utf8",
    )
    > MAX_INTERNAL_SESSION_RESOLUTION_RESPONSE_BYTES
  ) {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "is too large.",
    );
  }

  return text;
}


function requireBrowserSessionToken(
  token: string,
): string {
  if (
    typeof token !== "string"
    || !token
    || token !== token.trim()
  ) {
    throw new BrowserSessionError(
      "Browser session token is invalid.",
    );
  }

  const bytes =
    Buffer.byteLength(
      token,
      "utf8",
    );

  if (
    bytes < 32
    || bytes > 1024
  ) {
    throw new BrowserSessionError(
      "Browser session token is invalid.",
    );
  }

  return token;
}


export async function resolveBrowserSessionToken({
  sessionToken,
  fetchImpl = fetch,
}: {
  sessionToken: string;
  fetchImpl?: typeof fetch;
}): Promise<BrowserSessionResolution> {
  let token: string;

  try {
    token =
      requireBrowserSessionToken(
        sessionToken,
      );
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserSessionError
    ) {
      return {
        authenticated: false,
        clearCookie: true,
      };
    }

    throw error;
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
      throw new BrowserSessionUnavailableError(
        "Browser session authentication "
        + "is temporarily unavailable.",
      );
    }

    throw error;
  }

  const endpoint =
    new URL(
      INTERNAL_SESSION_RESOLVE_PATH,
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
                token,
            }),
          cache:
            "no-store",
        },
      );
  } catch {
    throw new BrowserSessionUnavailableError(
      "Browser session authentication "
      + "is temporarily unavailable.",
    );
  }

  if (response.status === 401) {
    // Expired, revoked, absent, suspended-principal,
    // or ended-link states are intentionally collapsed by
    // the backend. The BFF likewise exposes no distinction.
    return {
      authenticated: false,
      clearCookie: true,
    };
  }

  if (!response.ok) {
    throw new BrowserSessionUnavailableError(
      "Browser session authentication "
      + "is temporarily unavailable.",
    );
  }

  const text =
    await readBoundedText(
      response,
    );

  let payload: unknown;

  try {
    payload =
      JSON.parse(text);
  } catch {
    throw new BrowserSessionUnavailableError(
      "Internal session resolution response "
      + "is invalid.",
    );
  }

  return parseResolutionSuccess(
    payload,
  );
}


export async function resolveBrowserSession():
  Promise<BrowserSessionResolution> {
  const cookieStore =
    await cookies();

  // Production resolves only the __Host- credential.
  // Development resolves only the explicitly configured
  // development cookie name.
  //
  // We deliberately do not fall back from the production
  // __Host- cookie to the weaker development cookie.
  const cookieName =
    getSessionCookieName();

  const sessionToken =
    cookieStore.get(
      cookieName,
    )?.value;

  if (!sessionToken) {
    return {
      authenticated: false,
      clearCookie: false,
    };
  }

  return resolveBrowserSessionToken({
    sessionToken,
  });
}
