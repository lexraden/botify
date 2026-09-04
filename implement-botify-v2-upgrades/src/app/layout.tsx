import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Botify v2 — release notes",
  description: "Имя и лого магазина → профиль бота в Telegram; /settings seller-бота на RU/EN.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="bg-slate-100 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
