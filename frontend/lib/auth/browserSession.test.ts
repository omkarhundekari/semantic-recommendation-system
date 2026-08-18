import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  cookies,
} from "next/headers";

import {
  INTERNAL_LOGIN_SECRET_HEADER,
} from "@/lib/auth/internalLoginCompletion";

import {
  DEVELOPMENT_SESSION_COOKIE_NAME,
  PRODUCTION_SESSION_COOKIE_NAME,
} from "@/lib/auth/sessionCookie";

import {
  BrowserSessionUnavailableError,
  INTERNAL_SESSION_RESOLVE_PATH,
  resolveBrowserSession,
  resolveBrowserSessionToken,
} from "./browserSession";


vi.mock(
  "next/headers",
  () => ({
    cookies:
      vi.fn(),
  }),
);


const INTERNAL_SECRET =
  "test-internal-login-secret-"
  + "0123456789abcdef0123456789abcdef";

const SESSION_TOKEN =
  "session-token-"
  + "0123456789abcdef0123456789abcdef";

const SESSION_RESPONSE = {
  principal_id:
    "prn_123e4567-e89b-42d3-a456-426614174001",
  identity_link_id:
    "pil_123e4567-e89b-42d3-a456-426614174002",
  session_id:
    "ses_123e4567-e89b-42d3-a456-426614174003",
  session_expires_at:
    "2026-08-23T22:00:00+00:00",
};


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
  "browser session resolver",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      process.env.SOLVYN_INTERNAL_API_BASE_URL =
        "http://127.0.0.1:8000";

      process.env.SOLVYN_INTERNAL_LOGIN_SECRET =
        INTERNAL_SECRET;

      vi.mocked(
        cookies,
      ).mockReset();
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
      "resolves an opaque session through the protected internal API",
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
                INTERNAL_SESSION_RESOLVE_PATH,
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
                session_token:
                  SESSION_TOKEN,
              });

              expect(
                init?.cache,
              ).toBe(
                "no-store",
              );

              return new Response(
                JSON.stringify(
                  SESSION_RESPONSE,
                ),
                {
                  status: 200,
                },
              );
            },
          ) as typeof fetch;

        const result =
          await resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          });

        expect(result).toEqual({
          authenticated: true,
          principalId:
            SESSION_RESPONSE.principal_id,
          identityLinkId:
            SESSION_RESPONSE.identity_link_id,
          sessionId:
            SESSION_RESPONSE.session_id,
          sessionExpiresAt:
            SESSION_RESPONSE.session_expires_at,
        });

        expect(fetchImpl).toHaveBeenCalledTimes(
          1,
        );
      },
    );

    it(
      "collapses stale or rejected session to unauthenticated",
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

        const result =
          await resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          });

        expect(result).toEqual({
          authenticated: false,
          clearCookie: true,
        });
      },
    );

    it(
      "does not send malformed browser session tokens",
      async () => {
        const fetchImpl =
          vi.fn();

        const result =
          await resolveBrowserSessionToken({
            sessionToken:
              "short",
            fetchImpl:
              fetchImpl as typeof fetch,
          });

        expect(result).toEqual({
          authenticated: false,
          clearCookie: true,
        });

        expect(fetchImpl).not.toHaveBeenCalled();
      },
    );

    it(
      "maps backend outage to unavailable",
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
          resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserSessionUnavailableError,
        );
      },
    );

    it(
      "maps network failure to unavailable",
      async () => {
        const fetchImpl =
          vi.fn(
            async () => {
              throw new Error(
                "network unavailable",
              );
            },
          ) as typeof fetch;

        await expect(
          resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserSessionUnavailableError,
        );
      },
    );

    it(
      "rejects malformed successful response",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  ...SESSION_RESPONSE,
                  session_id:
                    "wrong-prefix",
                }),
                {
                  status: 200,
                },
              ),
          ) as typeof fetch;

        await expect(
          resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserSessionUnavailableError,
        );
      },
    );

    it(
      "rejects timezone-less backend expiry",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  ...SESSION_RESPONSE,
                  session_expires_at:
                    "2026-08-23T22:00:00",
                }),
                {
                  status: 200,
                },
              ),
          ) as typeof fetch;

        await expect(
          resolveBrowserSessionToken({
            sessionToken:
              SESSION_TOKEN,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserSessionUnavailableError,
        );
      },
    );

    it(
      "returns unauthenticated without network when cookie is absent",
      async () => {
        vi.mocked(
          cookies,
        ).mockResolvedValue(
          {
            get:
              vi.fn(
                () =>
                  undefined,
              ),
          } as Awaited<
            ReturnType<typeof cookies>
          >,
        );

        const fetchMock =
          vi.fn();

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const result =
          await resolveBrowserSession();

        expect(result).toEqual({
          authenticated: false,
          clearCookie: false,
        });

        expect(fetchMock).not.toHaveBeenCalled();
      },
    );

    it(
      "reads only the development cookie outside production",
      async () => {
        process.env.NODE_ENV =
          "test";

        const get =
          vi.fn(
            (
              name: string,
            ) => {
              expect(name).toBe(
                DEVELOPMENT_SESSION_COOKIE_NAME,
              );

              return {
                name,
                value:
                  SESSION_TOKEN,
              };
            },
          );

        vi.mocked(
          cookies,
        ).mockResolvedValue(
          {
            get,
          } as unknown as Awaited<
            ReturnType<typeof cookies>
          >,
        );

        vi.stubGlobal(
          "fetch",
          vi.fn(
            async () =>
              new Response(
                JSON.stringify(
                  SESSION_RESPONSE,
                ),
                {
                  status: 200,
                },
              ),
          ),
        );

        const result =
          await resolveBrowserSession();

        expect(
          result.authenticated,
        ).toBe(true);

        expect(get).toHaveBeenCalledWith(
          DEVELOPMENT_SESSION_COOKIE_NAME,
        );

        expect(get).not.toHaveBeenCalledWith(
          PRODUCTION_SESSION_COOKIE_NAME,
        );
      },
    );

    it(
      "reads only the __Host- cookie in production",
      async () => {
        process.env.NODE_ENV =
          "production";

        process.env.SOLVYN_INTERNAL_API_BASE_URL =
          "https://internal.example.test";

        const get =
          vi.fn(
            (
              name: string,
            ) => {
              expect(name).toBe(
                PRODUCTION_SESSION_COOKIE_NAME,
              );

              return {
                name,
                value:
                  SESSION_TOKEN,
              };
            },
          );

        vi.mocked(
          cookies,
        ).mockResolvedValue(
          {
            get,
          } as unknown as Awaited<
            ReturnType<typeof cookies>
          >,
        );

        vi.stubGlobal(
          "fetch",
          vi.fn(
            async () =>
              new Response(
                JSON.stringify(
                  SESSION_RESPONSE,
                ),
                {
                  status: 200,
                },
              ),
          ),
        );

        const result =
          await resolveBrowserSession();

        expect(
          result.authenticated,
        ).toBe(true);

        expect(get).toHaveBeenCalledWith(
          PRODUCTION_SESSION_COOKIE_NAME,
        );

        expect(get).not.toHaveBeenCalledWith(
          DEVELOPMENT_SESSION_COOKIE_NAME,
        );
      },
    );
  },
);
