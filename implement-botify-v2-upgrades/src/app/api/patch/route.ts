import { readPatch } from "@/lib/v2";

export const dynamic = "force-dynamic";

export async function GET() {
  const patch = await readPatch();
  if (patch === null) {
    return new Response("patch not generated", { status: 404 });
  }
  return new Response(patch, {
    headers: {
      "content-type": "text/x-patch; charset=utf-8",
      "content-disposition": 'attachment; filename="v2.patch"',
    },
  });
}
