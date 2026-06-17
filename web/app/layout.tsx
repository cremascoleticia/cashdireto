import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Cockpit de Recebíveis",
  description: "Monitoramento de garantia de recebíveis de cartão",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-br">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-slate-50 text-slate-800`}>
        <header className="bg-slate-900 text-white">
          <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
            <span className="font-semibold">Cockpit de Recebíveis</span>
            <nav className="flex gap-4 text-sm">
              <Link className="hover:underline" href="/cockpit">
                Cockpit
              </Link>
              <Link className="hover:underline" href="/garantia">
                Gestão de garantia
              </Link>
              <Link className="hover:underline" href="/raiox">
                Raio-X de colateral
              </Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
