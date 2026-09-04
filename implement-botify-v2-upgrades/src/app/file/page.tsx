import Link from "next/link";
import { notFound } from "next/navigation";
import { CHANGED_FILES, readV2File } from "@/lib/v2";

export const dynamic = "force-dynamic";

export default async function FilePage({
  searchParams,
}: {
  searchParams: Promise<{ path?: string }>;
}) {
  const { path: rel } = await searchParams;
  if (!rel) notFound();
  const meta = CHANGED_FILES.find((f) => f.path === rel);
  const content = await readV2File(rel);
  if (!meta || content === null) notFound();

  const lines = content.split("\n");

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/" className="text-sm text-sky-700 hover:underline">
        ← Ко всем изменениям
      </Link>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="m-0 break-all font-mono text-lg font-semibold text-slate-900">{rel}</h1>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            meta.kind === "new" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {meta.kind}
        </span>
        <span className="text-xs text-slate-500">{lines.length} строк</span>
        <a
          href={`/api/file?path=${encodeURIComponent(rel)}`}
          className="ml-auto rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50"
        >
          Скачать raw
        </a>
      </div>
      <p className="mt-2 text-sm text-slate-600">{meta.summary}</p>

      <div className="mt-6 overflow-hidden rounded-2xl bg-slate-950 shadow-sm">
        <pre className="max-h-[80vh] overflow-auto p-4 text-xs leading-relaxed text-slate-100">
          {lines.map((line, i) => (
            <div key={i} className="flex">
              <span className="w-12 shrink-0 select-none pr-3 text-right text-slate-500">{i + 1}</span>
              <span className="whitespace-pre">{line}</span>
            </div>
          ))}
        </pre>
      </div>
    </main>
  );
}
