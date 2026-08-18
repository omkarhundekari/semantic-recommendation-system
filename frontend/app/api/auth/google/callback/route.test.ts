import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  NextRequest,
} from "next/server";

import {
  GOOGLE_AUTH_TRANSACTION_COOKIE,
  createGoogleAuthTransaction,
  serializeGoogleAuthTransaction,
} from "@/lib/auth/googleAuthTransaction";

import {
  GOOGLE_TOKEN_ENDPOINT,
} from "@/lib/auth/googleCallback";

import {
  INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH,
  INTERNAL_LOGIN_SECRET_HEADER,
} from "@/lib/auth/internalLoginCompletion";

import {
  GET,
} from "./route";


const TRANSACTION_SECRET =
  "test-auth-transaction-secret-"
  + "0123456789abcdef0123456789abcdef";

const INTERNAL_SECRET =
  "test-internal-login-secret-"
  + "0123456789abcdef0123456789abcdef";

const CLIENT_ID =
  "test-client.apps.googleusercontent.com";

const REDIRECT_URI =
  "http://localhost:3000/api/auth/google/callback";


const ORIGINAL_ENV = {
  NODE_ENV:
    process.env.NODE_ENV,
  GOOGLE_OIDC_CLIENT_ID:
    process.env.GOOGLE_OIDC_CLIENT_ID,
  GOOGLE_OIDC_REDIRECT_URI:
    process.env.GOOGLE_OIDC_REDIRECT_URI,
  SOLVYN_AUTH_TRANSACTION_SECRET:
    process.env.SOLVYN_AUTH_TRANSACTION_SECRET,
  SOLVYN_INTERNAL_API_BASE_URL:
    process.env.SOLVYN_INTERNAL_API_BASE_URL,
  SOLVYN_INTERNAL_LOGIN_SECRET:
    process.env.SOLVYN_INTERNAL_LOGIN_SECRET,
};


function restore(
  name: keyof typeof ORIGINAL_ENV,
): void {
  const value =
    ORIGINAL_ENV[name];

  if (value === undefined) {
    delete process.env[name];
  } else {
    process.env[name] =
      value;
  }
}


function requestFor({
  state,
  cookie,
}: {
  state: string;
  cookie: string;
}): NextRequest {
  return new NextRequest(
    `${REDIRECT_URI}`
    + `?code=authorization-code`
    + `&state=${encodeURIComponent(state)}`,
    {
      headers: {
        Cookie:
          `${GOOGLE_AUTH_TRANSACTION_COOKIE}`
          + `=${cookie}`,
      },
    },
  );
}


describe(
  "GET /api/auth/google/callback",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      process.env.GOOGLE_OIDC_CLIENT_ID =
        CLIENT_ID;

      process.env.GOOGLE_OIDC_REDIRECT_URI =
        REDIRECT_URI;

      process.env.SOLVYN_AUTH_TRANSACTION_SECRET =
        TRANSACTION_SECRET;

      process.env.SOLVYN_INTERNAL_API_BASE_URL =
        "http://127.0.0.1:8000";

      process.env.SOLVYN_INTERNAL_LOGIN_SECRET =
        INTERNAL_SECRET;
    });

    afterEach(() => {
      vi.unstubAllGlobals();

      for (
        const name
        of Object.keys(
          ORIGINAL_ENV,
        ) as Array<
          keyof typeof ORIGINAL_ENV
        >
      ) {
        restore(name);
      }
    });

    it(
      "exchanges code, completes backend login, clears transaction, and redirects safely",
      async () => {
        const transaction =
          createGoogleAuthTransaction({
            returnTo:
              "/projects?tab=roadmap",
          });

        const cookie =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret:
                TRANSACTION_SECRET,
            },
          );

        const fetchMock =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
              init?:
                RequestInit,
            ) => {
              const url =
                String(input);

              if (
                url
                === GOOGLE_TOKEN_ENDPOINT
              ) {
                const body =
                  new URLSearchParams(
                    String(
                      init?.body,
                    ),
                  );

                expect(
                  body.get(
                    "code_verifier",
                  ),
                ).toBe(
                  transaction.codeVerifier,
                );

                expect(
                  body.has(
                    "client_secret",
                  ),
                ).toBe(false);

                return new Response(
                  JSON.stringify({
                    id_token:
                      "header.payload.signature",
                    access_token:
                      "ignored-access-token",
                  }),
                  {
                    status: 200,
                  },
                );
              }

              const backendUrl =
                new URL(url);

              expect(
                backendUrl.origin,
              ).toBe(
                "http://127.0.0.1:8000",
              );

              expect(
                backendUrl.pathname,
              ).toBe(
                INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH,
              );

              const headers =
                new Headers(
                  init?.headers,
                );

              expect(
                headers.get(
                  INTERNAL_LOGIN_SECRET_HEADER,
                ),
              ).toBe(
                INTERNAL_SECRET,
              );

              expect(
                JSON.parse(
                  String(
                    init?.body,
                  ),
                ),
              ).toEqual({
                id_token:
                  "header.payload.signature",
                expected_nonce:
                  transaction.nonce,
                transaction_id:
                  transaction.transactionId,
              });

              return new Response(
                JSON.stringify({
                  status:
                    "provisioned",
                  principal_id:
                    "prn_123",
                  identity_link_id:
                    "pil_456",
                  session_token:
                    "session-token-0123456789abcdef0123456789abcdef",
                  session_expires_at:
                    "2026-08-23T22:00:00+00:00",
                }),
                {
                  status: 200,
                },
              );
            },
          ) as typeof fetch;

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const response =
          await GET(
            requestFor({
              state:
                transaction.state,
              cookie,
            }),
          );

        expect(
          response.status,
        ).toBe(303);

        expect(
          response.headers.get(
            "location",
          ),
        ).toBe(
          "http://localhost:3000/projects?tab=roadmap",
        );

        expect(
          response.headers.get(
            "location",
          ),
        ).not.toContain(
          "prn_",
        );

        expect(
          response.headers.get(
            "location",
          ),
        ).not.toContain(
          "pil_",
        );

        expect(fetchMock).toHaveBeenCalledTimes(
          2,
        );

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(setCookie).toContain(
          GOOGLE_AUTH_TRANSACTION_COOKIE,
        );

        expect(setCookie).toContain(
          "Max-Age=0",
        );

        // Local-development/test mode deliberately uses the
        // non-__Host cookie name. The dedicated cookie-authority
        // tests separately enforce __Host-Solvyn-Session in
        // production.
        expect(setCookie).toContain(
          "solvyn_session="
          + "session-token-"
          + "0123456789abcdef"
          + "0123456789abcdef",
        );

        expect(setCookie).toContain(
          "HttpOnly",
        );

        expect(setCookie).toContain(
          "SameSite=lax",
        );

        expect(setCookie).toContain(
          "Path=/",
        );

        expect(setCookie).not.toContain(
          "Domain=",
        );

        expect(
          response.headers.get(
            "location",
          ),
        ).not.toContain(
          "session-token-",
        );

        expect(
          response.headers.get(
            "cache-control",
          ),
        ).toBe("no-store");
      },
    );

    it(
      "rejects state mismatch before any network call",
      async () => {
        const transaction =
          createGoogleAuthTransaction();

        const cookie =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret:
                TRANSACTION_SECRET,
            },
          );

        const fetchMock =
          vi.fn();

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const response =
          await GET(
            requestFor({
              state:
                `${transaction.state}wrong`,
              cookie,
            }),
          );

        expect(
          response.status,
        ).toBe(401);

        expect(fetchMock).not.toHaveBeenCalled();

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toContain(
          "Max-Age=0",
        );
      },
    );

    it(
      "requires the signed transaction cookie",
      async () => {
        const response =
          await GET(
            new NextRequest(
              `${REDIRECT_URI}`
              + "?code=authorization-code"
              + "&state=random-state",
            ),
          );

        expect(
          response.status,
        ).toBe(401);

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toContain(
          "Max-Age=0",
        );
      },
    );

    it(
      "collapses backend denial without exposing durable identity state",
      async () => {
        const transaction =
          createGoogleAuthTransaction();

        const cookie =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret:
                TRANSACTION_SECRET,
            },
          );

        const fetchMock =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              if (
                String(input)
                === GOOGLE_TOKEN_ENDPOINT
              ) {
                return new Response(
                  JSON.stringify({
                    id_token:
                      "header.payload.signature",
                  }),
                  {
                    status: 200,
                  },
                );
              }

              return new Response(
                JSON.stringify({
                  detail:
                    "Authentication failed.",
                }),
                {
                  status: 401,
                },
              );
            },
          ) as typeof fetch;

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const response =
          await GET(
            requestFor({
              state:
                transaction.state,
              cookie,
            }),
          );

        expect(
          response.status,
        ).toBe(401);

        const body =
          await response.json();

        expect(body).toEqual({
          error:
            "Authentication failed.",
        });

        expect(
          JSON.stringify(body),
        ).not.toContain(
          "principal_suspended",
        );
      },
    );

    it(
      "fails closed when backend session is already expired",
      async () => {
        const transaction =
          createGoogleAuthTransaction();

        const cookie =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret:
                TRANSACTION_SECRET,
            },
          );

        const fetchMock =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              if (
                String(input)
                === GOOGLE_TOKEN_ENDPOINT
              ) {
                return new Response(
                  JSON.stringify({
                    id_token:
                      "header.payload.signature",
                  }),
                  {
                    status: 200,
                  },
                );
              }

              return new Response(
                JSON.stringify({
                  status:
                    "existing",
                  principal_id:
                    "prn_123",
                  identity_link_id:
                    "pil_456",
                  session_token:
                    "session-token-"
                    + "0123456789abcdef"
                    + "0123456789abcdef",
                  session_expires_at:
                    "2000-01-01T00:00:00Z",
                }),
                {
                  status: 200,
                },
              );
            },
          ) as typeof fetch;

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const response =
          await GET(
            requestFor({
              state:
                transaction.state,
              cookie,
            }),
          );

        expect(
          response.status,
        ).toBe(503);

        expect(
          response.headers.get(
            "location",
          ),
        ).toBeNull();

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        // The one-time Google transaction is still cleared.
        expect(setCookie).toContain(
          GOOGLE_AUTH_TRANSACTION_COOKIE,
        );

        expect(setCookie).toContain(
          "Max-Age=0",
        );

        // But the unusable Solvyn credential must never be
        // installed in the browser.
        expect(setCookie).not.toContain(
          "solvyn_session=",
        );

        expect(setCookie).not.toContain(
          "__Host-Solvyn-Session=",
        );
      },
    );

    it(
      "maps backend outage to temporary unavailability",
      async () => {
        const transaction =
          createGoogleAuthTransaction();

        const cookie =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret:
                TRANSACTION_SECRET,
            },
          );

        const fetchMock =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              if (
                String(input)
                === GOOGLE_TOKEN_ENDPOINT
              ) {
                return new Response(
                  JSON.stringify({
                    id_token:
                      "header.payload.signature",
                  }),
                  {
                    status: 200,
                  },
                );
              }

              return new Response(
                "unavailable",
                {
                  status: 503,
                },
              );
            },
          ) as typeof fetch;

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const response =
          await GET(
            requestFor({
              state:
                transaction.state,
              cookie,
            }),
          );

        expect(
          response.status,
        ).toBe(503);

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toContain(
          "Max-Age=0",
        );
      },
    );
  },
);
