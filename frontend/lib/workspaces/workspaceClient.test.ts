import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  WorkspaceClientAuthenticationError,
  WorkspaceClientUnavailableError,
  WorkspaceClientValidationError,
  discoverWorkspaces,
  provisionWorkspace,
} from "./workspaceClient";


describe(
  "workspaceClient",
  () => {
    it(
      "discovers browser workspaces without sending principal scope",
      async () => {
        const fetcher =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
            ) => {
              const value =
                input.toString();

              expect(
                value,
              ).toContain(
                "/api/workspaces",
              );

              expect(
                value,
              ).toContain(
                "cursor=opaque%2Bcursor%3D%3D",
              );

              expect(
                value,
              ).not.toContain(
                "principal",
              );

              return new Response(
                JSON.stringify({
                  workspaces: [
                    {
                      workspace_id:
                        "ws_123",
                      membership_id:
                        "wsm_123",
                      membership_role:
                        "owner",
                    },
                  ],
                  truncated:
                    true,
                  next_cursor:
                    "opaque-next",
                }),
                {
                  status:
                    200,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              );
            },
          );

        const result =
          await discoverWorkspaces({
            cursor:
              "opaque+cursor==",
            pageSize:
              25,
            fetcher:
              fetcher as typeof fetch,
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
            "opaque-next",
        });
      },
    );


    it(
      "maps definitive authentication failure to 401 state",
      async () => {
        const fetcher =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  error:
                    "Authentication is required.",
                }),
                {
                  status:
                    401,
                },
              ),
          );

        await expect(
          discoverWorkspaces({
            fetcher:
              fetcher as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          WorkspaceClientAuthenticationError,
        );
      },
    );


    it(
      "maps indeterminate failure to unavailable rather than authentication",
      async () => {
        const fetcher =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  error:
                    "Workspace service is temporarily unavailable.",
                }),
                {
                  status:
                    503,
                },
              ),
          );

        await expect(
          discoverWorkspaces({
            fetcher:
              fetcher as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          WorkspaceClientUnavailableError,
        );
      },
    );


    it(
      "rejects inconsistent discovery pagination metadata",
      async () => {
        const fetcher =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  workspaces: [],
                  truncated:
                    true,
                  next_cursor:
                    null,
                }),
                {
                  status:
                    200,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
          );

        await expect(
          discoverWorkspaces({
            fetcher:
              fetcher as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          WorkspaceClientUnavailableError,
        );
      },
    );


    it(
      "provisions through the same-origin workspace BFF",
      async () => {
        const fetcher =
          vi.fn(
            async (
              input:
                RequestInfo | URL,
              init?: RequestInit,
            ) => {
              expect(
                input.toString(),
              ).toBe(
                "/api/workspaces",
              );

              expect(
                init?.headers,
              ).toEqual({
                "Content-Type":
                  "application/json",
                "Idempotency-Key":
                  "workspace-bootstrap-1",
              });

              expect(
                JSON.parse(
                  String(
                    init?.body,
                  ),
                ),
              ).toEqual({
                reason:
                  "browser bootstrap",
              });

              return new Response(
                JSON.stringify({
                  workspace_id:
                    "ws_123",
                  membership_id:
                    "wsm_123",
                  membership_role:
                    "owner",
                  replayed:
                    false,
                }),
                {
                  status:
                    201,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              );
            },
          );

        const result =
          await provisionWorkspace({
            idempotencyKey:
              "workspace-bootstrap-1",
            reason:
              "browser bootstrap",
            fetcher:
              fetcher as typeof fetch,
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
      "rejects malformed provisioning success semantics",
      async () => {
        const fetcher =
          vi.fn(
            async () =>
              new Response(
                JSON.stringify({
                  workspace_id:
                    "ws_123",
                  membership_id:
                    "wsm_123",
                  membership_role:
                    "owner",
                  replayed:
                    true,
                }),
                {
                  status:
                    201,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
          );

        await expect(
          provisionWorkspace({
            idempotencyKey:
              "workspace-bootstrap-1",
            fetcher:
              fetcher as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          WorkspaceClientUnavailableError,
        );
      },
    );


    it(
      "rejects invalid client idempotency keys before fetch",
      async () => {
        const fetcher =
          vi.fn();

        await expect(
          provisionWorkspace({
            idempotencyKey:
              " bad-key ",
            fetcher:
              fetcher as typeof fetch,
          }),
        ).rejects.toBeInstanceOf(
          WorkspaceClientValidationError,
        );

        expect(
          fetcher,
        ).not.toHaveBeenCalled();
      },
    );
  },
);


describe(
  "default workspace bootstrap identity",
  () => {
    it(
      "uses a stable namespaced idempotency key",
      async () => {
        const {
          DEFAULT_WORKSPACE_BOOTSTRAP_IDEMPOTENCY_KEY,
        } =
          await import(
            "./workspaceClient"
          );

        expect(
          DEFAULT_WORKSPACE_BOOTSTRAP_IDEMPOTENCY_KEY,
        ).toBe(
          "browser-default-workspace-v1",
        );
      },
    );
  },
);
