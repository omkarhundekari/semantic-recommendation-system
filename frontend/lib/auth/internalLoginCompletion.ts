import "server-only";


export const INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH =
  "/internal/v1/auth/google/complete";

export const INTERNAL_LOGIN_SECRET_HEADER =
  "X-Solvyn-Internal-Login-Secret";

export const INTERNAL_LOGIN_REQUEST_TIMEOUT_MS =
  8 * 1000;

export const MAX_INTERNAL_LOGIN_RESPONSE_BYTES =
  64 * 1024;


export class InternalLoginConfigurationError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "InternalLoginConfigurationError";
  }
}


export class InternalLoginCompletionError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "InternalLoginCompletionError";
  }
}


export class InternalLoginRejectedError
  extends InternalLoginCompletionError {
  constructor(message: string) {
    super(message);
    this.name =
      "InternalLoginRejectedError";
  }
}


export class InternalLoginUnavailableError
  extends InternalLoginCompletionError {
  constructor(message: string) {
    super(message);
    this.name =
      "InternalLoginUnavailableError";
  }
}


export type InternalLoginCompletionResult = {
  status:
    | "existing"
    | "provisioned";
  principalId: string;
  identityLinkId: string;
  sessionToken: string;
  sessionExpiresAt: string;
};


type InternalLoginServerConfig = {
  apiBaseUrl: string;
  internalSecret: string;
};


function requireServerEnv(
  name: string,
): string {
  const value =
    process.env[name];

  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
  ) {
    throw new InternalLoginConfigurationError(
      `${name} is not configured correctly.`,
    );
  }

  return value;
}


function validateInternalApiBaseUrl(
  value: string,
): string {
  let parsed: URL;

  try {
    parsed =
      new URL(value);
  } catch {
    throw new InternalLoginConfigurationError(
      "SOLVYN_INTERNAL_API_BASE_URL "
      + "must be an absolute URL.",
    );
  }

  const isProduction =
    process.env.NODE_ENV === "production";

  const localDevelopment =
    !isProduction
    && parsed.protocol === "http:"
    && (
      parsed.hostname === "localhost"
      || parsed.hostname === "127.0.0.1"
    );

  if (
    parsed.protocol !== "https:"
    && !localDevelopment
  ) {
    throw new InternalLoginConfigurationError(
      "SOLVYN_INTERNAL_API_BASE_URL "
      + "must use HTTPS outside local development.",
    );
  }

  if (
    parsed.username
    || parsed.password
    || parsed.search
    || parsed.hash
  ) {
    throw new InternalLoginConfigurationError(
      "SOLVYN_INTERNAL_API_BASE_URL is invalid.",
    );
  }

  parsed.pathname =
    parsed.pathname.replace(
      /\/+$/,
      "",
    );

  return parsed.toString().replace(
    /\/$/,
    "",
  );
}


export function loadInternalLoginServerConfig():
  InternalLoginServerConfig {
  const apiBaseUrl =
    validateInternalApiBaseUrl(
      requireServerEnv(
        "SOLVYN_INTERNAL_API_BASE_URL",
      ),
    );

  const internalSecret =
    requireServerEnv(
      "SOLVYN_INTERNAL_LOGIN_SECRET",
    );

  const secretBytes =
    Buffer.byteLength(
      internalSecret,
      "utf8",
    );

  if (
    secretBytes < 32
    || secretBytes > 4 * 1024
  ) {
    throw new InternalLoginConfigurationError(
      "SOLVYN_INTERNAL_LOGIN_SECRET "
      + "must contain between 32 and 4096 bytes.",
    );
  }

  return {
    apiBaseUrl,
    internalSecret,
  };
}


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
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "is invalid.",
    );
  }

  return value;
}


function parseInternalLoginSuccess(
  payload: unknown,
): InternalLoginCompletionResult {
  if (
    typeof payload !== "object"
    || payload === null
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "is invalid.",
    );
  }

  const candidate =
    payload as {
      status?: unknown;
      principal_id?: unknown;
      identity_link_id?: unknown;
      session_token?: unknown;
      session_expires_at?: unknown;
    };

  if (
    candidate.status !== "existing"
    && candidate.status !== "provisioned"
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "is invalid.",
    );
  }

  if (
    typeof candidate.session_token !== "string"
    || !candidate.session_token
    || candidate.session_token
      !== candidate.session_token.trim()
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "contains an invalid session token.",
    );
  }

  if (
    Buffer.byteLength(
      candidate.session_token,
      "utf8",
    ) < 32
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "contains an invalid session token.",
    );
  }

  if (
    typeof candidate.session_expires_at !== "string"
    || !candidate.session_expires_at
    || candidate.session_expires_at
      !== candidate.session_expires_at.trim()
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "contains an invalid session expiry.",
    );
  }

  if (
    Number.isNaN(
      Date.parse(
        candidate.session_expires_at,
      ),
    )
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "contains an invalid session expiry.",
    );
  }

  return {
    status:
      candidate.status,
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
    sessionToken:
      candidate.session_token,
    sessionExpiresAt:
      candidate.session_expires_at,
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
        > MAX_INTERNAL_LOGIN_RESPONSE_BYTES
    ) {
      throw new InternalLoginUnavailableError(
        "Internal login completion response "
        + "is invalid.",
      );
    }
  }

  let text: string;

  try {
    text =
      await response.text();
  } catch {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "could not be read.",
    );
  }

  if (
    Buffer.byteLength(
      text,
      "utf8",
    )
    > MAX_INTERNAL_LOGIN_RESPONSE_BYTES
  ) {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "is too large.",
    );
  }

  return text;
}


export async function completeInternalGoogleLogin({
  idToken,
  expectedNonce,
  transactionId,
  fetchImpl = fetch,
}: {
  idToken: string;
  expectedNonce: string;
  transactionId: string;
  fetchImpl?: typeof fetch;
}): Promise<InternalLoginCompletionResult> {
  if (
    typeof idToken !== "string"
    || !idToken
    || idToken !== idToken.trim()
  ) {
    throw new InternalLoginCompletionError(
      "Google ID token is invalid.",
    );
  }

  if (
    typeof expectedNonce !== "string"
    || !expectedNonce
    || expectedNonce !== expectedNonce.trim()
  ) {
    throw new InternalLoginCompletionError(
      "Google login nonce is invalid.",
    );
  }



  if (
    typeof transactionId !== "string"
    || !transactionId
    || transactionId !== transactionId.trim()
    || Buffer.byteLength(
      transactionId,
      "utf8",
    ) < 32
  ) {
    throw new InternalLoginCompletionError(
      "Internal login transaction ID is invalid.",
    );
  }

  const config =
    loadInternalLoginServerConfig();

  const endpoint =
    new URL(
      INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH,
      `${config.apiBaseUrl}/`,
    );

  let response: Response;

  const controller =
    new AbortController();

  const timeout =
    setTimeout(
      () => {
        controller.abort();
      },
      INTERNAL_LOGIN_REQUEST_TIMEOUT_MS,
    );

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
              id_token:
                idToken,
              expected_nonce:
                expectedNonce,
              transaction_id:
                transactionId,
            }),
          cache:
            "no-store",
          signal:
            controller.signal,
        },
      );
  } catch {
    throw new InternalLoginUnavailableError(
      "Internal interactive authentication "
      + "is temporarily unavailable.",
    );
  } finally {
    clearTimeout(timeout);
  }

  const text =
    await readBoundedText(
      response,
    );

  if (response.status === 401) {
    throw new InternalLoginRejectedError(
      "Authentication failed.",
    );
  }

  if (
    response.status === 503
    || response.status === 429
    || response.status >= 500
  ) {
    throw new InternalLoginUnavailableError(
      "Internal interactive authentication "
      + "is temporarily unavailable.",
    );
  }

  if (!response.ok) {
    throw new InternalLoginUnavailableError(
      "Internal interactive authentication "
      + "returned an unexpected response.",
    );
  }

  let payload: unknown;

  try {
    payload =
      JSON.parse(text);
  } catch {
    throw new InternalLoginUnavailableError(
      "Internal login completion response "
      + "is invalid.",
    );
  }

  return parseInternalLoginSuccess(
    payload,
  );
}
