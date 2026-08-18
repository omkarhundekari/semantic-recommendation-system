import "server-only";

import {
  timingSafeEqual,
} from "node:crypto";

import type {
  GoogleAuthTransaction,
} from "./googleAuthTransaction";


export const GOOGLE_TOKEN_ENDPOINT =
  "https://oauth2.googleapis.com/token";

export const MAX_GOOGLE_AUTHORIZATION_CODE_BYTES =
  8 * 1024;

export const MAX_GOOGLE_TOKEN_RESPONSE_BYTES =
  64 * 1024;

export const MAX_GOOGLE_ID_TOKEN_BYTES =
  8 * 1024;


export class GoogleCallbackProtocolError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "GoogleCallbackProtocolError";
  }
}


export class GoogleTokenExchangeError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "GoogleTokenExchangeError";
  }
}


export class GoogleTokenExchangeRejectedError
  extends GoogleTokenExchangeError {
  constructor(message: string) {
    super(message);
    this.name =
      "GoogleTokenExchangeRejectedError";
  }
}


export class GoogleTokenExchangeUnavailableError
  extends GoogleTokenExchangeError {
  constructor(message: string) {
    super(message);
    this.name =
      "GoogleTokenExchangeUnavailableError";
  }
}


export type GoogleAuthorizationCodeCallback = {
  kind: "authorization_code";
  code: string;
};


export type GoogleAuthorizationDeniedCallback = {
  kind: "authorization_denied";
};


export type GoogleAuthorizationCallbackResult =
  | GoogleAuthorizationCodeCallback
  | GoogleAuthorizationDeniedCallback;


export type GoogleTokenExchangeResult = {
  idToken: string;
};


function requireSingleQueryValue(
  searchParams: URLSearchParams,
  name: string,
): string | null {
  const values =
    searchParams.getAll(name);

  if (values.length > 1) {
    throw new GoogleCallbackProtocolError(
      `Google callback parameter ${name} `
      + "must not be repeated.",
    );
  }

  if (values.length === 0) {
    return null;
  }

  const value = values[0];

  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
  ) {
    throw new GoogleCallbackProtocolError(
      `Google callback parameter ${name} `
      + "is invalid.",
    );
  }

  return value;
}


function constantTimeTextMatches(
  expected: string,
  received: string,
): boolean {
  const expectedBytes =
    Buffer.from(
      expected,
      "utf8",
    );

  const receivedBytes =
    Buffer.from(
      received,
      "utf8",
    );

  if (
    expectedBytes.byteLength
    !== receivedBytes.byteLength
  ) {
    return false;
  }

  return timingSafeEqual(
    expectedBytes,
    receivedBytes,
  );
}


function requireMatchingState(
  receivedState: string | null,
  expectedState: string,
): void {
  if (
    receivedState === null
    || !constantTimeTextMatches(
      expectedState,
      receivedState,
    )
  ) {
    throw new GoogleCallbackProtocolError(
      "Google authentication state is invalid.",
    );
  }
}


export function parseGoogleAuthorizationCallback({
  callbackUrl,
  transaction,
}: {
  callbackUrl: string | URL;
  transaction: GoogleAuthTransaction;
}): GoogleAuthorizationCallbackResult {
  let parsed: URL;

  try {
    parsed =
      callbackUrl instanceof URL
        ? callbackUrl
        : new URL(callbackUrl);
  } catch {
    throw new GoogleCallbackProtocolError(
      "Google authentication callback URL "
      + "is invalid.",
    );
  }

  const state =
    requireSingleQueryValue(
      parsed.searchParams,
      "state",
    );

  requireMatchingState(
    state,
    transaction.state,
  );

  const code =
    requireSingleQueryValue(
      parsed.searchParams,
      "code",
    );

  const error =
    requireSingleQueryValue(
      parsed.searchParams,
      "error",
    );

  if (
    code !== null
    && error !== null
  ) {
    throw new GoogleCallbackProtocolError(
      "Google authentication callback "
      + "contains conflicting results.",
    );
  }

  if (error !== null) {
    if (error === "access_denied") {
      return {
        kind: "authorization_denied",
      };
    }

    throw new GoogleCallbackProtocolError(
      "Google authentication callback "
      + "reported an unsupported error.",
    );
  }

  if (code === null) {
    throw new GoogleCallbackProtocolError(
      "Google authentication callback "
      + "does not contain an authorization code.",
    );
  }

  if (
    Buffer.byteLength(
      code,
      "utf8",
    )
    > MAX_GOOGLE_AUTHORIZATION_CODE_BYTES
  ) {
    throw new GoogleCallbackProtocolError(
      "Google authorization code is too large.",
    );
  }

  return {
    kind: "authorization_code",
    code,
  };
}


function parseGoogleTokenResponse(
  payload: string,
): GoogleTokenExchangeResult {
  if (
    Buffer.byteLength(
      payload,
      "utf8",
    )
    > MAX_GOOGLE_TOKEN_RESPONSE_BYTES
  ) {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token response is invalid.",
    );
  }

  let parsed: unknown;

  try {
    parsed = JSON.parse(payload);
  } catch {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token response is invalid.",
    );
  }

  if (
    typeof parsed !== "object"
    || parsed === null
  ) {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token response is invalid.",
    );
  }

  const candidate =
    parsed as {
      id_token?: unknown;
    };

  if (
    typeof candidate.id_token !== "string"
    || !candidate.id_token
    || candidate.id_token
      !== candidate.id_token.trim()
  ) {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token response does not contain "
      + "a valid ID token.",
    );
  }

  if (
    Buffer.byteLength(
      candidate.id_token,
      "utf8",
    )
    > MAX_GOOGLE_ID_TOKEN_BYTES
  ) {
    throw new GoogleTokenExchangeUnavailableError(
      "Google ID token is too large.",
    );
  }

  // Deliberately return only the ID token.
  //
  // Solvyn currently needs Google only for identity.
  // Access tokens and refresh tokens are not retained here.
  return {
    idToken:
      candidate.id_token,
  };
}


export async function exchangeGoogleAuthorizationCode({
  clientId,
  redirectUri,
  code,
  codeVerifier,
  fetchImpl = fetch,
}: {
  clientId: string;
  redirectUri: string;
  code: string;
  codeVerifier: string;
  fetchImpl?: typeof fetch;
}): Promise<GoogleTokenExchangeResult> {
  if (
    typeof clientId !== "string"
    || !clientId
    || clientId !== clientId.trim()
  ) {
    throw new GoogleTokenExchangeError(
      "Google OAuth client ID is invalid.",
    );
  }

  if (
    typeof redirectUri !== "string"
    || !redirectUri
    || redirectUri !== redirectUri.trim()
  ) {
    throw new GoogleTokenExchangeError(
      "Google OAuth redirect URI is invalid.",
    );
  }

  if (
    typeof code !== "string"
    || !code
    || code !== code.trim()
  ) {
    throw new GoogleTokenExchangeError(
      "Google authorization code is invalid.",
    );
  }

  if (
    Buffer.byteLength(
      code,
      "utf8",
    )
    > MAX_GOOGLE_AUTHORIZATION_CODE_BYTES
  ) {
    throw new GoogleTokenExchangeError(
      "Google authorization code is invalid.",
    );
  }

  if (
    typeof codeVerifier !== "string"
    || codeVerifier.length < 43
    || codeVerifier.length > 128
  ) {
    throw new GoogleTokenExchangeError(
      "Google PKCE code verifier is invalid.",
    );
  }

  const body =
    new URLSearchParams({
      client_id: clientId,
      code,
      code_verifier:
        codeVerifier,
      grant_type:
        "authorization_code",
      redirect_uri:
        redirectUri,
    });

  let response: Response;

  try {
    response =
      await fetchImpl(
        GOOGLE_TOKEN_ENDPOINT,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/x-www-form-urlencoded",
            Accept:
              "application/json",
          },
          body:
            body.toString(),
          cache:
            "no-store",
        },
      );
  } catch {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token exchange is temporarily "
      + "unavailable.",
    );
  }

  let payload: string;

  try {
    payload =
      await response.text();
  } catch {
    throw new GoogleTokenExchangeUnavailableError(
      "Google token exchange response "
      + "could not be read.",
    );
  }

  if (!response.ok) {
    if (
      response.status >= 500
      || response.status === 429
    ) {
      throw new GoogleTokenExchangeUnavailableError(
        "Google token exchange is temporarily "
        + "unavailable.",
      );
    }

    throw new GoogleTokenExchangeRejectedError(
      "Google token exchange was rejected.",
    );
  }

  return parseGoogleTokenResponse(
    payload,
  );
}
