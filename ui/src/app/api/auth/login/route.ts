import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const expected = process.env.AUTH_TOKEN;
  if (!expected) {
    return NextResponse.json({ error: "AUTH_TOKEN not configured" }, { status: 500 });
  }
  const body = (await req.json().catch(() => ({}))) as { token?: string };
  if (body.token !== expected) {
    return NextResponse.json({ error: "invalid token" }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set("auth_token", body.token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
