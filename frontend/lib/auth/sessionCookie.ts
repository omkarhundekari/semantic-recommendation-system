export const
  PRODUCTION_SESSION_COOKIE_NAME =
    "__Host-Solvyn-Session";

export const
  DEVELOPMENT_SESSION_COOKIE_NAME =
    "solvyn_session";


export const
  MIN_SESSION_TOKEN_BYTES = 32;

export const
  MAX_SESSION_TOKEN_BYTES = 1024;

export const
  MAX_SESSION_COOKIE_LIFETIME_SECONDS =
    30 * 24 * 60 * 60;


const SESSION_EXPIRY_WITH_TIMEZONE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;


export class SessionCookieError
  extends Error {
  constructor(message: string) {
    super(message);
    this.name =
      "SessionCookieError";
  }
}


export type SessionCookieOptions = {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: "/";
  maxAge: number;
  expires?: Date;
};


export type SessionCookie = {
  name: string;
  value: string;
  options: SessionCookieOptions;
};


type SessionCookieBaseAttributes = {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: "/";
};


function getSessionCookieBaseAttributes({
  production,
}: {
  production: boolean;
}): SessionCookieBaseAttributes {
  return {
    httpOnly: true,
    secure: production,
    sameSite: "lax",
    path: "/",
  };
}


function requireSessionToken(
  token: string,
): string {
  if (
    typeof token !== "string"
    || !token
    || token !== token.trim()
  ) {
    throw new SessionCookieError(
      "Session token is invalid.",
    );
  }

  const bytes =
    Buffer.byteLength(
      token,
      "utf8",
    );

  if (
    bytes < MIN_SESSION_TOKEN_BYTES
    || bytes > MAX_SESSION_TOKEN_BYTES
  ) {
    throw new SessionCookieError(
      "Session token is invalid.",
    );
  }

  return token;
}


function parseSessionExpiry(
  expiresAt: string,
): number {
  if (
    typeof expiresAt !== "string"
    || !expiresAt
    || expiresAt !== expiresAt.trim()
    || !SESSION_EXPIRY_WITH_TIMEZONE.test(
      expiresAt,
    )
  ) {
    throw new SessionCookieError(
      "Session expiry is invalid.",
    );
  }

  const expiresAtMs =
    Date.parse(expiresAt);

  if (!Number.isFinite(expiresAtMs)) {
    throw new SessionCookieError(
      "Session expiry is invalid.",
    );
  }

  return expiresAtMs;
}


export function getSessionCookieName({
  production =
    process.env.NODE_ENV === "production",
}: {
  production?: boolean;
} = {}): string {
  return production
    ? PRODUCTION_SESSION_COOKIE_NAME
    : DEVELOPMENT_SESSION_COOKIE_NAME;
}


export function buildSessionCookie({
  token,
  expiresAt,
  nowMs = Date.now(),
  production =
    process.env.NODE_ENV === "production",
}: {
  token: string;
  expiresAt: string;
  nowMs?: number;
  production?: boolean;
}): SessionCookie {
  const normalizedToken =
    requireSessionToken(token);

  if (
    !Number.isFinite(nowMs)
    || !Number.isSafeInteger(nowMs)
    || nowMs < 0
  ) {
    throw new SessionCookieError(
      "Current session-cookie time is invalid.",
    );
  }

  const expiresAtMs =
    parseSessionExpiry(
      expiresAt,
    );

  const lifetimeMs =
    expiresAtMs - nowMs;

  if (lifetimeMs <= 0) {
    throw new SessionCookieError(
      "Session is already expired.",
    );
  }

  const maxAge =
    Math.floor(
      lifetimeMs / 1000,
    );

  if (maxAge <= 0) {
    throw new SessionCookieError(
      "Session is already expired.",
    );
  }

  if (
    maxAge
    > MAX_SESSION_COOKIE_LIFETIME_SECONDS
  ) {
    throw new SessionCookieError(
      "Session expiry exceeds the "
      + "maximum supported lifetime.",
    );
  }

  return {
    name:
      getSessionCookieName({
        production,
      }),
    value:
      normalizedToken,
    options: {
      ...getSessionCookieBaseAttributes({
        production,
      }),
      maxAge,
    },
  };
}


export function buildClearedSessionCookie({
  production =
    process.env.NODE_ENV === "production",
}: {
  production?: boolean;
} = {}): SessionCookie {
  return {
    name:
      getSessionCookieName({
        production,
      }),
    value: "",
    options: {
      ...getSessionCookieBaseAttributes({
        production,
      }),
      maxAge: 0,
      expires:
        new Date(0),
    },
  };
}
