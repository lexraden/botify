import { NextRequest } from "next/server";
import { readV2File } from "@/lib/v2";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const rel = req.nextUrl.searchParams.get("path") ?? "";
  const content = await readV2File(rel);
  if (content === null) {
    return new Response("not found", { status: 404 });
  }
  const name = rel.split("/").pop() ?? "file.txt";
  return new Response(content, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "content-disposition": `attachment; filename="${name}"`,
    },
  });
}
