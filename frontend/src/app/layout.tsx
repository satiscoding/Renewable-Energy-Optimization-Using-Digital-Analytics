import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solar & Wind Control Room | Digital Analytics Platform",
  description: "Phase-II B.Tech Final-Year Capstone: Renewable Energy Optimization using Digital Analytics.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#090D16] text-slate-100 min-h-screen selection:bg-amber-500/30 selection:text-amber-200">
        {children}
      </body>
    </html>
  );
}
