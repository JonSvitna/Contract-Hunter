import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Local Contract Hunter AI",
  description: "Private MVP for local Maryland contract discovery"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="container flex items-center justify-between py-4">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Vulnaguard LLC</div>
              <h1 className="text-lg font-semibold text-navy">Local Contract Hunter AI</h1>
            </div>
            <nav className="flex gap-5 text-sm text-slate-700">
              <Link href="/">Dashboard</Link>
              <Link href="/opportunities">Opportunities</Link>
              <Link href="/sources">Sources</Link>
              <Link href="/settings">Settings</Link>
            </nav>
          </div>
        </header>
        <main className="container py-6">{children}</main>
      </body>
    </html>
  );
}
