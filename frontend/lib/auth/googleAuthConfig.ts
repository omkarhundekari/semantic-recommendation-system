import "server-only";


export const GOOGLE_AUTHORIZATION_ENDPOINT =
  "https://accounts.google.com/o/oauth2/v2/auth";


export class GoogleAuthConfigurationError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "GoogleAuthConfigurationError";
  }
}


export type GoogleAuthServerConfig = {
  clientId: string;
  redirectUri: string;
  transactionSecret: string;
};


function requireNonEmptyEnv(
  name: string,
): string {
  const value = process.env[name];

  if (
    typeof value !== "string"
    || value.trim() === ""
  ) {
    throw new GoogleAuthConfigurationError(
      `${name} is not configured.`,
    );
  }

  if (value !== value.trim()) {
    throw new GoogleAuthConfigurationError(
      `${name} must not contain surrounding whitespace.`,
    );
  }

  return value;
}


function validateRedirectUri(
  value: string,
): string {
  let parsed: URL;

  try {
    parsed = new URL(value);
  } catch {
    throw new GoogleAuthConfigurationError(
      "GOOGLE_OIDC_REDIRECT_URI must be an absolute URL.",
    );
  }

  const isProduction =
    process.env.NODE_ENV === "production";

  if (
    parsed.protocol !== "https:"
    && !(
      !isProduction
      && parsed.protocol === "http:"
      && (
        parsed.hostname === "localhost"
        || parsed.hostname === "127.0.0.1"
      )
    )
  ) {
    throw new GoogleAuthConfigurationError(
      "GOOGLE_OIDC_REDIRECT_URI must use HTTPS "
      + "outside local development.",
    );
  }

  if (
    parsed.username
    || parsed.password
    || parsed.hash
  ) {
    throw new GoogleAuthConfigurationError(
      "GOOGLE_OIDC_REDIRECT_URI is invalid.",
    );
  }

  return parsed.toString();
}


export function loadGoogleAuthServerConfig():
  GoogleAuthServerConfig {
  const clientId =
    requireNonEmptyEnv(
      "GOOGLE_OIDC_CLIENT_ID",
    );

  const redirectUri =
    validateRedirectUri(
      requireNonEmptyEnv(
        "GOOGLE_OIDC_REDIRECT_URI",
      ),
    );

  const transactionSecret =
    requireNonEmptyEnv(
      "SOLVYN_AUTH_TRANSACTION_SECRET",
    );

  if (
    Buffer.byteLength(
      transactionSecret,
      "utf8",
    ) < 32
  ) {
    throw new GoogleAuthConfigurationError(
      "SOLVYN_AUTH_TRANSACTION_SECRET must "
      + "contain at least 32 bytes.",
    );
  }

  return {
    clientId,
    redirectUri,
    transactionSecret,
  };
}
