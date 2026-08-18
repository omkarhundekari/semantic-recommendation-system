import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";

import {
  NextRequest,
} from "next/server";

import {
  GOOGLE_AUTH_TRANSACTION_COOKIE,
  deserializeGoogleAuthTransaction,
} from "@/lib/auth/googleAuthTransaction";

import {
  GET,
} from "./route";


const SECRET =
  "test-solvyn-auth-transaction-secret-12345678901234567890";


const ORIGINAL_ENV = {
  NODE_ENV:
    process.env.NODE_ENV,
  GOOGLE_OIDC_CLIENT_ID:
    process.env.GOOGLE_OIDC_CLIENT_ID,
  GOOGLE_OIDC_REDIRECT_URI:
    process.env.GOOGLE_OIDC_REDIRECT_URI,
  SOLVYN_AUTH_TRANSACTION_SECRET:
    process.env.SOLVYN_AUTH_TRANSACTION_SECRET,
};


function restoreEnv(
  name: keyof typeof ORIGINAL_ENV,
): void {
  const original =
    ORIGINAL_ENV[name];

  if (original === undefined) {
    delete process.env[name];
  } else {
    process.env[name] =
      original;
  }
}


describe(
  "GET /api/auth/google/start",
  () => {
    beforeEach(() => {
      process.env.GOOGLE_OIDC_CLIENT_ID =
        "test-client.apps.googleusercontent.com";

      process.env.GOOGLE_OIDC_REDIRECT_URI =
        "http://localhost:3000/api/auth/google/callback";

      process.env.SOLVYN_AUTH_TRANSACTION_SECRET =
        SECRET;
    });

    afterEach(() => {
      restoreEnv(
        "NODE_ENV",
      );

      restoreEnv(
        "GOOGLE_OIDC_CLIENT_ID",
      );

      restoreEnv(
        "GOOGLE_OIDC_REDIRECT_URI",
      );

      restoreEnv(
        "SOLVYN_AUTH_TRANSACTION_SECRET",
      );
    });

    it(
      "redirects to Google and stores signed transaction cookie",
      async () => {
        const request =
          new NextRequest(
            "http://localhost:3000/api/auth/google/start"
            + "?returnTo=%2Fprojects%3Ftab%3Droadmap",
          );

        const response =
          await GET(request);

        expect(
          response.status,
        ).toBe(302);

        const location =
          response.headers.get(
            "location",
          );

        expect(location).not.toBeNull();

        const googleUrl =
          new URL(
            location as string,
          );

        expect(
          googleUrl.origin,
        ).toBe(
          "https://accounts.google.com",
        );

        expect(
          googleUrl.searchParams.get(
            "response_type",
          ),
        ).toBe("code");

        expect(
          googleUrl.searchParams.get(
            "code_challenge_method",
          ),
        ).toBe("S256");

        const cookie =
          response.cookies.get(
            GOOGLE_AUTH_TRANSACTION_COOKIE,
          );

        expect(cookie).toBeDefined();

        const restored =
          deserializeGoogleAuthTransaction(
            cookie!.value,
            {
              secret: SECRET,
              now: Date.now(),
            },
          );

        expect(
          restored.returnTo,
        ).toBe(
          "/projects?tab=roadmap",
        );

        expect(
          googleUrl.searchParams.get(
            "state",
          ),
        ).toBe(
          restored.state,
        );

        expect(
          googleUrl.searchParams.get(
            "nonce",
          ),
        ).toBe(
          restored.nonce,
        );

        expect(
          googleUrl.searchParams.get(
            "code_challenge",
          ),
        ).toBe(
          restored.codeChallenge,
        );

        const setCookie =
          response.headers.get(
            "set-cookie",
          );

        expect(setCookie).toContain(
          "HttpOnly",
        );

        expect(setCookie).toContain(
          "SameSite=lax",
        );

        expect(setCookie).toContain(
          "Path=/api/auth/google",
        );

        expect(
          response.headers.get(
            "cache-control",
          ),
        ).toBe("no-store");
      },
    );

    it(
      "rejects an unsafe return path before redirecting",
      async () => {
        const request =
          new NextRequest(
            "http://localhost:3000/api/auth/google/start"
            + "?returnTo=https%3A%2F%2Fevil.example",
          );

        const response =
          await GET(request);

        expect(
          response.status,
        ).toBe(400);

        expect(
          response.headers.get(
            "location",
          ),
        ).toBeNull();

        expect(
          response.cookies.get(
            GOOGLE_AUTH_TRANSACTION_COOKIE,
          ),
        ).toBeUndefined();
      },
    );

    it(
      "fails closed when server auth configuration is missing",
      async () => {
        delete process.env.GOOGLE_OIDC_CLIENT_ID;

        const request =
          new NextRequest(
            "http://localhost:3000/api/auth/google/start",
          );

        const response =
          await GET(request);

        expect(
          response.status,
        ).toBe(503);

        expect(
          response.headers.get(
            "location",
          ),
        ).toBeNull();

        expect(
          response.cookies.get(
            GOOGLE_AUTH_TRANSACTION_COOKIE,
          ),
        ).toBeUndefined();
      },
    );
  },
);
