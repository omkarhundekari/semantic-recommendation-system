import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  createGoogleAuthTransaction,
} from "./googleAuthTransaction";

import {
  GOOGLE_TOKEN_ENDPOINT,
  GoogleCallbackProtocolError,
  GoogleTokenExchangeRejectedError,
  GoogleTokenExchangeUnavailableError,
  exchangeGoogleAuthorizationCode,
  parseGoogleAuthorizationCallback,
} from "./googleCallback";


const NOW =
  1_785_000_000_000;

const CLIENT_ID =
  "test-client.apps.googleusercontent.com";

const REDIRECT_URI =
  "http://localhost:3000/api/auth/google/callback";


function transaction() {
  return createGoogleAuthTransaction({
    now: NOW,
    returnTo: "/projects",
  });
}


describe(
  "Google authorization callback protocol",
  () => {
    it(
      "accepts one authorization code with matching state",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.set(
          "code",
          "authorization-code",
        );

        callback.searchParams.set(
          "state",
          current.state,
        );

        expect(
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toEqual({
          kind:
            "authorization_code",
          code:
            "authorization-code",
        });
      },
    );

    it(
      "rejects a state mismatch",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.set(
          "code",
          "authorization-code",
        );

        callback.searchParams.set(
          "state",
          `${current.state}x`,
        );

        expect(() =>
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toThrow(
          GoogleCallbackProtocolError,
        );
      },
    );

    it(
      "rejects repeated state parameters",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.append(
          "state",
          current.state,
        );

        callback.searchParams.append(
          "state",
          current.state,
        );

        callback.searchParams.set(
          "code",
          "authorization-code",
        );

        expect(() =>
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toThrow(
          /repeated/i,
        );
      },
    );

    it(
      "maps Google access_denied without exposing another state",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.set(
          "error",
          "access_denied",
        );

        callback.searchParams.set(
          "state",
          current.state,
        );

        expect(
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toEqual({
          kind:
            "authorization_denied",
        });
      },
    );

    it(
      "rejects unsupported Google callback errors",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.set(
          "error",
          "server_error",
        );

        callback.searchParams.set(
          "state",
          current.state,
        );

        expect(() =>
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toThrow(
          /unsupported error/i,
        );
      },
    );

    it(
      "rejects callback containing both code and error",
      () => {
        const current =
          transaction();

        const callback =
          new URL(REDIRECT_URI);

        callback.searchParams.set(
          "code",
          "authorization-code",
        );

        callback.searchParams.set(
          "error",
          "access_denied",
        );

        callback.searchParams.set(
          "state",
          current.state,
        );

        expect(() =>
          parseGoogleAuthorizationCallback({
            callbackUrl:
              callback,
            transaction:
              current,
          }),
        ).toThrow(
          /conflicting/i,
        );
      },
    );
  },
);


describe(
  "Google authorization-code exchange",
  () => {
    it(
      "posts the PKCE authorization-code exchange without a client secret",
      async () => {
        const current =
          transaction();

        const fetchImpl =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
              init?:
                RequestInit,
            ) => {
              expect(
                input,
              ).toBe(
                GOOGLE_TOKEN_ENDPOINT,
              );

              expect(
                init?.method,
              ).toBe("POST");

              const body =
                new URLSearchParams(
                  String(init?.body),
                );

              expect(
                body.get(
                  "client_id",
                ),
              ).toBe(
                CLIENT_ID,
              );

              expect(
                body.get(
                  "code",
                ),
              ).toBe(
                "authorization-code",
              );

              expect(
                body.get(
                  "code_verifier",
                ),
              ).toBe(
                current.codeVerifier,
              );

              expect(
                body.get(
                  "grant_type",
                ),
              ).toBe(
                "authorization_code",
              );

              expect(
                body.get(
                  "redirect_uri",
                ),
              ).toBe(
                REDIRECT_URI,
              );

              expect(
                body.has(
                  "client_secret",
                ),
              ).toBe(false);

              return new Response(
                JSON.stringify({
                  access_token:
                    "access-token-we-do-not-retain",
                  token_type:
                    "Bearer",
                  expires_in:
                    3600,
                  id_token:
                    "header.payload.signature",
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
          await exchangeGoogleAuthorizationCode({
            clientId:
              CLIENT_ID,
            redirectUri:
              REDIRECT_URI,
            code:
              "authorization-code",
            codeVerifier:
              current.codeVerifier,
            fetchImpl,
          });

        expect(result).toEqual({
          idToken:
            "header.payload.signature",
        });

        expect(
          "accessToken" in result,
        ).toBe(false);
      },
    );

    it(
      "rejects a successful response without an ID token",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  access_token:
                    "access-token",
                }),
                {
                  status: 200,
                },
              ),
          ) as typeof fetch;

        await expect(
          exchangeGoogleAuthorizationCode({
            clientId:
              CLIENT_ID,
            redirectUri:
              REDIRECT_URI,
            code:
              "authorization-code",
            codeVerifier:
              transaction()
                .codeVerifier,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          GoogleTokenExchangeUnavailableError,
        );
      },
    );

    it(
      "classifies a rejected authorization code separately",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  error:
                    "invalid_grant",
                }),
                {
                  status: 400,
                },
              ),
          ) as typeof fetch;

        await expect(
          exchangeGoogleAuthorizationCode({
            clientId:
              CLIENT_ID,
            redirectUri:
              REDIRECT_URI,
            code:
              "authorization-code",
            codeVerifier:
              transaction()
                .codeVerifier,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          GoogleTokenExchangeRejectedError,
        );
      },
    );

    it(
      "classifies Google server failure as unavailable",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                "temporary failure",
                {
                  status: 503,
                },
              ),
          ) as typeof fetch;

        await expect(
          exchangeGoogleAuthorizationCode({
            clientId:
              CLIENT_ID,
            redirectUri:
              REDIRECT_URI,
            code:
              "authorization-code",
            codeVerifier:
              transaction()
                .codeVerifier,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          GoogleTokenExchangeUnavailableError,
        );
      },
    );

    it(
      "fails closed when the network request fails",
      async () => {
        const fetchImpl =
          vi.fn(
            async () => {
              throw new Error(
                "network unavailable",
              );
            },
          ) as unknown as typeof fetch;

        await expect(
          exchangeGoogleAuthorizationCode({
            clientId:
              CLIENT_ID,
            redirectUri:
              REDIRECT_URI,
            code:
              "authorization-code",
            codeVerifier:
              transaction()
                .codeVerifier,
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          GoogleTokenExchangeUnavailableError,
        );
      },
    );
  },
);
