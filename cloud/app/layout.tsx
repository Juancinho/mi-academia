import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mi Academia · Tu aprendizaje, contigo",
  description: "Tu biblioteca educativa privada, conectada con ChatGPT. Conocimientos, fuentes y práctica espaciada.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="antialiased">{children}</body>
    </html>
  );
}
