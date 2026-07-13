import {
  describe,
  expect,
  it,
} from "vitest";

import {
  EXECUTION_EVIDENCE_REPOSITORY_KEY,
  readExecutionEvidenceRepositoryKey,
  removeExecutionEvidenceRepositoryKey,
  writeExecutionEvidenceRepositoryKey,
  type ExecutionEvidenceStorage,
} from "./executionEvidencePersistence";

describe("execution evidence persistence", () => {
  it("reads a normalized repository key", () => {
    const storage: ExecutionEvidenceStorage = {
      getItem: () =>
        "  github:owner/repository  ",
      setItem: () => undefined,
      removeItem: () => undefined,
    };

    expect(
      readExecutionEvidenceRepositoryKey(storage),
    ).toBe("github:owner/repository");
  });

  it("writes the normalized repository key", () => {
    let storedKey = "";
    let storedValue = "";

    const storage: ExecutionEvidenceStorage = {
      getItem: () => null,
      setItem: (key, value) => {
        storedKey = key;
        storedValue = value;
      },
      removeItem: () => undefined,
    };

    expect(
      writeExecutionEvidenceRepositoryKey(
        storage,
        "  github:owner/repository  ",
      ),
    ).toBe(true);

    expect(storedKey).toBe(
      EXECUTION_EVIDENCE_REPOSITORY_KEY,
    );
    expect(storedValue).toBe(
      "github:owner/repository",
    );
  });

  it("rejects an empty repository key", () => {
    const storage: ExecutionEvidenceStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error(
          "The storage write should not run.",
        );
      },
      removeItem: () => undefined,
    };

    expect(
      writeExecutionEvidenceRepositoryKey(
        storage,
        " ",
      ),
    ).toBe(false);
  });

  it("fails safely when browser storage is blocked", () => {
    const storage: ExecutionEvidenceStorage = {
      getItem: () => {
        throw new Error("Storage blocked.");
      },
      setItem: () => {
        throw new Error("Storage blocked.");
      },
      removeItem: () => {
        throw new Error("Storage blocked.");
      },
    };

    expect(
      readExecutionEvidenceRepositoryKey(storage),
    ).toBeNull();
    expect(
      writeExecutionEvidenceRepositoryKey(
        storage,
        "github:owner/repository",
      ),
    ).toBe(false);
    expect(
      removeExecutionEvidenceRepositoryKey(
        storage,
      ),
    ).toBe(false);
  });
});
