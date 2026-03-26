import { NextResponse } from "next/server";
import OpenAI from "openai";
import { z } from "zod";
import { readFile } from "node:fs/promises";
import path from "node:path";

type SlideCopy = {
  headline: string;
  subheadline: string;
  tag: string;
  bullets?: string[];
};

type CopyTone = "agressivo" | "elegante" | "educacional";

const SYSTEM_PROMPT = `Voce e um Copywriter Senior especializado em ofertas high-ticket para Instagram.
Sua escrita e assertiva, sofisticada e focada em conversao.

OBJETIVO:
Transformar um tema em carrossel de 7 slides com narrativa persuasiva.

REGRAS DE COPY (OBRIGATORIAS):
1) Frases curtas e de alto impacto.
2) Evitar cliches, jargoes vazios e promessas irreais.
3) Nao usar emojis.
4) Linguagem de autoridade com clareza e especificidade.
5) Headline e subheadline devem se complementar sem repetir a mesma ideia.
6) Cada slide precisa avancar a narrativa (nao repetir argumento).
7) CTA final com acao clara e imediata.

ESTRUTURA FIXA:
- Slide 1: GANCHO (interrompe scroll)
- Slide 2-3: PROBLEMA (dor, custo da inacao, erro comum)
- Slide 4: SOLUCAO (apresenta o caminho)
- Slide 5: BULLETS — lista de 3 a 4 topicos curtos e objetivos (metodo, passos, criterios)
- Slide 6: VALOR (resultado concreto, dado, prova)
- Slide 7: CTA (acao objetiva)

FORMATO DE SAIDA:
Retorne SOMENTE JSON valido no formato:
{
  "slides": [
    { "headline": "...", "subheadline": "...", "tag": "...", "bullets": [] }
  ]
}

REGRAS ESPECIAIS PARA O SLIDE 5 (BULLETS):
- headline: titulo curto que introduz a lista (ex: "3 passos para X")
- subheadline: string vazia ""
- bullets: array com 3 ou 4 frases curtas (max 60 chars cada), diretas, sem verbo auxiliar, sem emojis.
  Exemplo: ["Identifique o gargalo principal", "Implemente sem depender de budget extra", "Mensure em 15 dias"]
- Para todos os outros slides: bullets deve ser []

CONSTRAINTS:
- Exatamente 7 itens no array "slides".
- headline: 5 a 110 caracteres.
- subheadline: 0 a 170 caracteres (vazio no slide 5).
- tag em maiusculas.
- Portugues do Brasil.`;

const TONE_GUIDANCE: Record<CopyTone, string> = {
  agressivo:
    "Tom agressivo: direto ao ponto, senso de urgencia, contraste forte entre dor e ganho, CTA incisivo.",
  elegante:
    "Tom elegante: premium, sofisticado, objetivo sem ser apelativo, vocabulario refinado e confiante.",
  educacional:
    "Tom educacional: didatico, autoridade pela clareza, foco em explicar criterios e metodo com objetividade.",
};

const requestSchema = z.object({
  theme: z.string().trim().min(3, "Tema muito curto.").max(180, "Tema muito longo."),
  tone: z.enum(["agressivo", "elegante", "educacional"]).default("elegante"),
});

const slideSchema = z.object({
  headline: z.string().trim().min(5).max(140),
  subheadline: z.string().trim().max(220).default(""),
  tag: z.string().trim().min(2).max(24),
  bullets: z.array(z.string().trim().max(100)).max(4).default([]),
});

const modelResponseSchema = z.object({
  slides: z.array(slideSchema).length(7),
});

function createFallbackSlides(theme: string, tone: CopyTone): SlideCopy[] {
  const suffix =
    tone === "agressivo"
      ? "Sem desculpas, sem ruido."
      : tone === "educacional"
        ? "Com logica clara e aplicavel."
        : "Com presenca premium e precisao.";

  return [
    {
      headline: `${theme}: o filtro que separa amadores de autoridade`,
      subheadline: `Seu publico decide em segundos se voce merece atencao. ${suffix}`,
      tag: "GANCHO",
    },
    {
      headline: "A maioria publica sem estrategia visual",
      subheadline: "Sem narrativa e contraste, o conteudo perde valor percebido.",
      tag: "PROBLEMA",
    },
    {
      headline: "Informacao sem hierarquia nao converte",
      subheadline: "Quando tudo tem o mesmo peso, nada fixa.",
      tag: "PROBLEMA",
    },
    {
      headline: "Comece pelo conflito central do tema",
      subheadline: "Defina a dor principal e conduza a tensao com clareza.",
      tag: "SOLUCAO",
    },
    {
      headline: "Transforme tese em blocos de impacto",
      subheadline: "Uma ideia por slide, linguagem curta e memoravel.",
      tag: "SOLUCAO",
    },
    {
      headline: "Feche com prova de valor",
      subheadline: "Mostre resultado, metodo ou criterio que sustenta sua autoridade.",
      tag: "VALOR",
    },
    {
      headline: "Quer previsibilidade nos proximos posts?",
      subheadline: "Use este framework e publique seu proximo carrossel hoje.",
      tag: "CTA",
    },
  ];
}

async function getOpenAiApiKey() {
  if (process.env.OPENAI_API_KEY) {
    return process.env.OPENAI_API_KEY;
  }

  try {
    const envPath = path.resolve(process.cwd(), "..", ".env");
    const envFile = await readFile(envPath, "utf-8");
    const line = envFile
      .split("\n")
      .find((fileLine) => fileLine.trim().startsWith("OPENAI_API_KEY="));

    if (!line) {
      return null;
    }

    return line.replace("OPENAI_API_KEY=", "").trim();
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  let themeForFallback = "Tema";
  let toneForFallback: CopyTone = "elegante";

  try {
    const rawBody = (await request.json()) as unknown;
    const parsedBody = requestSchema.safeParse(rawBody);

    if (!parsedBody.success) {
      return NextResponse.json(
        { error: parsedBody.error.issues[0]?.message ?? "Tema invalido." },
        { status: 400 }
      );
    }

    const theme = parsedBody.data.theme;
    const tone = parsedBody.data.tone;
    themeForFallback = theme;
    toneForFallback = tone;
    const apiKey = await getOpenAiApiKey();

    if (!apiKey) {
      return NextResponse.json(
        { error: "OPENAI_API_KEY nao configurada no ambiente." },
        { status: 500 }
      );
    }

    const client = new OpenAI({ apiKey });

    const completion = await client.chat.completions.create({
      model: "gpt-4o-mini",
      temperature: 0.7,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: [
            `Tema: ${theme}`,
            `Tom solicitado: ${tone}. ${TONE_GUIDANCE[tone]}`,
            'Retorne SOMENTE JSON no formato: {"slides":[{"headline":"...","subheadline":"...","tag":"..."}, ...7 itens]}',
            "Respeite a estrutura: Slide 1 Gancho, 2-3 Problema, 4-6 Solucao/Valor, 7 CTA.",
            "Nao repita headline entre slides e nao use linguagem generica.",
          "O slide 5 DEVE ter bullets: array com 3-4 topicos curtos. Todos os outros slides: bullets: []",
          ].join("\n"),
        },
      ],
    });

    const rawContent = completion.choices[0]?.message?.content;

    if (!rawContent) {
      throw new Error("Resposta vazia do modelo.");
    }

    const parsedJson = JSON.parse(rawContent) as unknown;
    const parsedSlides = modelResponseSchema.safeParse(parsedJson);

    if (!parsedSlides.success) {
      throw new Error("Formato de resposta invalido.");
    }

    return NextResponse.json({
      theme,
      tone,
      slides: parsedSlides.data.slides,
    });
  } catch {
    return NextResponse.json(
      {
        error: "Falha ao processar com IA. Usando fallback local.",
        slides: createFallbackSlides(themeForFallback, toneForFallback),
      },
      { status: 500 }
    );
  }
}
