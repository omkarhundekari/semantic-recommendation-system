// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  EXECUTION_EVIDENCE_REPOSITORY_KEY,
} from "@/lib/executionEvidencePersistence";

import {
  AuthProvider,
} from "@/lib/auth/AuthProvider";


const {
  discoverWorkspacesMock,
  provisionWorkspaceMock,
} = vi.hoisted(
  () => ({
    discoverWorkspacesMock:
      vi.fn(),
    provisionWorkspaceMock:
      vi.fn(),
  }),
);


vi.mock(
  "@/lib/workspaces/workspaceClient",
  async (
    importOriginal,
  ) => {
    const actual =
      await importOriginal<
        typeof import(
          "@/lib/workspaces/workspaceClient"
        )
      >();

    return {
      ...actual,

      discoverWorkspaces:
        discoverWorkspacesMock,

      provisionWorkspace:
        provisionWorkspaceMock,
    };
  },
);

import Home from "./page";

function successfulPayload() {
  const occurredAt = "2026-07-13T12:00:00+00:00";

  return {
    created: true,
    sync: {
      repository_key: "github:owner/repository",
      status: "succeeded",
      evidence: [],
      sync_state: {
        repository_key: "github:owner/repository",
        status: "succeeded",
        latest_commit_sha: "abc123",
        cursor: null,
        last_attempted_at: occurredAt,
        last_succeeded_at: occurredAt,
        error_message: null,
      },
      sync_snapshot: {
        repository_key: "github:owner/repository",
        sources: {},
      },
      synced_counts: {
        commit: 1,
        pull_request: 1,
      },
      failed_types: [],
      errors: {},
    },
    stored: {
      schema_version: 1,
      revision: 0,
      saved_at: occurredAt,
      repository: {
        provider: "github",
        owner: "owner",
        repository: "repository",
        canonical_url:
          "https://github.com/owner/repository",
      },
      attributions: [],
      evidence: [
        {
          provider: "github",
          repository_full_name: "owner/repository",
          evidence_type: "commit",
          external_id: "abc123",
          title: "Add execution evidence panel",
          description: "",
          url:
            "https://github.com/owner/repository/commit/abc123",
          occurred_at: occurredAt,
          metadata: {},
          first_seen_at: occurredAt,
          last_seen_at: occurredAt,
        },
        {
          provider: "github",
          repository_full_name: "owner/repository",
          evidence_type: "pull_request",
          external_id: "42",
          title: "Merge repository evidence UI",
          description: "",
          url:
            "https://github.com/owner/repository/pull/42",
          occurred_at: occurredAt,
          metadata: {},
          first_seen_at: occurredAt,
          last_seen_at: occurredAt,
        },
      ],
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

function renderAuthenticatedHome() {
  discoverWorkspacesMock
    .mockResolvedValue({
      workspaces: [
        {
          workspaceId:
            "ws_execution_evidence_test",
          membershipId:
            "wsm_execution_evidence_test",
          membershipRole:
            "owner",
        },
      ],
      truncated:
        false,
      nextCursor:
        null,
    });

  provisionWorkspaceMock
    .mockRejectedValue(
      new Error(
        "Provisioning must not run in execution-evidence tests.",
      ),
    );

  return render(
    <AuthProvider
      initialState={{
        status:
          "authenticated",
        principal: {
          principalId:
            "prn_execution_evidence_test",
          principalKind:
            "human",
        },
      }}
    >
      <Home />
    </AuthProvider>,
  );
}


describe("execution evidence panel", () => {
  it("restores stored execution evidence on reload", async () => {
    const payload = successfulPayload();

    window.localStorage.setItem(
      EXECUTION_EVIDENCE_REPOSITORY_KEY,
      "github:owner/repository",
    );

    const fetchMock = vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify(payload.stored),
        {
          status: 200,
          headers: {
            "Content-Type":
              "application/json",
          },
        },
      ),
    );

    renderAuthenticatedHome();

    expect(
      screen.getByRole("button", {
        name: "Restoring evidence",
      }),
    ).toBeDisabled();

    expect(
      await screen.findByText(
        "Add execution evidence panel",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText(
        "Public GitHub repository URL",
      ),
    ).toHaveValue(
      "https://github.com/owner/repository",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/v1/execution-evidence/repositories/github%3Aowner/repository",
    );
  });

  it("keeps repository sync available without a planned project", () => {
    renderAuthenticatedHome();

    expect(
      screen.getByLabelText(
        "Public GitHub repository URL",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Sync execution evidence",
      }),
    ).toBeInTheDocument();
  });

  it("synchronizes and displays repository evidence", async () => {
    const fetchMock = vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify(successfulPayload()),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    renderAuthenticatedHome();

    fireEvent.change(
      screen.getByLabelText(
        "Public GitHub repository URL",
      ),
      {
        target: {
          value:
            "https://github.com/owner/repository",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Sync execution evidence",
      }),
    );

    expect(
      await screen.findByText("Sync completed"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Add execution evidence panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Merge repository evidence UI"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("owner/repository · revision 0"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText(
        /Generate and select a project direction before attaching/,
      ),
    ).toHaveLength(2);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [, options] = fetchMock.mock.calls[0];

    expect(JSON.parse(String(options?.body))).toEqual({
      repository_url:
        "https://github.com/owner/repository",
      since: null,
    });
  });

  it("shows repository validation failures", async () => {
    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify({
          detail:
            "Only github.com repositories are supported.",
        }),
        {
          status: 422,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    renderAuthenticatedHome();

    fireEvent.change(
      screen.getByLabelText(
        "Public GitHub repository URL",
      ),
      {
        target: {
          value:
            "https://gitlab.com/owner/repository",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Sync execution evidence",
      }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "Only github.com repositories are supported.",
    );
  });
});
