import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";


const {
  resolveBrowserSessionMock,
} = vi.hoisted(
  () => ({
    resolveBrowserSessionMock:
      vi.fn(),
  }),
);


vi.mock(
  "@/lib/auth/browserSession",
  async () => {
    class BrowserSessionUnavailableError
      extends Error {
      constructor(
        message: string,
      ) {
        super(message);

        this.name =
          "BrowserSessionUnavailableError";
      }
    }

    return {
      BrowserSessionUnavailableError,
      resolveBrowserSession:
        resolveBrowserSessionMock,
    };
  },
);


import {
  BrowserSessionUnavailableError,
} from "@/lib/auth/browserSession";

import {
  DEVELOPMENT_SESSION_COOKIE_NAME,
  PRODUCTION_SESSION_COOKIE_NAME,
} from "@/lib/auth/sessionCookie";

import {
  GET,
} from "./route";


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
  "GET /api/auth/session",
  () => {
    beforeEach(() => {
      process.env.NODE_ENV =
        "test";

      resolveBrowserSessionMock
        .mockReset();
    });

    afterEach(() => {
      restoreNodeEnv();
    });


    it(
      "returns unauthenticated without clearing when no cookie exists",
      async () => {
        resolveBrowserSessionMock
          .mockResolvedValue({
            authenticated: false,
            clearCookie: false,
          });

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(200);

        expect(
          await response.json(),
        ).toEqual({
          authenticated: false,
        });

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
      "returns only authenticated true for a valid session",
      async () => {
        resolveBrowserSessionMock
          .mockResolvedValue({
            authenticated: true,
            principalId:
              "prn_internal_only",
            identityLinkId:
              "pil_internal_only",
            sessionId:
              "ses_internal_only",
            sessionExpiresAt:
              "2026-08-23T22:00:00+00:00",
          });

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(200);

        const body =
          await response.json();

        expect(body).toEqual({
          authenticated: true,
        });

        const serialized =
          JSON.stringify(
            body,
          );

        expect(
          serialized,
        ).not.toContain(
          "prn_internal_only",
        );

        expect(
          serialized,
        ).not.toContain(
          "pil_internal_only",
        );

        expect(
          serialized,
        ).not.toContain(
          "ses_internal_only",
        );

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
      "clears a definitively stale development session",
      async () => {
        resolveBrowserSessionMock
          .mockResolvedValue({
            authenticated: false,
            clearCookie: true,
          });

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(200);

        expect(
          await response.json(),
        ).toEqual({
          authenticated: false,
        });

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(setCookie).not.toBeNull();

        expect(setCookie).toContain(
          `${DEVELOPMENT_SESSION_COOKIE_NAME}=`,
        );

        expect(setCookie).not.toContain(
          `${PRODUCTION_SESSION_COOKIE_NAME}=`,
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
      "clears the hardened production cookie with matching scope",
      async () => {
        process.env.NODE_ENV =
          "production";

        resolveBrowserSessionMock
          .mockResolvedValue({
            authenticated: false,
            clearCookie: true,
          });

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(200);

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(setCookie).not.toBeNull();

        expect(setCookie).toContain(
          `${PRODUCTION_SESSION_COOKIE_NAME}=`,
        );

        expect(setCookie).not.toContain(
          `${DEVELOPMENT_SESSION_COOKIE_NAME}=`,
        );

        expect(setCookie).toContain(
          "Secure",
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

        expect(setCookie).toContain(
          "Max-Age=0",
        );

        expect(setCookie).toContain(
          "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        );

        expect(
          setCookie?.toLowerCase(),
        ).not.toContain(
          "domain=",
        );

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "preserves the cookie when session resolution is unavailable",
      async () => {
        resolveBrowserSessionMock
          .mockRejectedValue(
            new BrowserSessionUnavailableError(
              "backend unavailable",
            ),
          );

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(503);

        const body =
          await response.json();

        expect(body).toEqual({
          error:
            "Session authentication is temporarily unavailable.",
        });

        expect(
          body,
        ).not.toHaveProperty(
          "authenticated",
        );

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
      "does not expose internal identity state on unavailable response",
      async () => {
        resolveBrowserSessionMock
          .mockRejectedValue(
            new BrowserSessionUnavailableError(
              "prn_secret pil_secret ses_secret",
            ),
          );

        const response =
          await GET();

        const body =
          await response.text();

        expect(
          response.status,
        ).toBe(503);

        expect(body).not.toContain(
          "prn_secret",
        );

        expect(body).not.toContain(
          "pil_secret",
        );

        expect(body).not.toContain(
          "ses_secret",
        );

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
        resolveBrowserSessionMock
          .mockRejectedValue(
            new TypeError(
              "unexpected programming failure",
            ),
          );

        await expect(
          GET(),
        ).rejects.toBeInstanceOf(
          TypeError,
        );
      },
    );
  },
);
