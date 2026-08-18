import {
  type NextRequest,
  NextResponse,
} from "next/server";

import {
  AuthCsrfRejectedError,
  requireAuthWriteRequest,
} from "@/lib/auth/authCsrf";

import {
  BrowserLogoutUnavailableError,
  revokeBrowserSessionToken,
} from "@/lib/auth/browserLogout";

import {
  buildClearedSessionCookie,
  getSessionCookieName,
} from "@/lib/auth/sessionCookie";


export const runtime = "nodejs";


function applyLogoutResponseHeaders(
  response: NextResponse,
): NextResponse {
  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  response.headers.set(
    "Pragma",
    "no-cache",
  );

  response.headers.set(
    "Vary",
    "Cookie",
  );

  return response;
}


function rejectedResponse():
  NextResponse {
  // CSRF failures must never alter session state.
  return applyLogoutResponseHeaders(
    NextResponse.json(
      {
        error:
          "Request rejected.",
      },
      {
        status: 403,
      },
    ),
  );
}


function unavailableResponse():
  NextResponse {
  // Explicit logout expresses the user's intent to destroy
  // the browser credential even when server-side revocation
  // cannot be confirmed.
  //
  // We still return 503 so the caller knows durable
  // revocation is indeterminate, but the local credential
  // must not remain usable in this browser.
  const response =
    applyLogoutResponseHeaders(
      NextResponse.json(
        {
          error:
            "Logout is temporarily unavailable.",
        },
        {
          status: 503,
        },
      ),
    );

  const cleared =
    buildClearedSessionCookie();

  response.cookies.set(
    cleared.name,
    cleared.value,
    cleared.options,
  );

  return response;
}


function successfulLogoutResponse({
  clearCookie,
}: {
  clearCookie: boolean;
}): NextResponse {
  const response =
    applyLogoutResponseHeaders(
      new NextResponse(
        null,
        {
          status: 204,
        },
      ),
    );

  if (!clearCookie) {
    return response;
  }

  const cleared =
    buildClearedSessionCookie();

  response.cookies.set(
    cleared.name,
    cleared.value,
    cleared.options,
  );

  return response;
}


export async function POST(
  request: NextRequest,
): Promise<NextResponse> {
  try {
    requireAuthWriteRequest(
      request,
    );
  } catch (
    error
  ) {
    if (
      error
      instanceof AuthCsrfRejectedError
    ) {
      return rejectedResponse();
    }

    throw error;
  }

  const cookieName =
    getSessionCookieName();

  const sessionToken =
    request.cookies.get(
      cookieName,
    )?.value;

  // Logout is idempotent:
  //
  // no browser credential already means logged out.
  //
  // Do not emit a clearing Set-Cookie when nothing exists.
  if (!sessionToken) {
    return successfulLogoutResponse({
      clearCookie: false,
    });
  }

  try {
    const result =
      await revokeBrowserSessionToken({
        sessionToken,
      });

    return successfulLogoutResponse({
      clearCookie:
        result.clearCookie,
    });
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserLogoutUnavailableError
    ) {
      return unavailableResponse();
    }

    throw error;
  }
}
