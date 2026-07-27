import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Khizar Sultan — AI & ML Portfolio",
  description:
    "Live, interactive AI and machine-learning projects across healthcare, cybersecurity, and finance — built by Khizar Sultan.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
