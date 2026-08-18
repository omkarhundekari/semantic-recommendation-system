import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH,
  INTERNAL_LOGIN_SECRET_HEADER,
  InternalLoginRejectedError,
  InternalLoginUnavailableError,
  completeInternalGoogleLogin,
} from "./internalLoginCompletion";


const SECRET =
  "test-internal-login-secret-"
  + "0123456789abcdef0123456789abcdef";


const ORIGINAL_ENV = {
  NODE_ENV:
    process.env.NODE_ENV,
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


describe(
  "internal Google login completion",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      process.env.SOLVYN_INTERNAL_API_BASE_URL =
        "http://127.0.0.1:8000";

      process.env.SOLVYN_INTERNAL_LOGIN_SECRET =
        SECRET;
    });

    afterEach(() => {
      restore("NODE_ENV");
      restore(
        "SOLVYN_INTERNAL_API_BASE_URL",
      );
      restore(
        "SOLVYN_INTERNAL_LOGIN_SECRET",
      );
    });

    it(
      "sends raw ID token and nonce to the protected backend boundary",
      async () => {
        const fetchImpl =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
              init?:
                RequestInit,
            ) => {
              const url =
                new URL(
                  String(input),
                );

              expect(
                url.origin,
              ).toBe(
                "http://127.0.0.1:8000",
              );

              expect(
                url.pathname,
              ).toBe(
                INTERNAL_GOOGLE_LOGIN_COMPLETE_PATH,
              );

              expect(
                init?.method,
              ).toBe("POST");

              const headers =
                new Headers(
                  init?.headers,
                );

              expect(
                headers.get(
                  INTERNAL_LOGIN_SECRET_HEADER,
                ),
              ).toBe(
                SECRET,
              );

              expect(
                JSON.parse(
                  String(init?.body),
                ),
              ).toEqual({
                id_token:
                  "signed-google-id-token",
                expected_nonce:
                  "expected-nonce",
              transaction_id:
                "transaction-id-0123456789abcdef0123456789abcdef",
              });

              return new Response(
                JSON.stringify({
                  status:
                    "existing",
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
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              );
            },
          ) as typeof fetch;

        const result =
          await completeInternalGoogleLogin({
            idToken:
              "signed-google-id-token",
            expectedNonce:
              "expected-nonce",
            transactionId:
              "transaction-id-0123456789abcdef0123456789abcdef",
            fetchImpl,
          });

        expect(result).toEqual({
          status:
            "existing",
          principalId:
            "prn_123",
          identityLinkId:
            "pil_456",
          sessionToken:
            "session-token-0123456789abcdef0123456789abcdef",
          sessionExpiresAt:
            "2026-08-23T22:00:00+00:00",
        });
      },
    );

    it(
      "collapses backend authentication denial",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  detail:
                    "Authentication failed.",
                }),
                {
                  status: 401,
                },
              ),
          ) as typeof fetch;

        await expect(
          completeInternalGoogleLogin({
            idToken:
              "signed-google-id-token",
            expectedNonce:
              "expected-nonce",
            transactionId:
              "transaction-id-0123456789abcdef0123456789abcdef",
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          InternalLoginRejectedError,
        );
      },
    );

    it(
      "treats backend outage as unavailable",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                "unavailable",
                {
                  status: 503,
                },
              ),
          ) as typeof fetch;

        await expect(
          completeInternalGoogleLogin({
            idToken:
              "signed-google-id-token",
            expectedNonce:
              "expected-nonce",
            transactionId:
              "transaction-id-0123456789abcdef0123456789abcdef",
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          InternalLoginUnavailableError,
        );
      },
    );
  },
);
