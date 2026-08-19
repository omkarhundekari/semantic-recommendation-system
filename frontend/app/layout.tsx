import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import {
  AuthProvider,
  type AuthState,
} from "@/lib/auth/AuthProvider";

import {
  BrowserProfileUnavailableError,
  resolveBrowserProfile,
} from "@/lib/auth/browserProfile";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Solvyn",
  description: "Evidence-grounded project directions and interactive execution roadmaps.",
};

async function resolveInitialAuthState():
  Promise<AuthState> {
  try {
    const resolution =
      await resolveBrowserProfile();

    if (!resolution.authenticated) {
      // Server Components intentionally do not mutate
      // session cookies. A stale credential is cleared only
      // by the /api/me route handler on a later retry.
      return {
        status: "unauthenticated",
      };
    }

    return {
      status: "authenticated",
      principal: {
        principalId:
          resolution.profile.principalId,
        principalKind:
          resolution.profile.principalKind,
      },
    };
  } catch (
    error
  ) {
    if (
      error
      instanceof BrowserProfileUnavailableError
    ) {
      return {
        status: "unavailable",
      };
    }

    throw error;
  }
}


export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const initialAuthState =
    await resolveInitialAuthState();

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider
          initialState={
            initialAuthState
          }
        >
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
