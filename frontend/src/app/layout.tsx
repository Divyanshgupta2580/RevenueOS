import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RevenueOS — AI Revenue Recovery Decision Engine",
  description: "Autonomous revenue recovery decision engine built for the Razorpay AI Buildathon 2026.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0A0D12] text-[#F3F4F6] min-h-screen antialiased selection:bg-[#F59E0B]/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
