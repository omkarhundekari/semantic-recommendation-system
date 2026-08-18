import {
  describe,
  expect,
  it,
} from "vitest";

import {
  DEVELOPMENT_SESSION_COOKIE_NAME,
  MAX_SESSION_COOKIE_LIFETIME_SECONDS,
  PRODUCTION_SESSION_COOKIE_NAME,
  SessionCookieError,
  buildClearedSessionCookie,
  buildSessionCookie,
  getSessionCookieName,
} from "./sessionCookie";


const NOW =
  Date.parse(
    "2026-08-16T23:00:00.000Z",
  );

const TOKEN =
  "session-token-"
  + "0123456789abcdef"
  + "0123456789abcdef";


describe(
  "session cookie authority",
  () => {
    it(
      "uses __Host- cookie in production",
      () => {
        expect(
          getSessionCookieName({
            production: true,
          }),
        ).toBe(
          PRODUCTION_SESSION_COOKIE_NAME,
        );

        expect(
          PRODUCTION_SESSION_COOKIE_NAME,
        ).toBe(
          "__Host-Solvyn-Session",
        );
      },
    );


    it(
      "uses non-prefixed cookie on local development",
      () => {
        expect(
          getSessionCookieName({
            production: false,
          }),
        ).toBe(
          DEVELOPMENT_SESSION_COOKIE_NAME,
        );

        expect(
          DEVELOPMENT_SESSION_COOKIE_NAME
          .startsWith("__Host-"),
        ).toBe(false);
      },
    );


    it(
      "builds hardened production cookie",
      () => {
        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt:
              "2026-08-23T23:00:00.000Z",
            nowMs:
              NOW,
            production:
              true,
          });

        expect(cookie).toEqual({
          name:
            "__Host-Solvyn-Session",
          value:
            TOKEN,
          options: {
            httpOnly: true,
            secure: true,
            sameSite: "lax",
            path: "/",
            maxAge:
              7 * 24 * 60 * 60,
          },
        });

        expect(
          "domain"
          in cookie.options,
        ).toBe(false);

        expect(
          "expires"
          in cookie.options,
        ).toBe(false);
      },
    );


    it(
      "allows insecure cookie only for non-production development",
      () => {
        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt:
              "2026-08-16T23:10:00.000Z",
            nowMs:
              NOW,
            production:
              false,
          });

        expect(
          cookie.name,
        ).toBe(
          DEVELOPMENT_SESSION_COOKIE_NAME,
        );

        expect(
          cookie.options.secure,
        ).toBe(false);

        expect(
          cookie.options.httpOnly,
        ).toBe(true);

        expect(
          cookie.options.sameSite,
        ).toBe("lax");

        expect(
          cookie.options.path,
        ).toBe("/");
      },
    );


    it(
      "derives Max-Age exclusively from backend expiry",
      () => {
        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt:
              "2026-08-16T23:02:03.900Z",
            nowMs:
              NOW,
            production:
              true,
          });

        expect(
          cookie.options.maxAge,
        ).toBe(123);
      },
    );


    it(
      "accepts backend timezone-offset expiry",
      () => {
        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt:
              "2026-08-17T00:00:00+01:00",
            nowMs:
              Date.parse(
                "2026-08-16T22:00:00Z",
              ),
            production:
              true,
          });

        expect(
          cookie.options.maxAge,
        ).toBe(3600);
      },
    );


    it.each([
      "",
      " ",
      "short-token",
      ` ${TOKEN}`,
      `${TOKEN} `,
    ])(
      "rejects invalid session token %j",
      (token) => {
        expect(
          () =>
            buildSessionCookie({
              token,
              expiresAt:
                "2026-08-17T00:00:00Z",
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          SessionCookieError,
        );
      },
    );


    it(
      "rejects oversized session token",
      () => {
        expect(
          () =>
            buildSessionCookie({
              token:
                "x".repeat(1025),
              expiresAt:
                "2026-08-17T00:00:00Z",
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          SessionCookieError,
        );
      },
    );


    it.each([
      "",
      "not-a-date",
      "2026-08-23",
      "2026-08-23T22:00:00",
      " 2026-08-23T22:00:00Z",
      "2026-08-23T22:00:00Z ",
    ])(
      "rejects invalid or timezone-less expiry %j",
      (expiresAt) => {
        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt,
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          SessionCookieError,
        );
      },
    );


    it(
      "rejects already expired session",
      () => {
        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt:
                "2026-08-16T22:59:59Z",
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          "Session is already expired.",
        );
      },
    );


    it(
      "rejects session expiring exactly now",
      () => {
        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt:
                "2026-08-16T23:00:00Z",
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          "Session is already expired.",
        );
      },
    );


    it(
      "rejects sub-second remaining session",
      () => {
        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt:
                "2026-08-16T23:00:00.500Z",
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          "Session is already expired.",
        );
      },
    );


    it(
      "allows the backend maximum lifetime",
      () => {
        const expiresAt =
          new Date(
            NOW
            + (
              MAX_SESSION_COOKIE_LIFETIME_SECONDS
              * 1000
            ),
          ).toISOString();

        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt,
            nowMs:
              NOW,
            production:
              true,
          });

        expect(
          cookie.options.maxAge,
        ).toBe(
          MAX_SESSION_COOKIE_LIFETIME_SECONDS,
        );
      },
    );


    it(
      "rejects cookie lifetime beyond backend maximum",
      () => {
        const expiresAt =
          new Date(
            NOW
            + (
              (
                MAX_SESSION_COOKIE_LIFETIME_SECONDS
                + 1
              )
              * 1000
            ),
          ).toISOString();

        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt,
              nowMs:
                NOW,
              production:
                true,
            }),
        ).toThrow(
          "maximum supported lifetime",
        );
      },
    );


    it.each([
      Number.NaN,
      Number.POSITIVE_INFINITY,
      -1,
      1.5,
    ])(
      "rejects invalid current time %s",
      (nowMs) => {
        expect(
          () =>
            buildSessionCookie({
              token:
                TOKEN,
              expiresAt:
                "2026-08-17T00:00:00Z",
              nowMs,
              production:
                true,
            }),
        ).toThrow(
          SessionCookieError,
        );
      },
    );


    it(
      "does not create Domain or Expires attributes",
      () => {
        const cookie =
          buildSessionCookie({
            token:
              TOKEN,
            expiresAt:
              "2026-08-17T00:00:00Z",
            nowMs:
              NOW,
            production:
              true,
          });

        expect(
          Object.keys(
            cookie.options,
          ).sort(),
        ).toEqual(
          [
            "httpOnly",
            "maxAge",
            "path",
            "sameSite",
            "secure",
          ].sort(),
        );
      },
    );
  },
);


describe(
  "cleared session cookie",
  () => {
    it(
      "clears production cookie with the same hardened scope",
      () => {
        const issued =
          buildSessionCookie({
            token:
              "session-token-0123456789abcdef0123456789abcdef",
            expiresAt:
              "2026-08-23T22:00:00Z",
            nowMs:
              Date.parse(
                "2026-08-16T22:00:00Z",
              ),
            production: true,
          });

        const cleared =
          buildClearedSessionCookie({
            production: true,
          });

        expect(cleared.name).toBe(
          "__Host-Solvyn-Session",
        );

        expect(cleared.value).toBe("");

        expect(cleared.options).toEqual(
          expect.objectContaining({
            httpOnly:
              issued.options.httpOnly,
            secure:
              issued.options.secure,
            sameSite:
              issued.options.sameSite,
            path:
              issued.options.path,
            maxAge: 0,
          }),
        );

        expect(
          cleared.options.expires,
        ).toEqual(
          new Date(0),
        );

        expect(
          "domain" in cleared.options,
        ).toBe(false);
      },
    );

    it(
      "clears only the development cookie outside production",
      () => {
        const cleared =
          buildClearedSessionCookie({
            production: false,
          });

        expect(cleared.name).toBe(
          "solvyn_session",
        );

        expect(
          cleared.name,
        ).not.toBe(
          "__Host-Solvyn-Session",
        );

        expect(
          cleared.options.secure,
        ).toBe(false);

        expect(
          cleared.options.path,
        ).toBe("/");

        expect(
          cleared.options.maxAge,
        ).toBe(0);

        expect(
          cleared.options.expires,
        ).toEqual(
          new Date(0),
        );
      },
    );

    it(
      "keeps issuance and clearing attributes structurally aligned",
      () => {
        for (
          const production
          of [
            false,
            true,
          ]
        ) {
          const issued =
            buildSessionCookie({
              token:
                "session-token-0123456789abcdef0123456789abcdef",
              expiresAt:
                "2026-08-23T22:00:00Z",
              nowMs:
                Date.parse(
                  "2026-08-16T22:00:00Z",
                ),
              production,
            });

          const cleared =
            buildClearedSessionCookie({
              production,
            });

          expect(
            cleared.name,
          ).toBe(
            issued.name,
          );

          expect(
            cleared.options.httpOnly,
          ).toBe(
            issued.options.httpOnly,
          );

          expect(
            cleared.options.secure,
          ).toBe(
            issued.options.secure,
          );

          expect(
            cleared.options.sameSite,
          ).toBe(
            issued.options.sameSite,
          );

          expect(
            cleared.options.path,
          ).toBe(
            issued.options.path,
          );
        }
      },
    );
  },
);
