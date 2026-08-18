import {
  type NextRequest,
  NextResponse,
} from "next/server";

import {
  GOOGLE_AUTH_TRANSACTION_COOKIE,
  GoogleAuthTransactionError,
  deserializeGoogleAuthTransaction,
} from "@/lib/auth/googleAuthTransaction";

import {
  GoogleAuthConfigurationError,
  loadGoogleAuthServerConfig,
} from "@/lib/auth/googleAuthConfig";

import {
  GoogleCallbackProtocolError,
  GoogleTokenExchangeRejectedError,
  GoogleTokenExchangeUnavailableError,
  exchangeGoogleAuthorizationCode,
  parseGoogleAuthorizationCallback,
} from "@/lib/auth/googleCallback";

import {
  InternalLoginConfigurationError,
  InternalLoginRejectedError,
  InternalLoginUnavailableError,
  completeInternalGoogleLogin,
} from "@/lib/auth/internalLoginCompletion";

import {
  SessionCookieError,
  buildSessionCookie,
} from "@/lib/auth/sessionCookie";


export const runtime = "nodejs";


function clearTransactionCookie(
  response: NextResponse,
): NextResponse {
  response.cookies.set(
    GOOGLE_AUTH_TRANSACTION_COOKIE,
    "",
    {
      httpOnly: true,
      secure:
        process.env.NODE_ENV
        === "production",
      sameSite: "lax",
      path:
        "/api/auth/google",
      maxAge: 0,
      expires:
        new Date(0),
    },
  );

  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  return response;
}


function authenticationFailed():
  NextResponse {
  return clearTransactionCookie(
    NextResponse.json(
      {
        error:
          "Authentication failed.",
      },
      {
        status: 401,
      },
    ),
  );
}


function authenticationUnavailable():
  NextResponse {
  return clearTransactionCookie(
    NextResponse.json(
      {
        error:
          "Authentication is temporarily unavailable.",
      },
      {
        status: 503,
      },
    ),
  );
}


function redirectToReturnPath(
  request: NextRequest,
  returnTo: string,
): NextResponse {
  const destination =
    new URL(
      returnTo,
      request.nextUrl.origin,
    );

  return clearTransactionCookie(
    NextResponse.redirect(
      destination,
      {
        status: 303,
      },
    ),
  );
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
        "Google callback configuration failure.",
        {
          error:
            error.message,
        },
      );

      return authenticationUnavailable();
    }

    throw error;
  }

  const serializedTransaction =
    request.cookies.get(
      GOOGLE_AUTH_TRANSACTION_COOKIE,
    )?.value;

  if (!serializedTransaction) {
    return authenticationFailed();
  }

  let transaction;

  try {
    transaction =
      deserializeGoogleAuthTransaction(
        serializedTransaction,
        {
          secret:
            config.transactionSecret,
        },
      );
  } catch (
    error
  ) {
    if (
      error
      instanceof GoogleAuthTransactionError
    ) {
      return authenticationFailed();
    }

    throw error;
  }

  let callback;

  try {
    callback =
      parseGoogleAuthorizationCallback({
        callbackUrl:
          request.nextUrl,
        transaction,
      });
  } catch (
    error
  ) {
    if (
      error
      instanceof GoogleCallbackProtocolError
    ) {
      return authenticationFailed();
    }

    throw error;
  }

  if (
    callback.kind
    === "authorization_denied"
  ) {
    return authenticationFailed();
  }

  let tokenResult;

  try {
    tokenResult =
      await exchangeGoogleAuthorizationCode({
        clientId:
          config.clientId,
        redirectUri:
          config.redirectUri,
        code:
          callback.code,
        codeVerifier:
          transaction.codeVerifier,
      });
  } catch (
    error
  ) {
    if (
      error
      instanceof GoogleTokenExchangeRejectedError
    ) {
      return authenticationFailed();
    }

    if (
      error
      instanceof GoogleTokenExchangeUnavailableError
    ) {
      return authenticationUnavailable();
    }

    throw error;
  }

  let internalLoginResult;

  try {
    // The raw Google ID token crosses only the trusted
    // BFF -> FastAPI server boundary.
    //
    // Python performs cryptographic verification and nonce
    // binding, then resolves/provisions exactly one principal.
    //
    // principal_id and identity_link_id are deliberately not
    // written into the browser URL or a client-readable cookie.
    internalLoginResult =
      await completeInternalGoogleLogin({
        idToken:
          tokenResult.idToken,
        expectedNonce:
          transaction.nonce,
        transactionId:
          transaction.transactionId,
      });
  } catch (
    error
  ) {
    if (
      error
      instanceof InternalLoginRejectedError
    ) {
      return authenticationFailed();
    }

    if (
      error
      instanceof InternalLoginUnavailableError
      || error
        instanceof InternalLoginConfigurationError
    ) {
      console.error(
        "Internal Google login completion unavailable.",
      );

      return authenticationUnavailable();
    }

    throw error;
  }

  let sessionCookie;

  try {
    sessionCookie =
      buildSessionCookie({
        token:
          internalLoginResult.sessionToken,
        expiresAt:
          internalLoginResult.sessionExpiresAt,
      });
  } catch (
    error
  ) {
    if (
      error
      instanceof SessionCookieError
    ) {
      // Never log the raw session credential.
      //
      // A backend-issued credential that cannot be represented
      // safely as the browser session cookie must fail closed.
      console.error(
        "Solvyn session cookie could not be issued.",
      );

      return authenticationUnavailable();
    }

    throw error;
  }

  const response =
    redirectToReturnPath(
      request,
      transaction.returnTo,
    );

  // The raw Solvyn session credential enters the browser only
  // here, as an HttpOnly cookie constructed by the dedicated
  // cookie authority.
  //
  // It is never placed in:
  // - the redirect URL;
  // - query parameters;
  // - fragments;
  // - response JSON;
  // - browser storage;
  // - client-readable JavaScript state.
  response.cookies.set(
    sessionCookie.name,
    sessionCookie.value,
    sessionCookie.options,
  );

  return response;
}
