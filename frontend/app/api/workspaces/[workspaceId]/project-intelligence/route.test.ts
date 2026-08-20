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
  requestBrowserProjectIntelligence,
} =
  vi.hoisted(() => ({
    requestBrowserProjectIntelligence:
      vi.fn(),
  }));


vi.mock(
  "@/lib/workspaces/browserProjectIntelligence",
  async () => {
    const actual =
      await vi.importActual<
        typeof import(
          "@/lib/workspaces/browserProjectIntelligence"
        )
      >(
        "@/lib/workspaces/browserProjectIntelligence",
      );

    return {
      ...actual,
      requestBrowserProjectIntelligence,
    };
  },
);


import {
  BrowserProjectIntelligenceAuthenticationError,
  BrowserProjectIntelligenceAuthorizationError,
  BrowserProjectIntelligenceNotFoundError,
  BrowserProjectIntelligenceUnavailableError,
  BrowserProjectIntelligenceValidationError,
} from "@/lib/workspaces/browserProjectIntelligence";

import {
  POST,
} from "./route";


function request(
  body:
    string = JSON.stringify({
      goal:
        "Build a RAG evaluation project",
    }),
): NextRequest {
  return new NextRequest(
    "http://localhost/api/workspaces/wsp_test/project-intelligence",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body,
    },
  );
}


function context(
  workspaceId:
    string = "wsp_test",
) {
  return {
    params:
      Promise.resolve({
        workspaceId,
      }),
  };
}


function expectPrivateHeaders(
  response:
    Response,
) {
  expect(
    response.headers.get(
      "Cache-Control",
    ),
  ).toBe(
    "no-store",
  );

  expect(
    response.headers.get(
      "Pragma",
    ),
  ).toBe(
    "no-cache",
  );

  expect(
    response.headers.get(
      "Vary",
    ),
  ).toBe(
    "Cookie",
  );
}


describe(
  "POST /api/workspaces/[workspaceId]/project-intelligence",
  () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });


    it(
      "passes workspace identity and request body to the server-only helper",
      async () => {
        const upstream = {
          response_schema_version:
            3,
          status:
            "ready",
          directions: [
            {
              id:
                "direction-one",
              project_id:
                "proj_authoritative",
              roadmap_snapshot_id:
                "snap_authoritative",
              project_direction_id:
                "direction-authoritative",
            },
          ],
        };

        requestBrowserProjectIntelligence
          .mockResolvedValue(
            upstream,
          );

        const response =
          await POST(
            request(),
            context(),
          );

        expect(
          response.status,
        ).toBe(
          200,
        );

        expect(
          await response.json(),
        ).toEqual(
          upstream,
        );

        expect(
          requestBrowserProjectIntelligence,
        ).toHaveBeenCalledTimes(
          1,
        );

        expect(
          requestBrowserProjectIntelligence,
        ).toHaveBeenCalledWith({
          workspaceId:
            "wsp_test",
          body: {
            goal:
              "Build a RAG evaluation project",
          },
        });

        expectPrivateHeaders(
          response,
        );
      },
    );


    it(
      "returns 400 for malformed browser JSON without calling upstream",
      async () => {
        const response =
          await POST(
            request(
              "{bad-json",
            ),
            context(),
          );

        expect(
          response.status,
        ).toBe(
          400,
        );

        expect(
          requestBrowserProjectIntelligence,
        ).not.toHaveBeenCalled();

        expectPrivateHeaders(
          response,
        );
      },
    );


    it.each([
      [
        new BrowserProjectIntelligenceAuthenticationError(
          "auth",
        ),
        401,
        "Authentication is required.",
      ],
      [
        new BrowserProjectIntelligenceAuthorizationError(
          "authorization",
        ),
        403,
        "Project creation is not permitted in this workspace.",
      ],
      [
        new BrowserProjectIntelligenceNotFoundError(
          "not-found",
        ),
        404,
        "Workspace was not found.",
      ],
      [
        new BrowserProjectIntelligenceValidationError(
          "validation",
        ),
        422,
        "Project intelligence request is invalid.",
      ],
      [
        new BrowserProjectIntelligenceUnavailableError(
          "unavailable",
        ),
        503,
        "Project intelligence service is temporarily unavailable.",
      ],
    ])(
      "maps helper error to BFF status %s",
      async (
        error,
        expectedStatus,
        expectedMessage,
      ) => {
        requestBrowserProjectIntelligence
          .mockRejectedValue(
            error,
          );

        const response =
          await POST(
            request(),
            context(),
          );

        expect(
          response.status,
        ).toBe(
          expectedStatus,
        );

        expect(
          await response.json(),
        ).toEqual({
          error:
            expectedMessage,
        });

        expectPrivateHeaders(
          response,
        );
      },
    );


    it(
      "keeps 403 distinct from authentication and availability failures",
      async () => {
        requestBrowserProjectIntelligence
          .mockRejectedValue(
            new BrowserProjectIntelligenceAuthorizationError(
              "member cannot create project",
            ),
          );

        const response =
          await POST(
            request(),
            context(),
          );

        expect(
          response.status,
        ).toBe(
          403,
        );

        expect(
          response.status,
        ).not.toBe(
          401,
        );

        expect(
          response.status,
        ).not.toBe(
          503,
        );

        expectPrivateHeaders(
          response,
        );
      },
    );
  },
);
