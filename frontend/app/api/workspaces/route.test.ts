// @vitest-environment node

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  NextRequest,
} from "next/server";


const {
  listMock,
  provisionMock,
} = vi.hoisted(
  () => ({
    listMock:
      vi.fn(),
    provisionMock:
      vi.fn(),
  }),
);


vi.mock(
  "@/lib/workspaces/browserWorkspaces",
  async () => {
    const actual =
      await vi.importActual<
        typeof import(
          "@/lib/workspaces/browserWorkspaces"
        )
      >(
        "@/lib/workspaces/browserWorkspaces",
      );

    return {
      ...actual,

      listBrowserWorkspaces:
        listMock,

      provisionBrowserWorkspace:
        provisionMock,
    };
  },
);


import {
  BrowserWorkspaceAuthenticationError,
  BrowserWorkspaceUnavailableError,
  BrowserWorkspaceValidationError,
} from "@/lib/workspaces/browserWorkspaces";

import {
  GET,
  POST,
} from "./route";


describe(
  "/api/workspaces",
  () => {
    beforeEach(
      () => {
        vi.clearAllMocks();
      },
    );


    it(
      "forwards opaque discovery parameters and returns pagination metadata",
      async () => {
        listMock
          .mockResolvedValue({
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

        const request =
          new NextRequest(
            "http://localhost/api/workspaces"
            + "?cursor=opaque%2Bcursor"
            + "&page_size=25",
          );

        const response =
          await GET(
            request,
          );

        expect(
          response.status,
        ).toBe(200);

        expect(
          listMock,
        ).toHaveBeenCalledWith({
          cursor:
            "opaque+cursor",
          pageSize:
            "25",
        });

        expect(
          await response.json(),
        ).toEqual({
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
        });

        expect(
          response.headers.get(
            "Cache-Control",
          ),
        ).toBe(
          "no-store",
        );

        expect(
          response.headers.get(
            "Vary",
          ),
        ).toBe(
          "Cookie",
        );
      },
    );


    it(
      "maps workspace validation failure to 422",
      async () => {
        listMock
          .mockRejectedValue(
            new BrowserWorkspaceValidationError(
              "invalid",
            ),
          );

        const response =
          await GET(
            new NextRequest(
              "http://localhost/api/workspaces?page_size=bad",
            ),
          );

        expect(
          response.status,
        ).toBe(422);

        expect(
          await response.json(),
        ).toEqual({
          error:
            "Workspace request is invalid.",
        });
      },
    );


    it(
      "maps indeterminate workspace failure to 503 rather than signed-out",
      async () => {
        listMock
          .mockRejectedValue(
            new BrowserWorkspaceUnavailableError(
              "unavailable",
            ),
          );

        const response =
          await GET(
            new NextRequest(
              "http://localhost/api/workspaces",
            ),
          );

        expect(
          response.status,
        ).toBe(503);

        expect(
          await response.json(),
        ).toEqual({
          error:
            "Workspace service is temporarily unavailable.",
        });
      },
    );


    it(
      "maps definitive authentication failure to 401",
      async () => {
        listMock
          .mockRejectedValue(
            new BrowserWorkspaceAuthenticationError(
              "authentication failed",
            ),
          );

        const response =
          await GET(
            new NextRequest(
              "http://localhost/api/workspaces",
            ),
          );

        expect(
          response.status,
        ).toBe(401);
      },
    );


    it(
      "returns 201 for first workspace creation",
      async () => {
        provisionMock
          .mockResolvedValue({
            workspaceId:
              "ws_123",
            membershipId:
              "wsm_123",
            membershipRole:
              "owner",
            replayed:
              false,
          });

        const request =
          new NextRequest(
            "http://localhost/api/workspaces",
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
                "Idempotency-Key":
                  "workspace-create-1",
              },
              body:
                JSON.stringify({
                  reason:
                    "self service",
                }),
            },
          );

        const response =
          await POST(
            request,
          );

        expect(
          response.status,
        ).toBe(201);

        expect(
          provisionMock,
        ).toHaveBeenCalledWith({
          idempotencyKey:
            "workspace-create-1",
          reason:
            "self service",
        });

        expect(
          await response.json(),
        ).toEqual({
          workspace_id:
            "ws_123",
          membership_id:
            "wsm_123",
          membership_role:
            "owner",
          replayed:
            false,
        });
      },
    );


    it(
      "returns 200 for idempotent workspace replay",
      async () => {
        provisionMock
          .mockResolvedValue({
            workspaceId:
              "ws_123",
            membershipId:
              "wsm_123",
            membershipRole:
              "owner",
            replayed:
              true,
          });

        const request =
          new NextRequest(
            "http://localhost/api/workspaces",
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
                "Idempotency-Key":
                  "workspace-replay-1",
              },
              body:
                JSON.stringify({}),
            },
          );

        const response =
          await POST(
            request,
          );

        expect(
          response.status,
        ).toBe(200);

        expect(
          (
            await response.json()
          ).replayed,
        ).toBe(true);
      },
    );
  },
);
