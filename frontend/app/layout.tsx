import type React from "react";
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Analytics } from "@vercel/analytics/next";
import { Toaster } from "@/components/ui/toaster";
import { Navbar } from "@/components/navbar";
import { Suspense } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "File Repo",
  description: "File Repository",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable}`}>
        <div className="min-h-dvh bg-[radial-gradient(1200px_600px_at_50%_-50%,oklch(0.205_0_0/.35),transparent)]">
          <header>
            <Suspense fallback={<div>Loading...</div>}>
              <Navbar />
            </Suspense>
          </header>
          <main className="container mx-auto px-4 py-6">
            <Suspense fallback={<div>Loading...</div>}>{children}</Suspense>
          </main>
        </div>
        <Toaster />
        <Analytics />
      </body>
    </html>
  );
}
