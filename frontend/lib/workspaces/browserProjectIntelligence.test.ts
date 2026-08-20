import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";


const SESSION_TOKEN =
  "session-token-that-is-definitely-long-enough-for-validation";

const INTERNAL_SECRET =
  "internal-login-secret";

const cookiesGet =
  vi.fn();

const {
  loadInternalLoginServerConfig,
} =
  vi.hoisted(() => ({
    loadInternalLoginServerConfig:
      vi.fn(),
  }));


vi.mock(
  "next/headers",
  () => ({
    cookies:
      vi.fn(async () => ({
        get:
          cookiesGet,
      })),
  }),
);


vi.mock(
  "@/lib/auth/internalLoginCompletion",
  async () => {
    const actual =
      await vi.importActual<
        typeof import(
          "@/lib/auth/internalLoginCompletion"
        )
      >(
        "@/lib/auth/internalLoginCompletion",
      );

    return {
      ...actual,
      loadInternalLoginServerConfig,
    };
  },
);


import {
  INTERNAL_LOGIN_SECRET_HEADER,
} from "@/lib/auth/internalLoginCompletion";

import {
  BROWSER_SESSION_HEADER,
} from "@/lib/auth/browserProfile";

import {
  BrowserProjectIntelligenceAuthenticationError,
  BrowserProjectIntelligenceAuthorizationError,
  BrowserProjectIntelligenceNotFoundError,
  BrowserProjectIntelligenceUnavailableError,
  BrowserProjectIntelligenceValidationError,
  requestBrowserProjectIntelligence,
} from "./browserProjectIntelligence";


function installSession() {
  cookiesGet.mockReturnValue({
    value:
      SESSION_TOKEN,
  });

  loadInternalLoginServerConfig.mockReturnValue({
    apiBaseUrl:
      "http://127.0.0.1:8000",
    internalSecret:
      INTERNAL_SECRET,
  });
}


describe(
  "requestBrowserProjectIntelligence",
  () => {
    beforeEach(() => {
      vi.clearAllMocks();
      installSession();
    });


    it(
      "posts through the authenticated workspace-scoped backend path",
      async () => {
        const payload = {
          response_schema_version: 3,
          status: "ready",
          directions: [
            {
              id: "direction-one",
              project_id:
                "proj_server_authoritative",
              roadmap_snapshot_id:
                "snap_server_authoritative",
              project_direction_id:
                "direction-server-authoritative",
            },
          ],
        };

        const fetchImpl =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
              init?:
                RequestInit,
            ) => {
              expect(
                input.toString(),
              ).toBe(
                "http://127.0.0.1:8000/v1/workspaces/wsp_test/project-intelligence",
              );

              expect(
                init?.method,
              ).toBe(
                "POST",
              );

              expect(
                init?.cache,
              ).toBe(
                "no-store",
              );

              const headers =
                new Headers(
                  init?.headers,
                );

              expect(
                headers.get(
                  BROWSER_SESSION_HEADER,
                ),
              ).toBe(
                SESSION_TOKEN,
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
                goal:
                  "Build a RAG evaluation system",
              });

              return new Response(
                JSON.stringify(
                  payload,
                ),
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
          await requestBrowserProjectIntelligence({
            workspaceId:
              "wsp_test",
            body: {
              goal:
                "Build a RAG evaluation system",
            },
            fetchImpl,
          });

        expect(
          result,
        ).toEqual(
          payload,
        );

        expect(
          fetchImpl,
        ).toHaveBeenCalledTimes(
          1,
        );
      },
    );


    it(
      "URL-encodes workspace identity rather than interpolating an unsafe path",
      async () => {
        const fetchImpl =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              expect(
                input.toString(),
              ).toBe(
                "http://127.0.0.1:8000/v1/workspaces/workspace%2Fone/project-intelligence",
              );

              return new Response(
                JSON.stringify({
                  status:
                    "ready",
                  directions: [],
                }),
                {
                  status: 200,
                },
              );
            },
          ) as typeof fetch;

        await requestBrowserProjectIntelligence({
          workspaceId:
            "workspace/one",
          body: {
            goal:
              "Build something",
          },
          fetchImpl,
        });
      },
    );


    it(
      "rejects malformed workspace identity before any backend request",
      async () => {
        const fetchImpl =
          vi.fn() as unknown as typeof fetch;

        await expect(
          requestBrowserProjectIntelligence({
            workspaceId:
              "  wsp_test  ",
            body: {},
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProjectIntelligenceValidationError,
        );

        expect(
          fetchImpl,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "requires a browser session before calling the backend",
      async () => {
        cookiesGet.mockReturnValue(
          undefined,
        );

        const fetchImpl =
          vi.fn() as unknown as typeof fetch;

        await expect(
          requestBrowserProjectIntelligence({
            workspaceId:
              "wsp_test",
            body: {},
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProjectIntelligenceAuthenticationError,
        );

        expect(
          fetchImpl,
        ).not.toHaveBeenCalled();
      },
    );


    it.each([
      [
        401,
        BrowserProjectIntelligenceAuthenticationError,
      ],
      [
        403,
        BrowserProjectIntelligenceAuthorizationError,
      ],
      [
        404,
        BrowserProjectIntelligenceNotFoundError,
      ],
      [
        422,
        BrowserProjectIntelligenceValidationError,
      ],
      [
        500,
        BrowserProjectIntelligenceUnavailableError,
      ],
      [
        503,
        BrowserProjectIntelligenceUnavailableError,
      ],
    ])(
      "preserves upstream status semantics for %s",
      async (
        status,
        expectedError,
      ) => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  detail:
                    "upstream failure",
                }),
                {
                  status,
                },
              ),
          ) as typeof fetch;

        await expect(
          requestBrowserProjectIntelligence({
            workspaceId:
              "wsp_test",
            body: {},
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          expectedError,
        );
      },
    );


    it(
      "treats transport failure as unavailable rather than signed-out",
      async () => {
        const fetchImpl =
          vi.fn(
            async () => {
              throw new Error(
                "connection refused",
              );
            },
          ) as typeof fetch;

        await expect(
          requestBrowserProjectIntelligence({
            workspaceId:
              "wsp_test",
            body: {},
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProjectIntelligenceUnavailableError,
        );
      },
    );


    it(
      "rejects malformed successful JSON rather than manufacturing intelligence",
      async () => {
        const fetchImpl =
          vi.fn(
            async () =>
              new Response(
                "{ definitely-not-json",
                {
                  status: 200,
                },
              ),
          ) as typeof fetch;

        await expect(
          requestBrowserProjectIntelligence({
            workspaceId:
              "wsp_test",
            body: {},
            fetchImpl,
          }),
        ).rejects.toBeInstanceOf(
          BrowserProjectIntelligenceUnavailableError,
        );
      },
    );
  },
);
