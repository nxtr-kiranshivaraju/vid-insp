import { NextRequest, NextResponse } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

async function proxy(req: NextRequest, ctx: { params: { path: string[] } }) {
  const base = process.env.COMPILER_URL;
  if (!base) {
    return NextResponse.json({ error: "COMPILER_URL not configured" }, { status: 500 });
  }

  const url = new URL(`${base.replace(/\/$/, "")}/${ctx.params.path.join("/")}`);
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const headers = new Headers();
  req.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k.toLowerCase())) headers.set(k, v);
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (err) {
    return NextResponse.json(
      { error: "compiler service unreachable", detail: String(err) },
      { status: 502 },
    );
  }

  const respHeaders = new Headers();
  upstream.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k.toLowerCase())) respHeaders.set(k, v);
  });
  return new NextResponse(upstream.body, { status: upstream.status, headers: respHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
