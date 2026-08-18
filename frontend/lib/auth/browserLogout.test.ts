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
  BrowserLogoutUnavailableError,
  INTERNAL_SESSION_REVOKE_PATH,
  revokeBrowserSessionToken,
} from "./browserLogout";


const INTERNAL_SECRET =
  "test-internal-login-secret-"
  + "0123456789abcdef"
  + "0123456789abcdef";

const TOKEN =
  "session-token-"
  + "0123456789abcdef"
  + "0123456789abcdef";


const ORIGINAL_ENV = {
  NODE_ENV:
    process.env.NODE_ENV,

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
    if (
      value === undefined
    ) {
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
  "browser logout authority",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      process.env
        .SOLVYN_INTERNAL_API_BASE_URL =
        "http://127.0.0.1:8000";

      process.env
        .SOLVYN_INTERNAL_LOGIN_SECRET =
        INTERNAL_SECRET;
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      restoreEnv();
    });


    it(
      "revokes the opaque session through the protected internal API",
      async () => {
        const fetchMock =
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
                INTERNAL_SESSION_REVOKE_PATH,
              );

              expect(
                init?.method,
              ).toBe(
                "POST",
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
                headers.get(
                  "Content-Type",
                ),
              ).toBe(
                "application/json",
              );

              expect(
                JSON.parse(
                  String(
                    init?.body,
                  ),
                ),
              ).toEqual({
                session_token:
                  TOKEN,
              });

              expect(
                init?.cache,
              ).toBe(
                "no-store",
              );

              return new Response(
                null,
                {
                  status: 204,
                },
              );
            },
          ) as typeof fetch;

        const result =
          await revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock,
          });

        expect(
          result,
        ).toEqual({
          clearCookie: true,
        });

        expect(
          fetchMock,
        ).toHaveBeenCalledTimes(
          1,
        );
      },
    );


    it.each([
      "",
      " ",
      "short",
      " session-token-0123456789abcdef0123456789abcdef",
      "session-token-0123456789abcdef0123456789abcdef ",
    ])(
      "clears malformed credential locally without network: %j",
      async (
        sessionToken,
      ) => {
        const fetchMock =
          vi.fn();

        const result =
          await revokeBrowserSessionToken({
            sessionToken,
            fetchImpl:
              fetchMock as typeof fetch,
          });

        expect(
          result,
        ).toEqual({
          clearCookie: true,
        });

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "preserves browser credential on backend 503",
      async () => {
        const fetchMock =
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
          revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock,
          }),
        ).rejects.toBeInstanceOf(
          BrowserLogoutUnavailableError,
        );
      },
    );


    it(
      "does not treat internal authentication 401 as successful logout",
      async () => {
        const fetchMock =
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
          revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock,
          }),
        ).rejects.toBeInstanceOf(
          BrowserLogoutUnavailableError,
        );
      },
    );


    it(
      "preserves browser credential on network failure",
      async () => {
        const fetchMock =
          vi.fn(
            async () => {
              throw new Error(
                "network down",
              );
            },
          ) as typeof fetch;

        await expect(
          revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock,
          }),
        ).rejects.toBeInstanceOf(
          BrowserLogoutUnavailableError,
        );
      },
    );


    it(
      "preserves browser credential on unexpected successful status",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  ok: true,
                }),
                {
                  status: 200,
                },
              ),
          ) as typeof fetch;

        await expect(
          revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock,
          }),
        ).rejects.toBeInstanceOf(
          BrowserLogoutUnavailableError,
        );
      },
    );


    it(
      "fails unavailable when internal configuration is missing",
      async () => {
        delete process.env
          .SOLVYN_INTERNAL_API_BASE_URL;

        const fetchMock =
          vi.fn();

        await expect(
          revokeBrowserSessionToken({
            sessionToken:
              TOKEN,
            fetchImpl:
              fetchMock as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserLogoutUnavailableError,
        );

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();
      },
    );
  },
);
