import {
  NextResponse,
} from "next/server";

import {
  BrowserProfileUnavailableError,
  resolveBrowserProfile,
} from "@/lib/auth/browserProfile";

import {
  buildClearedSessionCookie,
} from "@/lib/auth/sessionCookie";


export const runtime = "nodejs";


function applyProfileResponseHeaders(
  response: NextResponse,
): NextResponse {
  // Identity is browser-specific and must never be cached.
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
    applyProfileResponseHeaders(
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

  const cleared =
    buildClearedSessionCookie();

  response.cookies.set(
    cleared.name,
    cleared.value,
    cleared.options,
  );

  return response;
}


function authenticatedResponse({
  principalId,
  principalKind,
}: {
  principalId: string;
  principalKind: string;
}): NextResponse {
  return applyProfileResponseHeaders(
    NextResponse.json(
      {
        authenticated: true,
        principal: {
          principal_id:
            principalId,
          principal_kind:
            principalKind,
        },
      },
      {
        status: 200,
      },
    ),
  );
}


function unavailableResponse():
  NextResponse {
  // Indeterminate failures must never be represented as
  // authenticated:false because callers might then destroy
  // an otherwise-valid browser credential.
  return applyProfileResponseHeaders(
    NextResponse.json(
      {
        error:
          "Principal profile is temporarily unavailable.",
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
      await resolveBrowserProfile();
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserProfileUnavailableError
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

  return authenticatedResponse({
    principalId:
      resolution.profile.principalId,

    principalKind:
      resolution.profile.principalKind,
  });
}
