import {
  describe,
  expect,
  it,
} from "vitest";

import {
  GOOGLE_AUTH_TRANSACTION_TTL_SECONDS,
  GoogleAuthTransactionError,
  buildPkceCodeChallenge,
  createGoogleAuthTransaction,
  deserializeGoogleAuthTransaction,
  normalizeAuthReturnTo,
  serializeGoogleAuthTransaction,
} from "./googleAuthTransaction";


const SECRET =
  "test-only-solvyn-auth-transaction-secret-123456789";

const OTHER_SECRET =
  "different-test-solvyn-auth-transaction-secret-987654321";

const NOW = 1_785_000_000_000;


describe(
  "Google authentication transaction",
  () => {
    it(
      "creates unique state, nonce, and PKCE values",
      () => {
        const first =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo: "/projects",
          });

        const second =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo: "/projects",
          });

        expect(
          first.transactionId,
        ).not.toBe(
          second.transactionId,
        );

        expect(first.state).not.toBe(
          second.state,
        );

        expect(first.nonce).not.toBe(
          second.nonce,
        );

        expect(first.codeVerifier).not.toBe(
          second.codeVerifier,
        );

        expect(first.codeChallenge).toBe(
          buildPkceCodeChallenge(
            first.codeVerifier,
          ),
        );

        expect(first.returnTo).toBe(
          "/projects",
        );

        expect(first.expiresAt).toBe(
          NOW
          + (
            GOOGLE_AUTH_TRANSACTION_TTL_SECONDS
            * 1000
          ),
        );
      },
    );

    it(
      "round trips through a signed cookie payload",
      () => {
        const transaction =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo:
              "/workspace?from=login",
          });

        const serialized =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret: SECRET,
            },
          );

        const restored =
          deserializeGoogleAuthTransaction(
            serialized,
            {
              secret: SECRET,
              now: NOW + 1000,
            },
          );

        expect(restored).toEqual(
          transaction,
        );
      },
    );

    it(
      "preserves transaction ID through signed round trip",
      () => {
        const transaction =
          createGoogleAuthTransaction({
            now: NOW,
            returnTo: "/projects",
          });

        const serialized =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret: SECRET,
            },
          );

        const restored =
          deserializeGoogleAuthTransaction(
            serialized,
            {
              secret: SECRET,
              now: NOW + 1,
            },
          );

        expect(
          restored.transactionId,
        ).toBe(
          transaction.transactionId,
        );
      },
    );

    it(
      "rejects tampered transaction payloads",
      () => {
        const transaction =
          createGoogleAuthTransaction({
            now: NOW,
          });

        const serialized =
          serializeGoogleAuthTransaction(
            transaction,
            {
              secret: SECRET,
            },
          );

        const [
          payload,
          signature,
        ] = serialized.split(".");

        const tampered =
          `${
            payload.slice(0, -1)
          }A.${signature}`;

        expect(() =>
          deserializeGoogleAuthTransaction(
            tampered,
            {
              secret: SECRET,
              now: NOW + 1,
            },
          ),
        ).toThrow(
          GoogleAuthTransactionError,
        );
      },
    );

    it(
      "rejects a transaction signed by another secret",
      () => {
        const serialized =
          serializeGoogleAuthTransaction(
            createGoogleAuthTransaction({
              now: NOW,
            }),
            {
              secret: SECRET,
            },
          );

        expect(() =>
          deserializeGoogleAuthTransaction(
            serialized,
            {
              secret: OTHER_SECRET,
              now: NOW + 1,
            },
          ),
        ).toThrow(
          /signature/i,
        );
      },
    );

    it(
      "rejects expired transactions",
      () => {
        const serialized =
          serializeGoogleAuthTransaction(
            createGoogleAuthTransaction({
              now: NOW,
            }),
            {
              secret: SECRET,
            },
          );

        expect(() =>
          deserializeGoogleAuthTransaction(
            serialized,
            {
              secret: SECRET,
              now:
                NOW
                + (
                  GOOGLE_AUTH_TRANSACTION_TTL_SECONDS
                  * 1000
                ),
            },
          ),
        ).toThrow(
          /expired/i,
        );
      },
    );

    it(
      "rejects secrets shorter than 32 bytes",
      () => {
        expect(() =>
          serializeGoogleAuthTransaction(
            createGoogleAuthTransaction({
              now: NOW,
            }),
            {
              secret: "too-short",
            },
          ),
        ).toThrow(
          /32 bytes/i,
        );
      },
    );

    it(
      "accepts local return paths",
      () => {
        expect(
          normalizeAuthReturnTo(
            "/projects/123?tab=roadmap",
          ),
        ).toBe(
          "/projects/123?tab=roadmap",
        );
      },
    );

    it.each([
      "https://evil.example",
      "//evil.example",
      "\\\\evil.example",
      "javascript:alert(1)",
    ])(
      "rejects unsafe return path %s",
      (value) => {
        expect(() =>
          normalizeAuthReturnTo(value),
        ).toThrow(
          GoogleAuthTransactionError,
        );
      },
    );
  },
);
