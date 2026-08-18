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


const {
  revokeBrowserSessionTokenMock,
} = vi.hoisted(
  () => ({
    revokeBrowserSessionTokenMock:
      vi.fn(),
  }),
);


vi.mock(
  "@/lib/auth/browserLogout",
  async () => {
    class BrowserLogoutUnavailableError
      extends Error {
      constructor(
        message: string,
      ) {
        super(message);

        this.name =
          "BrowserLogoutUnavailableError";
      }
    }

    return {
      BrowserLogoutUnavailableError,
      revokeBrowserSessionToken:
        revokeBrowserSessionTokenMock,
    };
  },
);


import {
  BrowserLogoutUnavailableError,
} from "@/lib/auth/browserLogout";

import {
  DEVELOPMENT_SESSION_COOKIE_NAME,
  PRODUCTION_SESSION_COOKIE_NAME,
} from "@/lib/auth/sessionCookie";

import {
  POST,
} from "./route";


const TOKEN =
  "session-token-"
  + "0123456789abcdef"
  + "0123456789abcdef";

const URL =
  "http://localhost:3000/api/auth/logout";


const ORIGINAL_NODE_ENV =
  process.env.NODE_ENV;


function restoreNodeEnv(): void {
  if (
    ORIGINAL_NODE_ENV
    === undefined
  ) {
    delete process.env.NODE_ENV;
  } else {
    process.env.NODE_ENV =
      ORIGINAL_NODE_ENV;
  }
}


function request({
  origin =
    "http://localhost:3000",
  fetchSite =
    "same-origin",
  cookieName =
    DEVELOPMENT_SESSION_COOKIE_NAME,
  token =
    TOKEN,
  includeCookie =
    true,
}: {
  origin?: string | null;
  fetchSite?: string | null;
  cookieName?: string;
  token?: string;
  includeCookie?: boolean;
} = {}): NextRequest {
  const headers =
    new Headers();

  if (origin !== null) {
    headers.set(
      "Origin",
      origin,
    );
  }

  if (fetchSite !== null) {
    headers.set(
      "Sec-Fetch-Site",
      fetchSite,
    );
  }

  if (includeCookie) {
    headers.set(
      "Cookie",
      `${cookieName}=${token}`,
    );
  }

  return new NextRequest(
    URL,
    {
      method: "POST",
      headers,
    },
  );
}


function expectNoStoreHeaders(
  response: Response,
): void {
  expect(
    response.headers.get(
      "cache-control",
    ),
  ).toBe(
    "no-store",
  );

  expect(
    response.headers.get(
      "pragma",
    ),
  ).toBe(
    "no-cache",
  );

  expect(
    response.headers.get(
      "vary",
    ),
  ).toBe(
    "Cookie",
  );
}


describe(
  "POST /api/auth/logout",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      revokeBrowserSessionTokenMock
        .mockReset();
    });

    afterEach(() => {
      restoreNodeEnv();
    });


    it(
      "revokes session and clears development cookie",
      async () => {
        revokeBrowserSessionTokenMock
          .mockResolvedValue({
            clearCookie: true,
          });

        const response =
          await POST(
            request(),
          );

        expect(
          response.status,
        ).toBe(
          204,
        );

        expect(
          revokeBrowserSessionTokenMock,
        ).toHaveBeenCalledTimes(
          1,
        );

        expect(
          revokeBrowserSessionTokenMock,
        ).toHaveBeenCalledWith({
          sessionToken:
            TOKEN,
        });

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(
          setCookie,
        ).not.toBeNull();

        expect(
          setCookie,
        ).toContain(
          `${DEVELOPMENT_SESSION_COOKIE_NAME}=`,
        );

        expect(
          setCookie,
        ).not.toContain(
          `${PRODUCTION_SESSION_COOKIE_NAME}=`,
        );

        expect(
          setCookie,
        ).toContain(
          "HttpOnly",
        );

        expect(
          setCookie,
        ).toContain(
          "Path=/",
        );

        expect(
          setCookie,
        ).toContain(
          "SameSite=lax",
        );

        expect(
          setCookie,
        ).toContain(
          "Max-Age=0",
        );

        expect(
          setCookie,
        ).toContain(
          "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        );

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "is idempotently successful with no session cookie",
      async () => {
        const response =
          await POST(
            request({
              includeCookie:
                false,
            }),
          );

        expect(
          response.status,
        ).toBe(
          204,
        );

        expect(
          revokeBrowserSessionTokenMock,
        ).not.toHaveBeenCalled();

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toBeNull();

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "clears browser credential when revocation is unavailable",
      async () => {
        revokeBrowserSessionTokenMock
          .mockRejectedValue(
            new BrowserLogoutUnavailableError(
              "backend unavailable",
            ),
          );

        const response =
          await POST(
            request(),
          );

        expect(
          response.status,
        ).toBe(
          503,
        );

        expect(
          await response.json(),
        ).toEqual({
          error:
            "Logout is temporarily unavailable.",
        });

        // Explicit logout destroys the local browser
        // credential even when durable revocation cannot
        // be confirmed.
        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(setCookie).not.toBeNull();

        expect(setCookie).toContain(
          `${DEVELOPMENT_SESSION_COOKIE_NAME}=`,
        );

        expect(setCookie).toContain(
          "Path=/",
        );

        expect(setCookie).toContain(
          "HttpOnly",
        );

        expect(setCookie).toContain(
          "SameSite=lax",
        );

        expect(setCookie).toContain(
          "Max-Age=0",
        );

        expect(setCookie).toContain(
          "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        );

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "rejects cross-origin logout before revocation",
      async () => {
        const response =
          await POST(
            request({
              origin:
                "https://attacker.example",
              fetchSite:
                "cross-site",
            }),
          );

        expect(
          response.status,
        ).toBe(
          403,
        );

        expect(
          await response.json(),
        ).toEqual({
          error:
            "Request rejected.",
        });

        expect(
          revokeBrowserSessionTokenMock,
        ).not.toHaveBeenCalled();

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toBeNull();

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "rejects missing Origin before revocation",
      async () => {
        const response =
          await POST(
            request({
              origin: null,
            }),
          );

        expect(
          response.status,
        ).toBe(
          403,
        );

        expect(
          revokeBrowserSessionTokenMock,
        ).not.toHaveBeenCalled();

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toBeNull();
      },
    );


    it(
      "clears hardened production cookie after definitive logout",
      async () => {
        process.env.NODE_ENV =
          "production";

        revokeBrowserSessionTokenMock
          .mockResolvedValue({
            clearCookie: true,
          });

        const response =
          await POST(
            request({
              cookieName:
                PRODUCTION_SESSION_COOKIE_NAME,
            }),
          );

        expect(
          response.status,
        ).toBe(
          204,
        );

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(
          setCookie,
        ).toContain(
          `${PRODUCTION_SESSION_COOKIE_NAME}=`,
        );

        expect(
          setCookie,
        ).not.toContain(
          `${DEVELOPMENT_SESSION_COOKIE_NAME}=`,
        );

        expect(
          setCookie,
        ).toContain(
          "Secure",
        );

        expect(
          setCookie,
        ).toContain(
          "HttpOnly",
        );

        expect(
          setCookie,
        ).toContain(
          "Path=/",
        );

        expect(
          setCookie,
        ).toContain(
          "SameSite=lax",
        );

        expect(
          setCookie,
        ).toContain(
          "Max-Age=0",
        );

        expect(
          setCookie,
        ).toContain(
          "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        );

        expect(
          setCookie?.toLowerCase(),
        ).not.toContain(
          "domain=",
        );
      },
    );


    it(
      "does not accept development cookie in production",
      async () => {
        process.env.NODE_ENV =
          "production";

        const response =
          await POST(
            request({
              cookieName:
                DEVELOPMENT_SESSION_COOKIE_NAME,
            }),
          );

        expect(
          response.status,
        ).toBe(
          204,
        );

        expect(
          revokeBrowserSessionTokenMock,
        ).not.toHaveBeenCalled();

        expect(
          response.headers.get(
            "set-cookie",
          ),
        ).toBeNull();
      },
    );


    it(
      "does not swallow unexpected programming errors",
      async () => {
        revokeBrowserSessionTokenMock
          .mockRejectedValue(
            new TypeError(
              "programming bug",
            ),
          );

        await expect(
          POST(
            request(),
          ),
        ).rejects.toThrow(
          "programming bug",
        );
      },
    );
  },
);
