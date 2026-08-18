import {
  GOOGLE_AUTHORIZATION_ENDPOINT,
} from "./googleAuthConfig";

import type {
  GoogleAuthTransaction,
} from "./googleAuthTransaction";


export type GoogleAuthorizationRequest = {
  clientId: string;
  redirectUri: string;
  transaction: GoogleAuthTransaction;
};


export function buildGoogleAuthorizationUrl({
  clientId,
  redirectUri,
  transaction,
}: GoogleAuthorizationRequest): URL {
  if (
    typeof clientId !== "string"
    || clientId.trim() === ""
    || clientId !== clientId.trim()
  ) {
    throw new Error(
      "Google OAuth client ID is invalid.",
    );
  }

  let callback: URL;

  try {
    callback = new URL(redirectUri);
  } catch {
    throw new Error(
      "Google OAuth redirect URI is invalid.",
    );
  }

  if (
    callback.protocol !== "https:"
    && callback.protocol !== "http:"
  ) {
    throw new Error(
      "Google OAuth redirect URI is invalid.",
    );
  }

  const url = new URL(
    GOOGLE_AUTHORIZATION_ENDPOINT,
  );

  url.searchParams.set(
    "client_id",
    clientId,
  );

  url.searchParams.set(
    "redirect_uri",
    callback.toString(),
  );

  url.searchParams.set(
    "response_type",
    "code",
  );

  // Keep initial permissions intentionally minimal.
  //
  // openid:
  //   OIDC identity.
  //
  // email:
  //   permits verified-email claims for signup policy
  //   and future display/session metadata.
  //
  // No Google APIs, Drive data, contacts, repository
  // access, offline access, or broad permissions.
  url.searchParams.set(
    "scope",
    "openid email",
  );

  url.searchParams.set(
    "state",
    transaction.state,
  );

  url.searchParams.set(
    "nonce",
    transaction.nonce,
  );

  url.searchParams.set(
    "code_challenge",
    transaction.codeChallenge,
  );

  url.searchParams.set(
    "code_challenge_method",
    "S256",
  );

  return url;
}
