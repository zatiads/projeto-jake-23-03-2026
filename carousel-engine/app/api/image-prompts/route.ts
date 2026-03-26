import { NextResponse } from "next/server";
import OpenAI from "openai";
import { z } from "zod";
import { readFile } from "node:fs/promises";
import path from "node:path";

const requestSchema = z.object({
  theme: z.string().trim().min(3).max(180),
  tone: z.enum(["agressivo", "elegante", "educacional"]).default("elegante"),
  slides: z
    .array(
      z.object({
        id: z.string(),
        headline: z.string(),
        subheadline: z.string(),
        tag: z.string(),
      })
    )
    .length(7),
});

const responseSchema = z.object({
  prompts: z
    .array(
      z.object({
        id: z.string(),
        prompt: z.string().min(20).max(800),
      })
    )
    .length(7),
});

async function getOpenAiApiKey() {
  if (process.env.OPENAI_API_KEY) {
    return process.env.OPENAI_API_KEY;
  }

  try {
    const envPath = path.resolve(process.cwd(), "..", ".env");
    const envFile = await readFile(envPath, "utf-8");
    const line = envFile.split("\n").find((v) => v.trim().startsWith("OPENAI_API_KEY="));
    return line?.replace("OPENAI_API_KEY=", "").trim() ?? null;
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  try {
    const rawBody = (await request.json()) as unknown;
    const parsed = requestSchema.safeParse(rawBody);
    if (!parsed.success) {
      return NextResponse.json({ error: "Payload invalido." }, { status: 400 });
    }

    const apiKey = await getOpenAiApiKey();
    if (!apiKey) {
      return NextResponse.json({ error: "OPENAI_API_KEY nao configurada." }, { status: 500 });
    }

    const client = new OpenAI({ apiKey });
    const completion = await client.chat.completions.create({
      model: "gpt-4o-mini",
      temperature: 0.7,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content: [
            "You are a world-class art director specializing in hyper-cinematic, ultra-realistic editorial photography for high-end brands.",
            "Your prompts are used with DALL-E 3 to generate images for Instagram carousels.",
            "",
            "PROMPT ARCHITECTURE (apply to every image):",
            "1. SUBJECT: Describe the core visual concept tied to the slide's message. Avoid generic stock-photo subjects.",
            "2. STYLE: Cinematic ultra-realism. Blend physical reality with digital/holographic elements where relevant — glowing data streams, volumetric light rays, floating interfaces integrated seamlessly into real scenes.",
            "3. TECHNICAL: Shot on Hasselblad medium format, 50mm lens, f/1.4 aperture, shallow depth of field, sharp subject with smooth bokeh.",
            "4. LIGHTING: Dramatic chiaroscuro — deep rich shadows contrasted with luminous practicals or rim lights. Avoid flat lighting.",
            "5. COLOR: Cinematic color grade — desaturated midtones, deep shadows, vivid selective color accents (blues, electric teals or warm ambers depending on theme).",
            "6. COMPOSITION: Rule of thirds, strong leading lines, intentional negative space for text overlay area.",
            "7. CONSISTENCY: Maintain the same protagonist/environment/color palette across slides when the theme involves a person or specific setting.",
            "8. ALWAYS END WITH: 'no text, no watermarks, no logos, no UI mockups, photorealistic, 8K, award-winning commercial photography'.",
            "",
            "Output ONLY JSON: {\"prompts\":[{\"id\":\"01\",\"prompt\":\"...\"}]} with exactly 7 items.",
          ].join("\n"),
        },
        {
          role: "user",
          content: [
            `Theme: ${parsed.data.theme}`,
            `Tone: ${parsed.data.tone}`,
            `Slides: ${JSON.stringify(parsed.data.slides)}`,
            "",
            "Generate one hyper-cinematic prompt per slide that visually expresses the slide's headline and subheadline concept.",
            "Make each prompt specific, impactful, and different in composition from the others — but maintain visual consistency (same protagonist/palette).",
            "Slides about problems → tense, moody, high-contrast. Slides about solutions → luminous, aspirational, clean. CTA slide → intimate, direct, energetic.",
          ].join("\n"),
        },
      ],
    });

    const raw = completion.choices[0]?.message?.content;
    if (!raw) {
      throw new Error("Sem resposta.");
    }

    const parsedResponse = responseSchema.safeParse(JSON.parse(raw) as unknown);
    if (!parsedResponse.success) {
      throw new Error("Formato invalido.");
    }

    return NextResponse.json(parsedResponse.data);
  } catch {
    return NextResponse.json({ error: "Falha ao gerar prompts de imagem." }, { status: 500 });
  }
}
