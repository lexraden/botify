import Link from "next/link";
import { db } from "@/db";
import { sql } from "drizzle-orm";
import { CHANGED_FILES, readPatch } from "@/lib/v2";

export const dynamic = "force-dynamic";

const FEATURES = [
  {
    title: "Имя и лого магазина → профиль бота в Telegram",
    items: [
      "PUT /bots/{id}/shop-name → setMyName; null → исходное имя из seller_bots.default_bot_name",
      "POST /bots/{id}/shop-logo → setMyProfilePhoto (Bot API 9.x, aiogram ≥ 3.30); JPEG 640×640, центр-кроп, альфа на белом",
      "DELETE /bots/{id}/shop-logo → removeMyProfilePhoto",
      "Ошибки Telegram (токен отозван, бот заблокирован, 429) логируются и не роняют запрос кабинета",
      "В ответах эндпоинтов — telegram_sync: ok | skipped | rate_limited | failed (+ retry_after)",
    ],
  },
  {
    title: "Настройки seller-бота на RU/EN",
    items: [
      "Весь маршрут /settings через ключи settings.* в seller_texts.py",
      "Язык — тот же выбор /lang (sellers.locale); RU-строки байт-в-байт прежние",
      "Чужаку алерт «Настройки доступны только владельцу магазина.» по-прежнему русский",
      "owner_of() возвращает Seller — язык берётся без второго запроса в БД",
    ],
  },
  {
    title: "Свои улучшения v2",
    items: [
      "Экран «🪪 Профиль в Telegram» в /settings: ручная досылка имени и лого для ботов, подключённых до v2",
      "Разбор 429 Too Many Requests у setMyName: retry_after уходит в ответ и в пуш продавцу",
      "EXIF-поворот и первый кадр анимаций при подготовке аватара",
      "default_bot_name фиксируется и у managed-ботов (managed_bot_created.first_name)",
      "20 тестов на сервис и i18n без сети и без Telegram",
    ],
  },
];

export default async function HomePage() {
  await db.execute(sql`select 1`);
  const patch = await readPatch();
  const patchLines = patch ? patch.split("\n").length : 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="rounded-3xl bg-white p-10 shadow-[0_24px_60px_rgba(16,24,40,0.12)]">
        <p className="m-0 text-sm uppercase tracking-[0.08em] text-slate-500">lexraden/botify · release notes</p>
        <h1 className="mt-3 text-[clamp(2rem,5vw,3rem)] font-semibold leading-tight text-slate-950">
          Botify v2 — профиль бота в Telegram и RU/EN настройки
        </h1>
        <p className="mt-4 max-w-3xl text-slate-700">
          Готовый набор изменений поверх ветки <code className="rounded bg-slate-100 px-1">main</code>: новый сервис{" "}
          <code className="rounded bg-slate-100 px-1">backend/app/services/bot_profile.py</code>, миграция{" "}
          <code className="rounded bg-slate-100 px-1">c3d4e5f6a7b8</code>, переведённый{" "}
          <code className="rounded bg-slate-100 px-1">/settings</code> seller-бота и тесты. Ниже — файлы и патч.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            href="/api/patch"
            className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Скачать v2.patch {patchLines ? `(${patchLines} строк)` : ""}
          </a>
          <a
            href="https://github.com/lexraden/botify/tree/main"
            className="rounded-full border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
            target="_blank"
            rel="noreferrer"
          >
            Исходный репозиторий ↗
          </a>
        </div>
      </header>

      <section className="mt-10 grid gap-6 md:grid-cols-3">
        {FEATURES.map((f) => (
          <article key={f.title} className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-lg font-semibold text-slate-900">{f.title}</h2>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {f.items.map((i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-emerald-600">✓</span>
                  <span>{i}</span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="mt-10 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <h2 className="text-lg font-semibold text-slate-900">Изменённые файлы</h2>
        <p className="mt-1 text-sm text-slate-600">
          Пути указаны от корня репозитория. Нажми на файл, чтобы посмотреть готовое содержимое.
        </p>
        <ul className="mt-4 divide-y divide-slate-100">
          {CHANGED_FILES.map((f) => (
            <li key={f.path} className="flex flex-col gap-1 py-3 md:flex-row md:items-start md:gap-4">
              <span
                className={`inline-flex w-fit shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                  f.kind === "new" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                }`}
              >
                {f.kind === "new" ? "new" : "modified"}
              </span>
              <div className="min-w-0">
                <Link
                  href={`/file?path=${encodeURIComponent(f.path)}`}
                  className="font-mono text-sm text-sky-700 hover:underline"
                >
                  {f.path}
                </Link>
                <p className="m-0 mt-0.5 text-sm text-slate-600">{f.summary}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10 rounded-2xl bg-slate-950 p-6 text-slate-100 shadow-sm">
        <h2 className="text-lg font-semibold">Как применить и запушить</h2>
        <pre className="mt-3 overflow-x-auto text-xs leading-relaxed">
{`git clone https://github.com/lexraden/botify.git && cd botify
git checkout -b v2-bot-profile
curl -sL <URL этой страницы>/api/patch -o v2.patch
git apply --index v2.patch            # или скопировать файлы из botify-v2/ поверх репозитория

cd backend
.venv/bin/pip install -r requirements.txt   # aiogram>=3.30, Pillow
.venv/bin/alembic upgrade head              # c3d4e5f6a7b8_default_bot_name
.venv/bin/pytest -q tests/test_bot_profile.py

cd .. && git commit -m "v2: имя и лого магазина → профиль бота в Telegram; /settings на RU/EN"
git push -u origin v2-bot-profile`}
        </pre>
        <p className="mt-3 text-xs text-slate-400">
          Ревизия миграции: в main уже есть <code>v6d7e8f9a0b1_product_variants</code>, поэтому новая миграция получила
          id <code>c3d4e5f6a7b8</code> с down_revision = <code>b2c3d4e5f6a7</code> (текущий head).
        </p>
      </section>
    </main>
  );
}
