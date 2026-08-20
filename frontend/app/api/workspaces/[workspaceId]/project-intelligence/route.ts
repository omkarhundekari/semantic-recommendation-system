import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  BrowserProjectIntelligenceAuthenticationError,
  BrowserProjectIntelligenceAuthorizationError,
  BrowserProjectIntelligenceNotFoundError,
  BrowserProjectIntelligenceUnavailableError,
  BrowserProjectIntelligenceValidationError,
  requestBrowserProjectIntelligence,
} from "@/lib/workspaces/browserProjectIntelligence";


export const runtime = "nodejs";


function applyHeaders(
  response: NextResponse,
): NextResponse {
  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  response.headers.set(
    "Pragma",
    "no-cache",
  );

  response.headers.set(
    "Vary",
    "Cookie",
  );

  return response;
}


function errorResponse(
  error: string,
  status: number,
): NextResponse {
  return applyHeaders(
    NextResponse.json(
      {
        error,
      },
      {
        status,
      },
    ),
  );
}


export async function POST(
  request: NextRequest,
  context: {
    params:
      Promise<{
        workspaceId: string;
      }>;
  },
) {
  const {
    workspaceId,
  } =
    await context.params;

  let body: unknown;

  try {
    body =
      await request.json();
  } catch {
    return errorResponse(
      "Request body is invalid.",
      400,
    );
  }

  try {
    const payload =
      await requestBrowserProjectIntelligence({
        workspaceId,
        body,
      });

    return applyHeaders(
      NextResponse.json(
        payload,
        {
          status: 200,
        },
      ),
    );
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserProjectIntelligenceAuthenticationError
    ) {
      return errorResponse(
        "Authentication is required.",
        401,
      );
    }

    if (
      error
      instanceof BrowserProjectIntelligenceAuthorizationError
    ) {
      return errorResponse(
        "Project creation is not permitted in this workspace.",
        403,
      );
    }

    if (
      error
      instanceof BrowserProjectIntelligenceNotFoundError
    ) {
      return errorResponse(
        "Workspace was not found.",
        404,
      );
    }

    if (
      error
      instanceof BrowserProjectIntelligenceValidationError
    ) {
      return errorResponse(
        "Project intelligence request is invalid.",
        422,
      );
    }

    if (
      error
      instanceof BrowserProjectIntelligenceUnavailableError
    ) {
      return errorResponse(
        "Project intelligence service is temporarily unavailable.",
        503,
      );
    }

    throw error;
  }
}
