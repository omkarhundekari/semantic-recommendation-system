import {
  describe,
  expect,
  it,
} from "vitest";

import {
  createGoogleAuthTransaction,
} from "./googleAuthTransaction";

import {
  buildGoogleAuthorizationUrl,
} from "./googleAuthorization";


const NOW = 1_785_000_000_000;


describe(
  "Google authorization request",
  () => {
    it(
      "builds authorization-code OIDC request with PKCE",
      () => {
        const transaction =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo: "/projects",
          });

        const result =
          buildGoogleAuthorizationUrl({
            clientId:
              "test-client.apps.googleusercontent.com",
            redirectUri:
              "http://localhost:3000/api/auth/google/callback",
            transaction,
          });

        expect(result.origin).toBe(
          "https://accounts.google.com",
        );

        expect(result.pathname).toBe(
          "/o/oauth2/v2/auth",
        );

        expect(
          result.searchParams.get(
            "client_id",
          ),
        ).toBe(
          "test-client.apps.googleusercontent.com",
        );

        expect(
          result.searchParams.get(
            "response_type",
          ),
        ).toBe("code");

        expect(
          result.searchParams.get(
            "scope",
          ),
        ).toBe("openid email");

        expect(
          result.searchParams.get(
            "state",
          ),
        ).toBe(
          transaction.state,
        );

        expect(
          result.searchParams.get(
            "nonce",
          ),
        ).toBe(
          transaction.nonce,
        );

        expect(
          result.searchParams.get(
            "code_challenge",
          ),
        ).toBe(
          transaction.codeChallenge,
        );

        expect(
          result.searchParams.get(
            "code_challenge_method",
          ),
        ).toBe("S256");

        expect(
          result.searchParams.has(
            "client_secret",
          ),
        ).toBe(false);

        expect(
          result.searchParams.has(
            "access_type",
          ),
        ).toBe(false);

        expect(
          result.searchParams.has(
            "prompt",
          ),
        ).toBe(false);
      },
    );

    it(
      "does not put returnTo into Google's request",
      () => {
        const transaction =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo:
              "/workspace?tab=roadmap",
          });

        const result =
          buildGoogleAuthorizationUrl({
            clientId: "client",
            redirectUri:
              "http://localhost:3000/api/auth/google/callback",
            transaction,
          });

        expect(
          result.toString(),
        ).not.toContain(
          "workspace",
        );

        expect(
          result.searchParams.has(
            "returnTo",
          ),
        ).toBe(false);
      },
    );
  },
);
