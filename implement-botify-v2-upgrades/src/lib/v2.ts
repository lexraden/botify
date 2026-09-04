import { promises as fs } from "node:fs";
import path from "node:path";

export const V2_ROOT = path.join(process.cwd(), "botify-v2");

export type ChangeKind = "new" | "modified";

export interface ChangedFile {
  path: string;
  kind: ChangeKind;
  summary: string;
}

export const CHANGED_FILES: ChangedFile[] = [
  {
    path: "backend/app/services/bot_profile.py",
    kind: "new",
    summary:
      "Сервис синхронизации профиля бота: setMyName / setMyProfilePhoto / removeMyProfilePhoto, Pillow-конвертация лого 640×640, статусы ok/skipped/rate_limited/failed.",
  },
  {
    path: "backend/alembic/versions/c3d4e5f6a7b8_default_bot_name.py",
    kind: "new",
    summary: "Миграция: seller_bots.default_bot_name (исходное Telegram-имя). Прогнана up→down→up.",
  },
  {
    path: "backend/tests/test_bot_profile.py",
    kind: "new",
    summary: "20 тестов: конвертация картинки, вызовы Telegram на фейке, ошибки не роняют запрос, паритет RU/EN.",
  },
  {
    path: "backend/app/handlers/seller/settings.py",
    kind: "modified",
    summary: "Весь /settings через ключи settings.* (RU/EN по sellers.locale), owner_of() вместо второго запроса, экран «Профиль в Telegram».",
  },
  {
    path: "backend/app/services/seller_texts.py",
    kind: "modified",
    summary: "58 ключей settings.* + api.profile_sync_failed / api.profile_rate_limited в обоих языках; RU-строки прежние.",
  },
  {
    path: "backend/app/api/seller.py",
    kind: "modified",
    summary: "shop-name / shop-logo вызывают bot_profile, в ответе telegram_sync; summary отдаёт default_bot_name.",
  },
  {
    path: "backend/app/models/bots.py",
    kind: "modified",
    summary: "Поле default_bot_name у SellerBot.",
  },
  {
    path: "backend/app/services/bot_connect.py",
    kind: "modified",
    summary: "Фиксация default_bot_name из getMe.first_name при подключении и переподключении.",
  },
  {
    path: "backend/app/services/shop_draft.py",
    kind: "modified",
    summary: "promote_draft(bot_name=…) — исходное имя managed-бота.",
  },
  {
    path: "backend/app/handlers/hub/newshop.py",
    kind: "modified",
    summary: "Передаёт first_name созданного бота в promote_draft.",
  },
  {
    path: "backend/requirements.txt",
    kind: "modified",
    summary: "aiogram>=3.30, Pillow>=10.4.",
  },
  { path: "CHANGELOG.md", kind: "modified", summary: "Запись v2 от 2026-09-04." },
  { path: "README.md", kind: "modified", summary: "Раздел «Что нового в v2»." },
];

export function isAllowedPath(rel: string): boolean {
  return CHANGED_FILES.some((f) => f.path === rel);
}

export async function readV2File(rel: string): Promise<string | null> {
  if (!isAllowedPath(rel)) return null;
  const abs = path.join(V2_ROOT, rel);
  if (!abs.startsWith(V2_ROOT)) return null;
  try {
    return await fs.readFile(abs, "utf8");
  } catch {
    return null;
  }
}

export async function readPatch(): Promise<string | null> {
  try {
    return await fs.readFile(path.join(V2_ROOT, "v2.patch"), "utf8");
  } catch {
    return null;
  }
}
