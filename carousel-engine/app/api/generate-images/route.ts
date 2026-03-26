import { NextResponse } from "next/server";
import Replicate from "replicate";
import { z } from "zod";
import { readFile } from "node:fs/promises";
import path from "node:path";

export const maxDuration = 120;

const requestSchema = z.object({
  prompt: z.string().trim().min(5).max(1000),
  aspectRatio: z.string().trim().optional(), // ex: "1:1", "4:5"
});

// ── Env helpers ───────────────────────────────────────────────────────────────
async function readEnvFile() {
  try {
    const envPath = path.resolve(process.cwd(), "..", ".env");
    return await readFile(envPath, "utf-8");
  } catch {
    return "";
  }
}

async function getEnvKey(name: string): Promise<string | null> {
  if (process.env[name]) return process.env[name]!;
  const envFile = await readEnvFile();
  const line = envFile.split("\n").find((l) => l.trim().startsWith(`${name}=`));
  if (!line) return null;
  return line.replace(`${name}=`, "").trim() || null;
}

// ── URL → base64 data URL ─────────────────────────────────────────────────────
async function urlToDataUrl(url: string): Promise<string> {
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const base64 = Buffer.from(buf).toString("base64");
  const mime = res.headers.get("content-type") ?? "image/jpeg";
  return `data:${mime};base64,${base64}`;
}

// ── Master cinematic style suffix ────────────────────────────────────────────
const MASTER_STYLE = [
  "Cinematic ultra-realistic editorial photograph, 8K",
  "Hyperdetailed textures, dramatic chiaroscuro lighting — deep rich shadows contrasted with luminous practicals",
  "Seamlessly blends physical reality with digital/holographic elements: glowing data streams, floating UI interfaces, volumetric light rays integrated into real scenes",
  "Shot on Hasselblad medium format, 50mm f/1.4, shallow depth of field with smooth bokeh",
  "Cinematic color grade: desaturated midtones, vivid selective color accents (electric teal or warm amber)",
  "Award-winning commercial photography, magazine cover quality",
  "No text, no watermarks, no logos, no UI mockups",
].join(". ");

// ── Handler usando Replicate + google/imagen-4 ───────────────────────────────
export async function POST(request: Request) {
  try {
    const raw = (await request.json()) as unknown;
    const parsed = requestSchema.safeParse(raw);

    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0]?.message ?? "Prompt inválido." },
        { status: 400 },
      );
    }

    const { prompt, aspectRatio } = parsed.data;

    const token = await getEnvKey("REPLICATE_API_TOKEN");
    if (!token) {
      return NextResponse.json(
        { error: "REPLICATE_API_TOKEN não configurado no ambiente." },
        { status: 500 },
      );
    }

    const replicate = new Replicate({ auth: token });

    const finalPrompt = `${prompt}. ${MASTER_STYLE}`;

    const output = (await replicate.run("google/imagen-4", {
      input: {
        prompt: finalPrompt,
        aspect_ratio: aspectRatio || "4:5",
        safety_filter_level: "block_only_high",
        output_format: "jpg",
      },
    })) as string | string[];

    const imageUrl = Array.isArray(output) ? output[0] : output;
    if (!imageUrl) {
      return NextResponse.json({ error: "Geração sem retorno." }, { status: 500 });
    }

    const dataUrl = await urlToDataUrl(imageUrl);
    return NextResponse.json({ dataUrl, prompt, model: "google/imagen-4" });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Erro desconhecido.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
