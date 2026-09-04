import type { Metadata } from "next";
import Script from "next/script";
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
      <head>
        <Script
          src="https://checkout.razorpay.com/v1/checkout.js"
          strategy="afterInteractive"
        />
      </head>
      <body className="bg-[#0A0D12] text-[#F3F4F6] min-h-screen antialiased selection:bg-[#F59E0B]/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
