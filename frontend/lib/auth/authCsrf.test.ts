import {
  describe,
  expect,
  it,
} from "vitest";

import {
  NextRequest,
} from "next/server";

import {
  AuthCsrfRejectedError,
  requireAuthWriteRequest,
} from "./authCsrf";


const URL =
  "http://localhost:3000/api/auth/logout";


function request({
  method = "POST",
  origin = "http://localhost:3000",
  fetchSite = "same-origin",
}: {
  method?: string;
  origin?: string | null;
  fetchSite?: string | null;
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

  return new NextRequest(
    URL,
    {
      method,
      headers,
    },
  );
}


describe(
  "auth write CSRF authority",
  () => {
    it(
      "allows same-origin POST",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request(),
            ),
        ).not.toThrow();
      },
    );


    it(
      "allows a matching origin when Fetch Metadata is absent",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                fetchSite: null,
              }),
            ),
        ).not.toThrow();
      },
    );


    it(
      "allows Sec-Fetch-Site none only with matching Origin",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                fetchSite: "none",
              }),
            ),
        ).not.toThrow();
      },
    );


    it(
      "rejects GET",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                method: "GET",
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it(
      "rejects missing Origin",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                origin: null,
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it(
      "rejects cross-origin request",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                origin:
                  "https://attacker.example",
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it.each([
      "cross-site",
      "same-site",
    ])(
      "rejects Sec-Fetch-Site %s",
      (
        fetchSite,
      ) => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                fetchSite,
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it(
      "rejects malformed Origin",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                origin:
                  "not-an-origin",
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it(
      "rejects origin with credentials",
      () => {
        expect(
          () =>
            requireAuthWriteRequest(
              request({
                origin:
                  "http://user:pass@localhost:3000",
              }),
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );


    it(
      "does not trust Host independently of request origin",
      () => {
        const req =
          new NextRequest(
            URL,
            {
              method: "POST",
              headers: {
                Origin:
                  "http://localhost:4000",
                "Sec-Fetch-Site":
                  "same-origin",
              },
            },
          );

        expect(
          () =>
            requireAuthWriteRequest(
              req,
            ),
        ).toThrow(
          AuthCsrfRejectedError,
        );
      },
    );
  },
);
