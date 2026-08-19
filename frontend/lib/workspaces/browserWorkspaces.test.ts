// @vitest-environment node

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";


const {
  cookieGetMock,
  loadConfigMock,
} = vi.hoisted(
  () => ({
    cookieGetMock:
      vi.fn(),
    loadConfigMock:
      vi.fn(),
  }),
);


vi.mock(
  "next/headers",
  () => ({
    cookies:
      async () => ({
        get:
          cookieGetMock,
      }),
  }),
);


vi.mock(
  "@/lib/auth/internalLoginCompletion",
  () => ({
    INTERNAL_LOGIN_SECRET_HEADER:
      "X-Solvyn-Internal-Login-Secret",

    InternalLoginConfigurationError:
      class InternalLoginConfigurationError
        extends Error {},

    loadInternalLoginServerConfig:
      loadConfigMock,
  }),
);


import {
  BrowserWorkspaceUnavailableError,
  BrowserWorkspaceValidationError,
  listBrowserWorkspaces,
  provisionBrowserWorkspace,
} from "./browserWorkspaces";


const SESSION_TOKEN =
  "session-token-"
  + "0123456789abcdef"
  + "0123456789abcdef";

const API_BASE_URL =
  "http://backend.test:8000";

const INTERNAL_SECRET =
  "test-only-internal-login-secret-"
  + "0123456789abcdef0123456789abcdef";


function workspacePayload() {
  return [
    {
      workspace_id:
        "ws_123",
      workspace_kind:
        "provisioned",
      membership_id:
        "wsm_123",
      membership_role:
        "owner",
      membership_revision:
        1,
      workspace_created_at:
        "2026-08-18T12:00:00+00:00",
      workspace_updated_at:
        "2026-08-18T12:00:00+00:00",
      membership_created_at:
        "2026-08-18T12:00:00+00:00",
      membership_updated_at:
        "2026-08-18T12:00:00+00:00",
    },
  ];
}


function provisioningPayload() {
  return {
    workspace: {
      workspace_id:
        "ws_123",
      workspace_kind:
        "provisioned",
      created_at:
        "2026-08-18T12:00:00+00:00",
      updated_at:
        "2026-08-18T12:00:00+00:00",
    },
    membership: {
      membership_id:
        "wsm_123",
      workspace_id:
        "ws_123",
      principal_id:
        "prn_backend_only",
      status:
        "active",
      role:
        "owner",
      revision:
        1,
      created_by_principal_id:
        null,
      created_at:
        "2026-08-18T12:00:00+00:00",
      updated_at:
        "2026-08-18T12:00:00+00:00",
      status_changed_at:
        "2026-08-18T12:00:00+00:00",
    },
    owner_transition: {
      transition_id:
        "wmrt_123",
    },
  };
}


describe(
  "browser workspace server boundary",
  () => {
    beforeEach(
      () => {
        vi.clearAllMocks();

        cookieGetMock
          .mockReturnValue({
            value:
              SESSION_TOKEN,
          });

        loadConfigMock
          .mockReturnValue({
            apiBaseUrl:
              API_BASE_URL,
            internalSecret:
              INTERNAL_SECRET,
          });
      },
    );


    it(
      "forwards discovery cursor opaquely and preserves pagination metadata",
      async () => {
        const fetchMock =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              const url =
                new URL(
                  input.toString(),
                );

              expect(
                url.pathname,
              ).toBe(
                "/v1/workspaces",
              );

              expect(
                url.searchParams.get(
                  "cursor",
                ),
              ).toBe(
                "opaque+/cursor==",
              );

              expect(
                url.searchParams.get(
                  "page_size",
                ),
              ).toBe("25");

              return new Response(
                JSON.stringify(
                  workspacePayload(),
                ),
                {
                  status: 200,
                  headers: {
                    "Content-Type":
                      "application/json",
                    "Workspace-Discovery-Truncated":
                      "true",
                    "Workspace-Discovery-Next-Cursor":
                      "next+/cursor==",
                  },
                },
              );
            },
          );

        const result =
          await listBrowserWorkspaces({
            cursor:
              "opaque+/cursor==",
            pageSize:
              "25",
            fetchImpl:
              fetchMock as typeof fetch,
          });

        expect(
          result,
        ).toEqual({
          workspaces: [
            {
              workspaceId:
                "ws_123",
              membershipId:
                "wsm_123",
              membershipRole:
                "owner",
            },
          ],
          truncated:
            true,
          nextCursor:
            "next+/cursor==",
        });
      },
    );


    it(
      "rejects inconsistent discovery pagination metadata",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify(
                  workspacePayload(),
                ),
                {
                  status: 200,
                  headers: {
                    "Content-Type":
                      "application/json",
                    "Workspace-Discovery-Truncated":
                      "true",
                  },
                },
              ),
          );

        await expect(
          listBrowserWorkspaces({
            fetchImpl:
              fetchMock as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserWorkspaceUnavailableError,
        );
      },
    );


    it(
      "preserves backend 422 as request validation rather than outage",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  detail:
                    "invalid",
                }),
                {
                  status:
                    422,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
          );

        await expect(
          listBrowserWorkspaces({
            pageSize:
              "invalid",
            fetchImpl:
              fetchMock as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserWorkspaceValidationError,
        );
      },
    );


    it(
      "treats backend 403 as unavailable rather than signed-out or validation",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  detail:
                    "forbidden",
                }),
                {
                  status:
                    403,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
          );

        await expect(
          listBrowserWorkspaces({
            fetchImpl:
              fetchMock as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserWorkspaceUnavailableError,
        );
      },
    );


    it(
      "accepts first provisioning only as 201 plus replayed false",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify(
                  provisioningPayload(),
                ),
                {
                  status:
                    201,
                  headers: {
                    "Content-Type":
                      "application/json",
                    "Idempotency-Replayed":
                      "false",
                  },
                },
              ),
          );

        const result =
          await provisionBrowserWorkspace({
            idempotencyKey:
              "workspace-create-1",
            reason:
              "self service",
            fetchImpl:
              fetchMock as typeof fetch,
          });

        expect(
          result,
        ).toEqual({
          workspaceId:
            "ws_123",
          membershipId:
            "wsm_123",
          membershipRole:
            "owner",
          replayed:
            false,
        });
      },
    );


    it(
      "rejects inconsistent provisioning replay metadata",
      async () => {
        const fetchMock =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify(
                  provisioningPayload(),
                ),
                {
                  status:
                    201,
                  headers: {
                    "Content-Type":
                      "application/json",
                    "Idempotency-Replayed":
                      "true",
                  },
                },
              ),
          );

        await expect(
          provisionBrowserWorkspace({
            idempotencyKey:
              "workspace-create-1",
            fetchImpl:
              fetchMock as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          BrowserWorkspaceUnavailableError,
        );
      },
    );
  },
);
