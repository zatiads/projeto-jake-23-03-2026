import { NextResponse } from "next/server";
import JSZip from "jszip";
import { z } from "zod";
import { renderSlideToPng } from "@/lib/render";

export const maxDuration = 60; // seconds (Vercel Pro/Enterprise; no-op on Hobby but safe)

const slideSchema = z.object({
  id: z.string().min(1).max(4),
  headline: z.string().trim().min(1).max(160),
  subheadline: z.string().trim().max(260).default(""),
  tag: z.string().trim().min(1).max(24),
  variant: z.enum(["cover", "split", "statement", "closing", "bullets"]).optional(),
  backgroundImage: z.string().optional(),
  grayscale: z.boolean().optional(),
  overlayOpacity: z.number().min(0).max(0.95).optional(),
  lightMode: z.boolean().optional(),
  headlineSize: z.number().min(50).max(180).optional(),
  subheadlineSize: z.number().min(50).max(180).optional(),
  bullets: z.array(z.string()).max(4).optional(),
  ctaText: z.string().trim().max(120).optional(),
  imagePosX: z.number().min(0).max(100).optional(),
  imagePosY: z.number().min(0).max(100).optional(),
});

const requestSchema = z.object({
  slides: z.array(slideSchema).length(7),
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

    const zip = new JSZip();

    // Sequential rendering to avoid memory spikes and respect serverless limits
    for (let i = 0; i < parsed.data.slides.length; i++) {
      const slide = parsed.data.slides[i]!;
      const png = await renderSlideToPng(slide);
      const filename = `${String(i + 1).padStart(2, "0")}.png`;
      zip.file(filename, png);
    }

    const archive = await zip.generateAsync({ type: "uint8array" });
    const archiveCopy = Uint8Array.from(archive);

    return new Response(archiveCopy as unknown as BodyInit, {
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="carousel.zip"',
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[export] render error:", message);
    return NextResponse.json(
      { error: `Falha ao renderizar: ${message}` },
      { status: 500 }
    );
  }
}
