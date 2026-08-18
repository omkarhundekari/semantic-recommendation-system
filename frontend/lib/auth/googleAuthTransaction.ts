import {
  createHash,
  createHmac,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";


export const GOOGLE_AUTH_TRANSACTION_TTL_SECONDS =
  10 * 60;

export const GOOGLE_AUTH_TRANSACTION_VERSION = 1;

export const GOOGLE_AUTH_TRANSACTION_COOKIE =
  "solvyn_google_auth_transaction";


export type GoogleAuthTransaction = {
  version: 1;
  transactionId: string;
  state: string;
  nonce: string;
  codeVerifier: string;
  codeChallenge: string;
  returnTo: string;
  createdAt: number;
  expiresAt: number;
};


export class GoogleAuthTransactionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GoogleAuthTransactionError";
  }
}


function base64UrlEncode(
  value: Buffer,
): string {
  return value
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}


function randomBase64Url(
  bytes: number,
): string {
  return base64UrlEncode(
    randomBytes(bytes),
  );
}


export function buildPkceCodeChallenge(
  codeVerifier: string,
): string {
  if (
    typeof codeVerifier !== "string"
    || codeVerifier.length < 43
  ) {
    throw new GoogleAuthTransactionError(
      "PKCE code verifier is invalid.",
    );
  }

  return base64UrlEncode(
    createHash("sha256")
      .update(codeVerifier, "utf8")
      .digest(),
  );
}


export function normalizeAuthReturnTo(
  value: string | null | undefined,
): string {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return "/";
  }

  if (
    !value.startsWith("/")
    || value.startsWith("//")
    || value.includes("\\")
    || /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication return path is invalid.",
    );
  }

  const parsed = new URL(
    value,
    "https://solvyn.local",
  );

  if (
    parsed.origin !== "https://solvyn.local"
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication return path is invalid.",
    );
  }

  return (
    parsed.pathname
    + parsed.search
    + parsed.hash
  );
}


export function createGoogleAuthTransaction({
  now = Date.now(),
  returnTo = "/",
}: {
  now?: number;
  returnTo?: string;
} = {}): GoogleAuthTransaction {
  if (
    !Number.isSafeInteger(now)
    || now < 0
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction time is invalid.",
    );
  }

  const transactionId = randomBase64Url(32);
  const state = randomBase64Url(32);
  const nonce = randomBase64Url(32);

  // 32 random bytes become a 43-character
  // base64url value, satisfying the PKCE
  // verifier length requirement.
  const codeVerifier = randomBase64Url(32);

  const createdAt = now;
  const expiresAt =
    createdAt
    + (
      GOOGLE_AUTH_TRANSACTION_TTL_SECONDS
      * 1000
    );

  return {
    version:
      GOOGLE_AUTH_TRANSACTION_VERSION,
    transactionId,
    state,
    nonce,
    codeVerifier,
    codeChallenge:
      buildPkceCodeChallenge(codeVerifier),
    returnTo:
      normalizeAuthReturnTo(returnTo),
    createdAt,
    expiresAt,
  };
}


function requireSigningSecret(
  secret: string,
): Buffer {
  if (typeof secret !== "string") {
    throw new GoogleAuthTransactionError(
      "Authentication transaction secret "
      + "is invalid.",
    );
  }

  const encoded = Buffer.from(
    secret,
    "utf8",
  );

  if (encoded.byteLength < 32) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction secret "
      + "must contain at least 32 bytes.",
    );
  }

  return encoded;
}


function signPayload(
  payload: string,
  secret: string,
): string {
  return base64UrlEncode(
    createHmac(
      "sha256",
      requireSigningSecret(secret),
    )
      .update(payload, "utf8")
      .digest(),
  );
}


export function serializeGoogleAuthTransaction(
  transaction: GoogleAuthTransaction,
  {
    secret,
  }: {
    secret: string;
  },
): string {
  const payload = base64UrlEncode(
    Buffer.from(
      JSON.stringify(transaction),
      "utf8",
    ),
  );

  const signature =
    signPayload(payload, secret);

  return `${payload}.${signature}`;
}


function constantTimeSignatureMatches(
  expected: string,
  received: string,
): boolean {
  const expectedBytes = Buffer.from(
    expected,
    "utf8",
  );
  const receivedBytes = Buffer.from(
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


function parseTransactionPayload(
  payload: string,
): GoogleAuthTransaction {
  let parsed: unknown;

  try {
    parsed = JSON.parse(
      Buffer.from(
        payload,
        "base64url",
      ).toString("utf8"),
    );
  } catch {
    throw new GoogleAuthTransactionError(
      "Authentication transaction is invalid.",
    );
  }

  if (
    typeof parsed !== "object"
    || parsed === null
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction is invalid.",
    );
  }

  const candidate =
    parsed as Partial<
      GoogleAuthTransaction
    >;

  if (
    candidate.version
      !== GOOGLE_AUTH_TRANSACTION_VERSION
    || typeof candidate.transactionId !== "string"
    || candidate.transactionId.length < 32
    || typeof candidate.state !== "string"
    || candidate.state.length < 32
    || typeof candidate.nonce !== "string"
    || candidate.nonce.length < 32
    || typeof candidate.codeVerifier
      !== "string"
    || candidate.codeVerifier.length < 43
    || typeof candidate.codeChallenge
      !== "string"
    || typeof candidate.returnTo
      !== "string"
    || !Number.isSafeInteger(
      candidate.createdAt,
    )
    || !Number.isSafeInteger(
      candidate.expiresAt,
    )
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction is invalid.",
    );
  }

  if (
    buildPkceCodeChallenge(
      candidate.codeVerifier,
    )
    !== candidate.codeChallenge
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction PKCE "
      + "state is invalid.",
    );
  }

  return {
    version:
      GOOGLE_AUTH_TRANSACTION_VERSION,
    transactionId:
      candidate.transactionId,
    state: candidate.state,
    nonce: candidate.nonce,
    codeVerifier:
      candidate.codeVerifier,
    codeChallenge:
      candidate.codeChallenge,
    returnTo:
      normalizeAuthReturnTo(
        candidate.returnTo,
      ),
    createdAt:
      candidate.createdAt as number,
    expiresAt:
      candidate.expiresAt as number,
  };
}


export function deserializeGoogleAuthTransaction(
  value: string,
  {
    secret,
    now = Date.now(),
  }: {
    secret: string;
    now?: number;
  },
): GoogleAuthTransaction {
  if (
    typeof value !== "string"
    || !value
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction is missing.",
    );
  }

  const pieces = value.split(".");

  if (pieces.length !== 2) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction is invalid.",
    );
  }

  const [
    payload,
    receivedSignature,
  ] = pieces;

  const expectedSignature =
    signPayload(
      payload,
      secret,
    );

  if (
    !constantTimeSignatureMatches(
      expectedSignature,
      receivedSignature,
    )
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction signature "
      + "is invalid.",
    );
  }

  const transaction =
    parseTransactionPayload(payload);

  if (
    !Number.isSafeInteger(now)
    || now < 0
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction time "
      + "is invalid.",
    );
  }

  if (transaction.expiresAt <= now) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction has expired.",
    );
  }

  if (
    transaction.expiresAt
    <= transaction.createdAt
  ) {
    throw new GoogleAuthTransactionError(
      "Authentication transaction lifetime "
      + "is invalid.",
    );
  }

  return transaction;
}
