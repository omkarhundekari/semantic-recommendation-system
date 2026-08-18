import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  INTERNAL_LOGIN_SECRET_HEADER,
} from "./internalLoginCompletion";

import {
  BROWSER_SESSION_HEADER,
  BrowserProfileUnavailableError,
  MAX_PRODUCT_ME_RESPONSE_BYTES,
  PRODUCT_ME_PATH,
  resolveBrowserProfileToken,
} from "./browserProfile";


const INTERNAL_SECRET =
  "test-internal-login-secret-"
  + "0123456789abcdef0123456789abcdef";

const SESSION_TOKEN =
  "session-token-"
  + "0123456789abcdef0123456789abcdef";


const ORIGINAL_ENV = {
  SOLVYN_INTERNAL_API_BASE_URL:
    process.env
      .SOLVYN_INTERNAL_API_BASE_URL,

  SOLVYN_INTERNAL_LOGIN_SECRET:
    process.env
      .SOLVYN_INTERNAL_LOGIN_SECRET,
};


function restoreEnv(): void {
  for (
    const [
      name,
      value,
    ]
    of Object.entries(
      ORIGINAL_ENV,
    )
  ) {
    if (value === undefined) {
      delete process.env[
        name
      ];
    } else {
      process.env[
        name
      ] = value;
    }
  }
}


describe(
  "browser profile backend bridge",
  () => {
    beforeEach(
      () => {
        process.env
          .SOLVYN_INTERNAL_API_BASE_URL =
            "http://127.0.0.1:8000";

        process.env
          .SOLVYN_INTERNAL_LOGIN_SECRET =
            INTERNAL_SECRET;
      },
    );

    afterEach(
      () => {
        restoreEnv();
        vi.restoreAllMocks();
      },
    );


    it(
      "forwards the opaque session directly to /v1/me",
      async () => {
        const fetchImpl =
          vi.fn(
            async (
              input,
              init,
            ) => {
              const url =
                new URL(
                  String(input),
                );

              expect(
                url.pathname,
              ).toBe(
                PRODUCT_ME_PATH,
              );

              expect(
                init?.method,
              ).toBe(
                "GET",
              );

              expect(
                init?.cache,
              ).toBe(
                "no-store",
              );

              const headers =
                new Headers(
                  init?.headers,
                );

              expect(
                headers.get(
                  BROWSER_SESSION_HEADER,
                ),
              ).toBe(
                SESSION_TOKEN,
              );

              expect(
                headers.get(
                  INTERNAL_LOGIN_SECRET_HEADER,
                ),
              ).toBe(
                INTERNAL_SECRET,
              );

              expect(
                headers.get(
                  "Authorization",
                ),
              ).toBeNull();

              expect(
                init?.body,
              ).toBeUndefined();

              return new Response(
                JSON.stringify({
                  principal_id:
                    "prn_123e4567-e89b-42d3-a456-426614174001",
                  principal_kind:
                    "human",
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
          ) as unknown as typeof fetch;

        const result =
          await resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          });

        expect(result).toEqual({
          authenticated: true,
          profile: {
            principalId:
              "prn_123e4567-e89b-42d3-a456-426614174001",
            principalKind:
              "human",
          },
        });

        expect(fetchImpl).toHaveBeenCalledTimes(
          1,
        );
      },
    );


    it(
      "returns only the minimal validated profile",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  principal_id:
                    "prn_123e4567-e89b-42d3-a456-426614174001",
                  principal_kind:
                    "human",

                  identity_link_id:
                    "pil_must_not_escape",

                  issuer:
                    "https://accounts.google.com",

                  subject:
                    "google-subject-must-not-escape",

                  session_token:
                    "session-must-not-escape",
                }),
                {
                  status: 200,
                },
              ),
          ) as unknown as typeof fetch;

        const result =
          await resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          });

        expect(result).toEqual({
          authenticated: true,
          profile: {
            principalId:
              "prn_123e4567-e89b-42d3-a456-426614174001",
            principalKind:
              "human",
          },
        });

        const serialized =
          JSON.stringify(
            result,
          );

        expect(
          serialized,
        ).not.toContain(
          "pil_must_not_escape",
        );

        expect(
          serialized,
        ).not.toContain(
          "accounts.google.com",
        );

        expect(
          serialized,
        ).not.toContain(
          "google-subject-must-not-escape",
        );

        expect(
          serialized,
        ).not.toContain(
          "session-must-not-escape",
        );
      },
    );


    it(
      "maps backend 401 to definitive stale session",
      async () => {
        const result =
          await resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,

            fetchImpl:
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
              ) as unknown as typeof fetch,
          });

        expect(result).toEqual({
          authenticated: false,
          clearCookie: true,
        });
      },
    );


    it(
      "preserves the browser credential when the internal transport is rejected",
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
                  status: 403,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
          ) as typeof fetch;

        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );

        expect(
          fetchImpl,
        ).toHaveBeenCalledTimes(1);
      },
    );


    it(
      "preserves credential semantics on backend outage",
      async () => {
        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,

            fetchImpl:
              vi.fn(
                async () =>
                  new Response(
                    JSON.stringify({
                      detail:
                        "temporarily unavailable",
                    }),
                    {
                      status: 503,
                    },
                  ),
              ) as unknown as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );
      },
    );


    it(
      "preserves credential semantics on network failure",
      async () => {
        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,

            fetchImpl:
              vi.fn(
                async () => {
                  throw new Error(
                    "network unavailable",
                  );
                },
              ) as unknown as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );
      },
    );


    it(
      "rejects malformed successful backend responses",
      async () => {
        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,

            fetchImpl:
              vi.fn(
                async () =>
                  new Response(
                    JSON.stringify({
                      principal_id:
                        "not-a-principal",
                      principal_kind:
                        "human",
                    }),
                    {
                      status: 200,
                    },
                  ),
              ) as unknown as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );
      },
    );


    it(
      "rejects oversized backend responses",
      async () => {
        const body =
          "x".repeat(
            MAX_PRODUCT_ME_RESPONSE_BYTES
            + 1,
          );

        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,

            fetchImpl:
              vi.fn(
                async () =>
                  new Response(
                    body,
                    {
                      status: 200,
                    },
                  ),
              ) as unknown as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );
      },
    );


    it(
      "treats a malformed local session credential as stale",
      async () => {
        const fetchImpl =
          vi.fn();

        const result =
          await resolveBrowserProfileToken({
            sessionToken:
              "too-short",
            fetchImpl:
              fetchImpl as unknown as typeof fetch,
          });

        expect(result).toEqual({
          authenticated: false,
          clearCookie: true,
        });

        expect(
          fetchImpl,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "fails unavailable when server configuration is missing",
      async () => {
        delete process.env
          .SOLVYN_INTERNAL_LOGIN_SECRET;

        await expect(
          resolveBrowserProfileToken({
            sessionToken:
              SESSION_TOKEN,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProfileUnavailableError,
        );
      },
    );
  },
);
