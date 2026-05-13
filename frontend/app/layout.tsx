import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Toaster } from "@/components/ui/Toaster";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "BharatQuant — AI Indian Market Analysis",
  description:
    "AI-powered Indian stock market analysis & trade-signal platform. Educational use only.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans min-h-screen`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 p-4 md:p-6 lg:p-8 animate-fade-in">
              {children}
            </main>
            <footer className="border-t border-border px-6 py-3 text-xs text-muted-foreground text-center">
              ⚠️ This tool is for educational and research purposes only —
              <span className="font-medium"> not financial advice.</span>
            </footer>
          </div>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
