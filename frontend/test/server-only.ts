// Test-only shim for Next.js `server-only`.
//
// Next.js handles `import "server-only"` specially during
// application compilation. Vitest does not run through that
// compiler path and would execute the npm marker package,
// whose runtime body intentionally throws.
//
// This shim exists only in the Vitest resolver. Production
// code retains the real `import "server-only"` boundary.
export {};
