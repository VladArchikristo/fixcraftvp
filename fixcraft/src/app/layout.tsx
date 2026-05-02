import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FixCraft VP — Handyman Services in Charlotte, NC",
  description:
    "Professional furniture assembly, TV mounting, and handyman services in Charlotte, NC. Same-day booking available. Call (786) 566-0753.",
  keywords:
    "handyman Charlotte NC, furniture assembly, IKEA assembly, TV mounting, FixCraft",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-gray-950 text-white">{children}</body>
    </html>
  );
}
