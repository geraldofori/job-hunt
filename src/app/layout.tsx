import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShellNav } from "@/features/shell/AppShellNav";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Job Hunt",
  description: "Werkstudent application command center",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full">
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 border-r md:block">
          <div className="flex h-14 items-center border-b px-4">
            <p className="text-sm font-semibold tracking-tight">Job Hunt</p>
          </div>
          <AppShellNav />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center border-b px-6 md:hidden">
            <p className="text-sm font-semibold tracking-tight">Job Hunt</p>
          </header>
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
