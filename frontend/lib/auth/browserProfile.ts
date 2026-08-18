import "server-only";

import {
  cookies,
} from "next/headers";

import {
  INTERNAL_LOGIN_SECRET_HEADER,
  InternalLoginConfigurationError,
  loadInternalLoginServerConfig,
} from "@/lib/auth/internalLoginCompletion";

import {
  MAX_SESSION_TOKEN_BYTES,
  MIN_SESSION_TOKEN_BYTES,
  getSessionCookieName,
} from "@/lib/auth/sessionCookie";


export const PRODUCT_ME_PATH =
  "/v1/me";

export const BROWSER_SESSION_HEADER =
  "X-Solvyn-Browser-Session";

export const MAX_PRODUCT_ME_RESPONSE_BYTES =
  16 * 1024;


export class BrowserProfileError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProfileError";
  }
}


export class BrowserProfileUnavailableError
  extends BrowserProfileError {
  constructor(message: string) {
    super(message);
    this.name =
      "BrowserProfileUnavailableError";
  }
}


export type BrowserPrincipalProfile = {
  principalId: string;
  principalKind: string;
};


export type AuthenticatedBrowserProfile = {
  authenticated: true;
  profile: BrowserPrincipalProfile;
};


export type UnauthenticatedBrowserProfile = {
  authenticated: false;

  // Only a definitive backend 401 may mark an existing
  // browser credential for destruction.
  //
  // Missing browser cookie is not an invalid credential.
  clearCookie: boolean;
};


export type BrowserProfileResolution =
  | AuthenticatedBrowserProfile
  | UnauthenticatedBrowserProfile;


function requireBrowserSessionToken(
  token: string,
): string {
  if (
    typeof token !== "string"
    || !token
    || token !== token.trim()
  ) {
    throw new BrowserProfileError(
      "Browser session token is invalid.",
    );
  }

  const bytes =
    Buffer.byteLength(
      token,
      "utf8",
    );

  if (
    bytes < MIN_SESSION_TOKEN_BYTES
    || bytes > MAX_SESSION_TOKEN_BYTES
  ) {
    throw new BrowserProfileError(
      "Browser session token is invalid.",
    );
  }

  return token;
}


function requirePrincipalIdentifier(
  value: unknown,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
    || !value.startsWith("prn_")
  ) {
    throw new BrowserProfileUnavailableError(
      "Principal profile response is invalid.",
    );
  }

  return value;
}


function requirePrincipalKind(
  value: unknown,
): string {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
  ) {
    throw new BrowserProfileUnavailableError(
      "Principal profile response is invalid.",
    );
  }

  return value;
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
        > MAX_PRODUCT_ME_RESPONSE_BYTES
    ) {
      throw new BrowserProfileUnavailableError(
        "Principal profile response is invalid.",
      );
    }
  }

  let text: string;

  try {
    text =
      await response.text();
  } catch {
    throw new BrowserProfileUnavailableError(
      "Principal profile response could not be read.",
    );
  }

  if (
    Buffer.byteLength(
      text,
      "utf8",
    )
    > MAX_PRODUCT_ME_RESPONSE_BYTES
  ) {
    throw new BrowserProfileUnavailableError(
      "Principal profile response is too large.",
    );
  }

  return text;
}


function parseProfileResponse(
  payload: unknown,
): BrowserPrincipalProfile {
  if (
    typeof payload !== "object"
    || payload === null
    || Array.isArray(payload)
  ) {
    throw new BrowserProfileUnavailableError(
      "Principal profile response is invalid.",
    );
  }

  const candidate =
    payload as {
      principal_id?: unknown;
      principal_kind?: unknown;
    };

  // Deliberately construct a fresh minimal profile instead
  // of returning the backend object.
  //
  // If FastAPI ever gains additional identity fields, they
  // do not automatically cross the browser-facing boundary.
  return {
    principalId:
      requirePrincipalIdentifier(
        candidate.principal_id,
      ),

    principalKind:
      requirePrincipalKind(
        candidate.principal_kind,
      ),
  };
}


export async function resolveBrowserProfileToken({
  sessionToken,
  fetchImpl = fetch,
}: {
  sessionToken: string;
  fetchImpl?: typeof fetch;
}): Promise<BrowserProfileResolution> {
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
      error instanceof BrowserProfileError
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
      throw new BrowserProfileUnavailableError(
        "Browser profile is temporarily unavailable.",
      );
    }

    throw error;
  }

  const endpoint =
    new URL(
      PRODUCT_ME_PATH,
      `${config.apiBaseUrl}/`,
    );

  let response: Response;

  try {
    response =
      await fetchImpl(
        endpoint,
        {
          method: "GET",
          headers: {
            Accept:
              "application/json",

            [BROWSER_SESSION_HEADER]:
              token,

            [INTERNAL_LOGIN_SECRET_HEADER]:
              config.internalSecret,
          },
          cache:
            "no-store",
        },
      );
  } catch {
    throw new BrowserProfileUnavailableError(
      "Browser profile is temporarily unavailable.",
    );
  }

  if (response.status === 401) {
    // FastAPI has authoritatively rejected this credential.
    //
    // Missing, expired, revoked, suspended-principal,
    // ended-link, and other invalid durable session states
    // intentionally collapse here.
    return {
      authenticated: false,
      clearCookie: true,
    };
  }

  if (!response.ok) {
    // Storage failures, backend outages, unexpected status
    // codes, and other indeterminate failures preserve the
    // browser credential.
    throw new BrowserProfileUnavailableError(
      "Browser profile is temporarily unavailable.",
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
    throw new BrowserProfileUnavailableError(
      "Principal profile response is invalid.",
    );
  }

  return {
    authenticated: true,
    profile:
      parseProfileResponse(
        payload,
      ),
  };
}


export async function resolveBrowserProfile():
  Promise<BrowserProfileResolution> {
  const cookieStore =
    await cookies();

  const sessionToken =
    cookieStore.get(
      getSessionCookieName(),
    )?.value;

  if (sessionToken === undefined) {
    return {
      authenticated: false,
      clearCookie: false,
    };
  }

  return resolveBrowserProfileToken({
    sessionToken,
  });
}
