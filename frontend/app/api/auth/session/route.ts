import {
  NextResponse,
} from "next/server";

import {
  BrowserSessionUnavailableError,
  resolveBrowserSession,
} from "@/lib/auth/browserSession";

import {
  buildClearedSessionCookie,
} from "@/lib/auth/sessionCookie";


export const runtime = "nodejs";


function applySessionResponseHeaders(
  response: NextResponse,
): NextResponse {
  // Session-state responses must never be cached.
  //
  // Vary: Cookie additionally prevents a cache that ignores
  // application intent from reusing one browser's auth state
  // for another browser.
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


function unauthenticatedResponse({
  clearCookie,
}: {
  clearCookie: boolean;
}): NextResponse {
  const response =
    applySessionResponseHeaders(
      NextResponse.json(
        {
          authenticated: false,
        },
        {
          status: 200,
        },
      ),
    );

  if (!clearCookie) {
    return response;
  }

  // A backend semantic 401 is authoritative evidence that
  // the browser credential is stale or unusable.
  //
  // Only that definitive result may destroy browser session
  // state. Backend outages and indeterminate failures must
  // preserve the credential so recovery is automatic.
  const cleared =
    buildClearedSessionCookie();

  response.cookies.set(
    cleared.name,
    cleared.value,
    cleared.options,
  );

  return response;
}


function authenticatedResponse():
  NextResponse {
  // This endpoint answers only the session-state question.
  //
  // Durable identity fields remain server-side. Browser-facing
  // profile/identity data belongs behind a separate /me contract.
  return applySessionResponseHeaders(
    NextResponse.json(
      {
        authenticated: true,
      },
      {
        status: 200,
      },
    ),
  );
}


function unavailableResponse():
  NextResponse {
  // An outage is deliberately NOT represented as
  // authenticated:false. Doing so would collapse
  // "cannot determine" into "logged out".
  return applySessionResponseHeaders(
    NextResponse.json(
      {
        error:
          "Session authentication is temporarily unavailable.",
      },
      {
        status: 503,
      },
    ),
  );
}


export async function GET():
  Promise<NextResponse> {
  let resolution;

  try {
    resolution =
      await resolveBrowserSession();
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserSessionUnavailableError
    ) {
      return unavailableResponse();
    }

    throw error;
  }

  if (!resolution.authenticated) {
    return unauthenticatedResponse({
      clearCookie:
        resolution.clearCookie,
    });
  }

  return authenticatedResponse();
}
