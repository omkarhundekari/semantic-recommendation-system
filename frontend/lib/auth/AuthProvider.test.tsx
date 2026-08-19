// @vitest-environment jsdom
import {
  act,
  renderHook,
} from "@testing-library/react";

import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  AuthProvider,
  useAuth,
  type AuthState,
} from "./AuthProvider";


function wrapperFor(
  initialState: AuthState,
) {
  return function Wrapper({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <AuthProvider
        initialState={
          initialState
        }
      >
        {children}
      </AuthProvider>
    );
  };
}


function deferredResponse() {
  let resolve:
    (response: Response) => void =
      () => {};

  const promise =
    new Promise<Response>(
      (resolver) => {
        resolve = resolver;
      },
    );

  return {
    promise,
    resolve,
  };
}


afterEach(
  () => {
    vi.restoreAllMocks();
  },
);


describe(
  "AuthProvider",
  () => {
    it(
      "preserves server-seeded authenticated state without fetching on mount",
      () => {
        const fetchMock =
          vi.spyOn(
            globalThis,
            "fetch",
          );

        const {
          result,
        } =
          renderHook(
            () => useAuth(),
            {
              wrapper:
                wrapperFor({
                  status:
                    "authenticated",
                  principal: {
                    principalId:
                      "prn_test",
                    principalKind:
                      "human",
                  },
                }),
            },
          );

        expect(
          result.current.state,
        ).toEqual({
          status:
            "authenticated",
          principal: {
            principalId:
              "prn_test",
            principalKind:
              "human",
          },
        });

        expect(
          result.current
            .isRetrying,
        ).toBe(false);

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "maps definitive unauthenticated retry result without collapsing unavailable",
      async () => {
        vi.spyOn(
          globalThis,
          "fetch",
        ).mockResolvedValue(
          new Response(
            JSON.stringify({
              authenticated:
                false,
            }),
            {
              status: 200,
              headers: {
                "Content-Type":
                  "application/json",
              },
            },
          ),
        );

        const {
          result,
        } =
          renderHook(
            () => useAuth(),
            {
              wrapper:
                wrapperFor({
                  status:
                    "unavailable",
                }),
            },
          );

        await act(
          async () => {
            await result.current
              .retry();
          },
        );

        expect(
          result.current.state,
        ).toEqual({
          status:
            "unauthenticated",
        });
      },
    );


    it(
      "maps a 503 retry to unavailable rather than unauthenticated",
      async () => {
        vi.spyOn(
          globalThis,
          "fetch",
        ).mockResolvedValue(
          new Response(
            JSON.stringify({
              error:
                "temporarily unavailable",
            }),
            {
              status: 503,
            },
          ),
        );

        const {
          result,
        } =
          renderHook(
            () => useAuth(),
            {
              wrapper:
                wrapperFor({
                  status:
                    "authenticated",
                  principal: {
                    principalId:
                      "prn_test",
                    principalKind:
                      "human",
                  },
                }),
            },
          );

        await act(
          async () => {
            await result.current
              .retry();
          },
        );

        expect(
          result.current.state,
        ).toEqual({
          status:
            "unavailable",
        });

        expect(
          result.current.state
            .status,
        ).not.toBe(
          "unauthenticated",
        );
      },
    );


    it(
      "never regresses authenticated state to loading while retry is pending",
      async () => {
        const pending =
          deferredResponse();

        vi.spyOn(
          globalThis,
          "fetch",
        ).mockReturnValue(
          pending.promise,
        );

        const {
          result,
        } =
          renderHook(
            () => useAuth(),
            {
              wrapper:
                wrapperFor({
                  status:
                    "authenticated",
                  principal: {
                    principalId:
                      "prn_test",
                    principalKind:
                      "human",
                  },
                }),
            },
          );

        let retryPromise:
          Promise<void>;

        act(
          () => {
            retryPromise =
              result.current.retry();
          },
        );

        expect(
          result.current.state
            .status,
        ).toBe(
          "authenticated",
        );

        expect(
          result.current
            .isRetrying,
        ).toBe(true);

        await act(
          async () => {
            pending.resolve(
              new Response(
                JSON.stringify({
                  authenticated:
                    true,
                  principal: {
                    principal_id:
                      "prn_test",
                    principal_kind:
                      "human",
                  },
                }),
                {
                  status: 200,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
            );

            await retryPromise!;
          },
        );

        expect(
          result.current.state
            .status,
        ).toBe(
          "authenticated",
        );

        expect(
          result.current
            .isRetrying,
        ).toBe(false);
      },
    );


    it(
      "applies only the newest result when retries overlap",
      async () => {
        const first =
          deferredResponse();

        const second =
          deferredResponse();

        vi.spyOn(
          globalThis,
          "fetch",
        )
          .mockReturnValueOnce(
            first.promise,
          )
          .mockReturnValueOnce(
            second.promise,
          );

        const {
          result,
        } =
          renderHook(
            () => useAuth(),
            {
              wrapper:
                wrapperFor({
                  status:
                    "unauthenticated",
                }),
            },
          );

        let firstRetry:
          Promise<void>;

        let secondRetry:
          Promise<void>;

        act(
          () => {
            firstRetry =
              result.current.retry();

            secondRetry =
              result.current.retry();
          },
        );

        await act(
          async () => {
            second.resolve(
              new Response(
                JSON.stringify({
                  authenticated:
                    true,
                  principal: {
                    principal_id:
                      "prn_newest",
                    principal_kind:
                      "human",
                  },
                }),
                {
                  status: 200,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
            );

            await secondRetry!;
          },
        );

        expect(
          result.current.state,
        ).toEqual({
          status:
            "authenticated",
          principal: {
            principalId:
              "prn_newest",
            principalKind:
              "human",
          },
        });

        await act(
          async () => {
            first.resolve(
              new Response(
                JSON.stringify({
                  authenticated:
                    false,
                }),
                {
                  status: 200,
                  headers: {
                    "Content-Type":
                      "application/json",
                  },
                },
              ),
            );

            await firstRetry!;
          },
        );

        expect(
          result.current.state,
        ).toEqual({
          status:
            "authenticated",
          principal: {
            principalId:
              "prn_newest",
            principalKind:
              "human",
          },
        });
      },
    );


    it(
      "throws when useAuth is used outside its provider",
      () => {
        expect(
          () =>
            renderHook(
              () => useAuth(),
            ),
        ).toThrow(
          "useAuth must be used within AuthProvider.",
        );
      },
    );
  },
);
