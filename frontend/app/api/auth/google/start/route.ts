import {
  type NextRequest,
  NextResponse,
} from "next/server";

import {
  GOOGLE_AUTH_TRANSACTION_COOKIE,
  GOOGLE_AUTH_TRANSACTION_TTL_SECONDS,
  createGoogleAuthTransaction,
  serializeGoogleAuthTransaction,
} from "@/lib/auth/googleAuthTransaction";

import {
  GoogleAuthConfigurationError,
  loadGoogleAuthServerConfig,
} from "@/lib/auth/googleAuthConfig";

import {
  buildGoogleAuthorizationUrl,
} from "@/lib/auth/googleAuthorization";


export const runtime = "nodejs";


function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}


export async function GET(
  request: NextRequest,
): Promise<NextResponse> {
  let config;

  try {
    config =
      loadGoogleAuthServerConfig();
  } catch (error) {
    if (
      error
      instanceof GoogleAuthConfigurationError
    ) {
      console.error(
        "Google authentication start "
        + "configuration failure.",
        {
          error: error.message,
        },
      );

      return NextResponse.json(
        {
          error:
            "Authentication is temporarily unavailable.",
        },
        {
          status: 503,
        },
      );
    }

    throw error;
  }

  const rawReturnTo =
    request.nextUrl.searchParams.get(
      "returnTo",
    );

  let transaction;

  try {
    transaction =
      createGoogleAuthTransaction({
        returnTo:
          rawReturnTo ?? "/",
      });
  } catch {
    return NextResponse.json(
      {
        error:
          "Authentication request is invalid.",
      },
      {
        status: 400,
      },
    );
  }

  const serialized =
    serializeGoogleAuthTransaction(
      transaction,
      {
        secret:
          config.transactionSecret,
      },
    );

  const authorizationUrl =
    buildGoogleAuthorizationUrl({
      clientId:
        config.clientId,
      redirectUri:
        config.redirectUri,
      transaction,
    });

  const response =
    NextResponse.redirect(
      authorizationUrl,
      {
        status: 302,
      },
    );

  response.cookies.set(
    GOOGLE_AUTH_TRANSACTION_COOKIE,
    serialized,
    {
      httpOnly: true,
      secure: isProduction(),
      sameSite: "lax",
      path: "/api/auth/google",
      maxAge:
        GOOGLE_AUTH_TRANSACTION_TTL_SECONDS,
    },
  );

  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  return response;
}
