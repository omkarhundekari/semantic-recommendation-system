import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  BrowserProfileUnavailableError,
  resolveBrowserProfile,
} from "@/lib/auth/browserProfile";

import {
  DEVELOPMENT_SESSION_COOKIE_NAME,
  PRODUCTION_SESSION_COOKIE_NAME,
} from "@/lib/auth/sessionCookie";

import {
  GET,
} from "./route";


vi.mock(
  "@/lib/auth/browserProfile",
  async () => {
    const actual =
      await vi.importActual<
        typeof import(
          "@/lib/auth/browserProfile"
        )
      >(
        "@/lib/auth/browserProfile",
      );

    return {
      ...actual,
      resolveBrowserProfile:
        vi.fn(),
    };
  },
);


const resolveBrowserProfileMock =
  vi.mocked(
    resolveBrowserProfile,
  );


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

  const vary =
    new Set(
      (
        response.headers.get(
          "vary",
        )
        ?? ""
      )
        .split(",")
        .map(
          (value) =>
            value
              .trim()
              .toLowerCase(),
        )
        .filter(Boolean),
    );

  expect(
    vary.has("cookie"),
  ).toBe(true);
}


describe(
  "GET /api/me",
  () => {
    const originalNodeEnv =
      process.env.NODE_ENV;

    beforeEach(
      () => {
        process.env.NODE_ENV =
          "development";

        resolveBrowserProfileMock
          .mockReset();
      },
    );

    afterEach(
      () => {
        process.env.NODE_ENV =
          originalNodeEnv;
      },
    );


    it(
      "returns unauthenticated when no browser session exists",
      async () => {
        resolveBrowserProfileMock
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
      "returns only minimal browser-safe principal profile",
      async () => {
        resolveBrowserProfileMock
          .mockResolvedValue({
            authenticated: true,
            profile: {
              principalId:
                "prn_123e4567-e89b-42d3-a456-426614174001",
              principalKind:
                "human",
            },
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
          principal: {
            principal_id:
              "prn_123e4567-e89b-42d3-a456-426614174001",
            principal_kind:
              "human",
          },
        });

        const serialized =
          JSON.stringify(
            body,
          );

        expect(
          serialized,
        ).not.toContain(
          "identity_link",
        );

        expect(
          serialized,
        ).not.toContain(
          "issuer",
        );

        expect(
          serialized,
        ).not.toContain(
          "subject",
        );

        expect(
          serialized,
        ).not.toContain(
          "session",
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
      "clears a definitively stale development credential",
      async () => {
        resolveBrowserProfileMock
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
          "HttpOnly",
        );

        expect(setCookie).toContain(
          "Path=/",
        );

        expect(setCookie).toContain(
          "SameSite=lax",
        );

        expect(setCookie).toContain(
          "Max-Age=0",
        );

        expectNoStoreHeaders(
          response,
        );
      },
    );


    it(
      "clears the hardened production credential",
      async () => {
        process.env.NODE_ENV =
          "production";

        resolveBrowserProfileMock
          .mockResolvedValue({
            authenticated: false,
            clearCookie: true,
          });

        const response =
          await GET();

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
      "preserves the browser credential on backend unavailability",
      async () => {
        resolveBrowserProfileMock
          .mockRejectedValue(
            new BrowserProfileUnavailableError(
              "backend unavailable",
            ),
          );

        const response =
          await GET();

        expect(
          response.status,
        ).toBe(503);

        expect(
          await response.json(),
        ).toEqual({
          error:
            "Principal profile is temporarily unavailable.",
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
      "does not expose internal error or credential material",
      async () => {
        resolveBrowserProfileMock
          .mockRejectedValue(
            new BrowserProfileUnavailableError(
              "prn_secret "
              + "pil_secret "
              + "session-token-secret "
              + "internal-secret",
            ),
          );

        const response =
          await GET();

        const text =
          await response.text();

        expect(
          response.status,
        ).toBe(503);

        expect(text).not.toContain(
          "prn_secret",
        );

        expect(text).not.toContain(
          "pil_secret",
        );

        expect(text).not.toContain(
          "session-token-secret",
        );

        expect(text).not.toContain(
          "internal-secret",
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
        resolveBrowserProfileMock
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
