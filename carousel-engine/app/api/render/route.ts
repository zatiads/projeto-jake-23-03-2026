import { NextResponse } from "next/server";
import { z } from "zod";
import { renderSlideToPng } from "@/lib/render";

const requestSchema = z.object({
  id: z.string().min(1).max(4).default("01"),
  headline: z.string().trim().min(3).max(160),
  subheadline: z.string().trim().min(3).max(260),
  tag: z.string().trim().min(2).max(24),
  variant: z.enum(["cover", "split", "statement", "closing"]).optional(),
  backgroundImage: z.string().url().optional().or(z.literal("")),
  grayscale: z.boolean().optional(),
  overlayOpacity: z.number().min(0).max(0.95).optional(),
  lightMode: z.boolean().optional(),
});

const thumbnailQuerySchema = z.object({
  payload: z.string().min(1),
});

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as unknown;
    const parsed = requestSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0]?.message ?? "Payload invalido." },
        { status: 400 }
      );
    }

    const png = await renderSlideToPng(parsed.data);
    const payload = Uint8Array.from(png);

    return new Response(payload as unknown as BodyInit, {
      headers: {
        "Content-Type": "image/png",
        "Content-Disposition": `inline; filename="${parsed.data.id}.png"`,
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ error: "Falha ao renderizar slide." }, { status: 500 });
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const parsedQuery = thumbnailQuerySchema.safeParse({
      payload: searchParams.get("payload") ?? "",
    });

    if (!parsedQuery.success) {
      return NextResponse.json({ error: "Payload ausente." }, { status: 400 });
    }

    const rawPayload = JSON.parse(decodeURIComponent(parsedQuery.data.payload)) as unknown;
    const parsedBody = requestSchema.safeParse(rawPayload);

    if (!parsedBody.success) {
      return NextResponse.json(
        { error: parsedBody.error.issues[0]?.message ?? "Payload invalido." },
        { status: 400 }
      );
    }

    const png = await renderSlideToPng(parsedBody.data);
    const payload = Uint8Array.from(png);

    return new Response(payload as unknown as BodyInit, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=120",
      },
    });
  } catch {
    return NextResponse.json({ error: "Falha ao gerar thumbnail." }, { status: 500 });
  }
}
