"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  ImageIcon,
  LayoutDashboard,
  Shuffle,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ─── Types ──────────────────────────────────────────────────────────────────

type GeneratedImage = {
  slideId: string;
  prompt: string;
  dataUrl: string | null;
  error?: string;
  model?: string;
};

type SlideVariant = "cover" | "split" | "statement" | "closing" | "bullets";
type CopyTone = "agressivo" | "elegante" | "educacional";

type Slide = {
  id: string;
  headline: string;
  subheadline: string;
  tag: string;
  variant: SlideVariant;
  backgroundImage?: string;
  grayscale?: boolean;
  overlayOpacity?: number;
  lightMode?: boolean;
  imagePrompt?: string;
  headlineSize?: number;
  subheadlineSize?: number;
  bullets?: string[];
  ctaText?: string;
  imagePosX?: number;  // 0–100, default 50
  imagePosY?: number;  // 0–100, default 50
};

const VARIANT_LABELS: Record<SlideVariant, string> = {
  cover: "Capa",
  split: "Texto + Img",
  statement: "Statement",
  closing: "Fechamento",
  bullets: "Bullets",
};

const CTA_PRESETS = [
  "Siga @brunozatii para mais conteúdos",
  "Me segue pra não perder o próximo",
  "Salve esse post pra consultar depois",
  "Compartilhe com quem precisa disso",
  "Comente 'QUERO' e te mando mais",
  "Acesse o link na bio",
];

const DEFAULT_CTA = CTA_PRESETS[0];

const DEFAULT_SLIDES: Slide[] = [
  { id: "01", headline: "Título principal aqui", subheadline: "Subtítulo de apoio.", tag: "GANCHO", variant: "cover" },
  { id: "02", headline: "O problema real", subheadline: "Detalhe do problema.", tag: "PROBLEMA", variant: "split" },
  { id: "03", headline: "Por que acontece?", subheadline: "Raiz da questão.", tag: "PROBLEMA", variant: "split" },
  { id: "04", headline: "A solução existe", subheadline: "Apresentando a solução.", tag: "SOLUÇÃO", variant: "split" },
  { id: "05", headline: "O método em 3 passos", subheadline: "", tag: "VALOR", variant: "bullets", bullets: ["Identifique o problema raiz", "Aplique o método testado", "Mensure e escale os resultados"] },
  { id: "06", headline: "Resultado concreto", subheadline: "O que você vai alcançar.", tag: "VALOR", variant: "statement" },
  { id: "07", headline: "Próximo passo", subheadline: "Como começar agora.", tag: "CTA", variant: "closing", ctaText: DEFAULT_CTA },
];

// ─── SlideDots ───────────────────────────────────────────────────────────────

function SlideDots({ activeIndex, lightMode }: { activeIndex: number; lightMode?: boolean }) {
  return (
    <div className="flex gap-[5px]">
      {Array.from({ length: 7 }).map((_, i) => (
        <div
          key={i}
          className={`rounded-full transition-all ${
            i === activeIndex
              ? lightMode
                ? "w-4 h-[6px] bg-[#111126]"
                : "w-4 h-[6px] bg-[#f2f2de]"
              : lightMode
                ? "w-[6px] h-[6px] bg-[#111126]/25"
                : "w-[6px] h-[6px] bg-[#f2f2de]/25"
          }`}
        />
      ))}
    </div>
  );
}

// ─── SlidePreview (CSS only) ─────────────────────────────────────────────────

function SlidePreview({
  slide,
  activeIndex,
  compact = false,
  onPositionChange,
}: {
  slide: Slide;
  activeIndex: number;
  compact?: boolean;
  onPositionChange?: (x: number, y: number) => void;
}) {
  const darkMode = !slide.lightMode;
  const dragState = useRef<{ sx: number; sy: number; px: number; py: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const posX = slide.imagePosX ?? 50;
  const posY = slide.imagePosY ?? 50;
  const textPrimary = darkMode ? "text-[#f2f2de]" : "text-[#111126]";
  const textMeta = darkMode ? "text-[#f2f2de]/70" : "text-[#111126]/65";
  const baseBg = darkMode ? "bg-[#02021a]" : "bg-[#f5f5f7]";

  // Responsive font sizes using container query units (cqw = % of container width)
  // Base sizes calibrated to match the 1080px Satori render proportionally
  const hlBase = slide.variant === "cover" ? 8.15 : 6.85;
  const subBase = 4.63;
  const hlSize = `${hlBase * ((slide.headlineSize ?? 100) / 100)}cqw`;
  const subSize = `${subBase * ((slide.subheadlineSize ?? 100) / 100)}cqw`;

  return (
    <div
      className={`relative w-full aspect-[4/5] overflow-hidden [container-type:inline-size] ${baseBg} ${textPrimary}`}
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <div className="absolute inset-0 flex flex-col p-[7%]">
        {/* Header metadata */}
        <div className={`flex items-center justify-between mb-[4%] ${textMeta}`} style={{ fontSize: "2.1cqw" }}>
          <span className="font-medium">@brunozatii</span>
          <span>Fevereiro 2026 ®</span>
        </div>

        {/* Accent line */}
        <div className="flex items-center gap-[3%] mb-[3%]">
          <div className="h-[2px] rounded-full bg-[#003cbb]" style={{ width: "7cqw" }} />
          <div className="h-[2px] rounded-full bg-[#003cbb]/25 flex-1" />
        </div>

        {/* Headline — max 3 lines to guarantee breathing room */}
        <h2
          className="font-black tracking-[-0.05em] leading-[1.05] mb-[4%] overflow-hidden"
          style={{
            fontSize: hlSize,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
          }}
        >
          {slide.headline}
        </h2>

        {/* Content block — adapts by variant */}
        {slide.variant === "bullets" ? (
          // ── Numbered editorial bullets ─────────────────────────────────────
          <div className="flex-1 flex flex-col justify-center min-h-0" style={{ margin: "2% 0" }}>
            {(slide.bullets ?? []).slice(0, 4).map((bullet, i) => (
              <div key={i}>
                {i > 0 && (
                  <div
                    className="w-full"
                    style={{
                      height: "1px",
                      background: slide.lightMode ? "rgba(0,0,0,0.1)" : "rgba(255,255,255,0.1)",
                      margin: "2.8cqw 0",
                    }}
                  />
                )}
                <div className="flex items-center" style={{ gap: "4%" }}>
                  <span
                    className="shrink-0 font-black tabular-nums text-[#003cbb]"
                    style={{ fontSize: `calc(${subSize} * 0.8)`, minWidth: "5cqw", lineHeight: 1 }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span
                    className="flex-1 font-bold leading-[1.25] tracking-[-0.03em]"
                    style={{ fontSize: subSize }}
                  >
                    {bullet}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : slide.variant === "statement" ? (
          <div className="shrink-0 h-[2px] w-full rounded bg-[#003cbb]/25 mb-[5%]" />
        ) : (
          <div
            className="relative overflow-hidden rounded-xl mb-[4%] shrink-0"
            style={{
              height: "36cqw",
              cursor: slide.backgroundImage && !compact ? (dragging ? "grabbing" : "grab") : "default",
            }}
            onMouseDown={(e) => {
              if (!slide.backgroundImage || compact || !onPositionChange) return;
              dragState.current = { sx: e.clientX, sy: e.clientY, px: posX, py: posY };
              setDragging(true);
              e.preventDefault();
            }}
            onMouseMove={(e) => {
              if (!dragState.current || !onPositionChange) return;
              const containerW = e.currentTarget.offsetWidth;
              const containerH = e.currentTarget.offsetHeight;
              const dx = ((e.clientX - dragState.current.sx) / containerW) * 100 * 0.6;
              const dy = ((e.clientY - dragState.current.sy) / containerH) * 100 * 0.6;
              const nx = Math.max(0, Math.min(100, dragState.current.px - dx));
              const ny = Math.max(0, Math.min(100, dragState.current.py - dy));
              onPositionChange(nx, ny);
            }}
            onMouseUp={() => { dragState.current = null; setDragging(false); }}
            onMouseLeave={() => { dragState.current = null; setDragging(false); }}
          >
            {slide.backgroundImage ? (
              <>
                <div
                  className="absolute inset-0 bg-cover"
                  style={{
                    backgroundImage: `url(${slide.backgroundImage})`,
                    backgroundPosition: `${posX}% ${posY}%`,
                    filter: slide.grayscale ? "grayscale(1)" : "none",
                  }}
                />
                {darkMode && (
                  <div
                    className="absolute inset-0 bg-black"
                    style={{ opacity: slide.overlayOpacity ?? 0.35 }}
                  />
                )}
                {/* Drag hint — only on active (non-compact) preview */}
                {!compact && (
                  <div className="absolute bottom-1.5 right-1.5 bg-black/50 text-white/60 text-[1.5cqw] px-1.5 py-0.5 rounded font-medium select-none pointer-events-none">
                    arraste
                  </div>
                )}
              </>
            ) : (
              <div
                className={`absolute inset-0 flex items-center justify-center select-none ${
                  darkMode ? "bg-white/5 text-white/20" : "bg-black/5 text-black/20"
                }`}
                style={{ fontSize: "2.5cqw" }}
              >
                sem imagem
              </div>
            )}
          </div>
        )}

        {/* Subheadline — hidden on bullets variant */}
        {slide.variant !== "bullets" && (
          <p
            className="font-semibold tracking-[-0.02em] leading-[1.3] overflow-hidden"
            style={{
              fontSize: subSize,
              display: "-webkit-box",
              WebkitLineClamp: 4,
              WebkitBoxOrient: "vertical",
            }}
          >
            {slide.subheadline}
          </p>
        )}

        {/* CTA badge */}
        {slide.variant === "closing" && (
          <div
            className={`mt-[3%] self-start rounded-full border px-3 py-1 font-medium ${
              darkMode ? "border-[#f2f2de]/35 text-[#f2f2de]/80" : "border-[#111126]/30"
            }`}
            style={{ fontSize: "2cqw" }}
          >
            {slide.ctaText ?? DEFAULT_CTA}
          </div>
        )}

        {/* Footer — pushed to bottom */}
        <div className="mt-auto pt-[4%]">
          {!compact ? (
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="grid h-7 w-7 place-items-center rounded-full bg-white/60 text-black"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <SlideDots activeIndex={activeIndex} lightMode={slide.lightMode} />
              <button
                type="button"
                className="grid h-7 w-7 place-items-center rounded-full bg-white/60 text-black"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <SlideDots activeIndex={activeIndex} lightMode={slide.lightMode} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── MiniSlide: CSS-scaled thumbnail (no API calls) ──────────────────────────

function MiniSlide({
  slide,
  index,
  isActive,
  onClick,
}: {
  slide: Slide;
  index: number;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full overflow-hidden rounded-lg border transition-all ${
        isActive
          ? "border-white ring-1 ring-white/40"
          : "border-white/15 hover:border-white/40"
      }`}
    >
      <SlidePreview slide={slide} activeIndex={index} compact />
      <div
        className={`flex items-center justify-between px-2 py-[5px] text-[9px] font-semibold ${
          isActive ? "bg-white text-black" : "bg-neutral-900 text-white/55"
        }`}
      >
        <span>{String(index + 1).padStart(2, "0")}</span>
        <span className="uppercase tracking-widest opacity-60">{VARIANT_LABELS[slide.variant]}</span>
      </div>
    </button>
  );
}

// ─── Home ────────────────────────────────────────────────────────────────────

// Comprime imagem base64 para JPEG menor, evitando HTTP 413 no export
async function compressImage(dataUrl: string, maxDim = 1200, quality = 0.82): Promise<string> {
  if (!dataUrl?.startsWith("data:image")) return dataUrl;
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const scale = img.width > maxDim || img.height > maxDim
        ? Math.min(maxDim / img.width, maxDim / img.height)
        : 1;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(dataUrl); return; }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", quality));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function Home() {
  const [slides, setSlides] = useState<Slide[]>(DEFAULT_SLIDES);
  const [activeSlide, setActiveSlide] = useState("01");
  const [theme, setTheme] = useState("");
  const [tone, setTone] = useState<CopyTone>("elegante");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingImagePrompts, setIsGeneratingImagePrompts] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [genImages, setGenImages] = useState<GeneratedImage[]>([]);
  const [isGeneratingImages, setIsGeneratingImages] = useState(false);
  const [showImageLibrary, setShowImageLibrary] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  const currentSlide = useMemo(
    () => slides.find((s) => s.id === activeSlide) ?? slides[0],
    [slides, activeSlide],
  );
  const currentIndex = useMemo(
    () => slides.findIndex((s) => s.id === activeSlide),
    [slides, activeSlide],
  );

  const updateSlide = useCallback(
    (id: string, field: keyof Slide, value: unknown) => {
      setSlides((prev) =>
        prev.map((s) => (s.id === id ? { ...s, [field]: value } : s)),
      );
    },
    [],
  );

  const handleBatchUpload = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const fileArr = Array.from(files).slice(0, 7);
      fileArr.forEach((file, i) => {
        const reader = new FileReader();
        reader.onload = (ev) => {
          const result = ev.target?.result as string;
          setSlides((prev) =>
            prev.map((s, idx) => (idx === i ? { ...s, backgroundImage: result } : s)),
          );
        };
        reader.readAsDataURL(file);
      });
    },
    [],
  );

  const handleSingleUpload = useCallback(
    (id: string, files: FileList | null) => {
      if (!files?.[0]) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        updateSlide(id, "backgroundImage", ev.target?.result as string);
      };
      reader.readAsDataURL(files[0]);
    },
    [updateSlide],
  );

  const randomizeImages = useCallback(() => {
    const images = slides.map((s) => s.backgroundImage);
    const shuffled = shuffle(images);
    setSlides((prev) => prev.map((s, i) => ({ ...s, backgroundImage: shuffled[i] })));
  }, [slides]);

  const generateCopyWithAi = useCallback(async () => {
    if (!theme.trim()) {
      setError("Digite o tema do carrossel antes de gerar.");
      return;
    }
    setError(null);
    setIsGenerating(true);
    try {
      const res = await fetch("/api/copy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme, tone }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { slides: Slide[] };
      if (data?.slides?.length) {
        setSlides((prev) =>
          prev.map((s, i) => {
            const generated = data.slides[i];
            if (!generated) return s;
            const hasBullets = Array.isArray(generated.bullets) && generated.bullets.length > 0;
            return {
              ...s,
              headline: generated.headline ?? s.headline,
              subheadline: generated.subheadline ?? s.subheadline,
              tag: generated.tag ?? s.tag,
              ...(hasBullets ? { bullets: generated.bullets, variant: "bullets" as const } : {}),
            };
          }),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao gerar copy.");
    } finally {
      setIsGenerating(false);
    }
  }, [theme, tone]);

  const generateImagePrompts = useCallback(async () => {
    if (!theme.trim()) {
      setError("Digite o tema antes de gerar prompts.");
      return;
    }
    setError(null);
    setIsGeneratingImagePrompts(true);
    try {
      const res = await fetch("/api/image-prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme, tone, slides }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { prompts: { id: string; prompt: string }[] };
      if (data?.prompts?.length) {
        setSlides((prev) =>
          prev.map((s) => {
            const found = data.prompts.find((p) => p.id === s.id);
            return found ? { ...s, imagePrompt: found.prompt } : s;
          }),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao gerar prompts.");
    } finally {
      setIsGeneratingImagePrompts(false);
    }
  }, [theme, tone, slides]);

  // ── Gerar imagens com DALL-E 3 ─────────────────────────────────────────
  const generateImages = useCallback(async () => {
    // Exclui slides que não usam imagem de fundo; usa headline como fallback de prompt
    const targets = slides
      .filter((s) => s.variant !== "bullets")
      .map((s) => ({
        ...s,
        imagePrompt:
          s.imagePrompt && s.imagePrompt.trim().length > 4
            ? s.imagePrompt
            : `${s.headline}${s.subheadline ? `. ${s.subheadline}` : ""}`,
      }));

    if (targets.length === 0) {
      setError("Nenhum slide com imagem encontrado.");
      return;
    }
    setIsGeneratingImages(true);
    setShowImageLibrary(true);
    setError(null);
    setGenImages(targets.map((s) => ({ slideId: s.id, prompt: s.imagePrompt!, dataUrl: null })));

    for (const slide of targets) {
      try {
        const res = await fetch("/api/generate-images", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: slide.imagePrompt }),
        });
        const data = (await res.json()) as { dataUrl?: string; error?: string; model?: string };
        setGenImages((prev) =>
          prev.map((img) =>
            img.slideId === slide.id
              ? { ...img, dataUrl: data.dataUrl ?? null, error: data.error, model: data.model }
              : img,
          ),
        );
      } catch {
        setGenImages((prev) =>
          prev.map((img) =>
            img.slideId === slide.id ? { ...img, error: "Falha na geração." } : img,
          ),
        );
      }
    }
    setIsGeneratingImages(false);
  }, [slides]);

  const exportZip = useCallback(async () => {
    setError(null);
    setIsExporting(true);
    try {
      // Compress images before sending to avoid HTTP 413 (Vercel 4.5 MB limit)
      const compressedSlides = await Promise.all(
        slides.map(async (s) => ({
          ...s,
          backgroundImage: s.backgroundImage
            ? await compressImage(s.backgroundImage)
            : undefined,
        })),
      );
      const res = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slides: compressedSlides }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "carrossel.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao exportar.");
    } finally {
      setIsExporting(false);
    }
  }, [slides]);

  // ── Drag & drop single image ───────────────────────────────────────────────
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleSingleUpload(currentSlide.id, e.dataTransfer.files);
    },
    [currentSlide.id, handleSingleUpload],
  );

  const label = "block text-[10px] uppercase tracking-[0.18em] text-white/50 mb-1.5";
  const inputCls =
    "h-10 border-white/15 bg-white/[0.04] text-white placeholder:text-white/25 focus-visible:ring-white focus-visible:ring-1 text-sm";

  return (
    <main className="h-screen flex flex-col bg-[#0a0a0a] text-white overflow-hidden">
      {/* ── TOP BAR ─────────────────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 border-b border-white/10 bg-black px-5 py-2.5 shrink-0 flex-wrap gap-y-2">
        <div className="flex items-center gap-2 shrink-0 mr-1">
          <div className="rounded border border-white/20 p-1.5">
            <LayoutDashboard className="h-4 w-4" />
          </div>
          <span className="text-[13px] font-black uppercase tracking-[-0.02em] whitespace-nowrap">
            Gerador de Carrossel
          </span>
        </div>

        <Input
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generateCopyWithAi()}
          placeholder="Tema do carrossel..."
          className="flex-1 min-w-[180px] h-9 border-white/15 bg-white/[0.04] text-white text-sm placeholder:text-white/30 focus-visible:ring-1 focus-visible:ring-white"
        />

        {/* Tone selector */}
        <div className="flex gap-1 shrink-0">
          {(["agressivo", "elegante", "educacional"] as CopyTone[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTone(t)}
              className={`h-9 px-3 rounded-md border text-[10px] font-semibold uppercase tracking-[0.1em] transition ${
                tone === t
                  ? "bg-white text-black border-white"
                  : "border-white/20 text-white/60 hover:border-white/40"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 shrink-0">
          <label className="flex h-9 cursor-pointer items-center gap-1.5 rounded-md border border-white/20 px-3 text-[11px] font-medium text-white/70 transition hover:border-white/40 hover:text-white">
            <ImageIcon className="h-3.5 w-3.5" />
            Upload lote
            <input
              type="file"
              multiple
              accept="image/*"
              className="hidden"
              onChange={(e) => handleBatchUpload(e.target.files)}
            />
          </label>

          <Button
            onClick={generateCopyWithAi}
            disabled={isGenerating}
            className="h-9 bg-white text-black hover:bg-white/90 text-[11px] font-semibold px-3"
          >
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            {isGenerating ? "Gerando..." : "Copy IA"}
          </Button>

          <Button
            onClick={generateImagePrompts}
            disabled={isGeneratingImagePrompts}
            className="h-9 border border-[#003cbb]/60 bg-[#003cbb]/10 text-[#6b9fff] hover:bg-[#003cbb]/20 text-[11px] px-3"
          >
            <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
            {isGeneratingImagePrompts ? "..." : "Prompts IA"}
          </Button>

          <Button
            onClick={generateImages}
            disabled={isGeneratingImages}
            title="Gerar imagens com Flux 1.1 Pro (ou DALL-E 3)"
            className="h-9 border border-[#003cbb]/60 bg-[#003cbb]/10 text-[#6b9fff] hover:bg-[#003cbb]/20 text-[11px] px-3"
          >
            <ImageIcon className="mr-1.5 h-3.5 w-3.5" />
            {isGeneratingImages ? "Gerando..." : "Gerar Imagens"}
          </Button>

          <Button
            onClick={randomizeImages}
            title="Randomizar imagens"
            className="h-9 w-9 border border-white/20 bg-transparent text-white hover:bg-white hover:text-black p-0"
          >
            <Shuffle className="h-3.5 w-3.5" />
          </Button>

          <Button
            onClick={exportZip}
            disabled={isExporting}
            className="h-9 border border-white/20 bg-transparent text-white hover:bg-white hover:text-black text-[11px] px-3"
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {isExporting ? "..." : "ZIP"}
          </Button>
        </div>
      </header>

      {error && (
        <div className="shrink-0 bg-red-500/10 border-b border-red-500/20 px-5 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* ── MAIN AREA ────────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── EDITOR PANEL ──────────────────────────────────────────────────── */}
        <aside className="w-[340px] shrink-0 border-r border-white/10 overflow-y-auto bg-black">
          {/* Slide selector tabs */}
          <div className="flex gap-1 flex-wrap p-3 border-b border-white/10">
            {slides.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setActiveSlide(s.id)}
                className={`h-7 w-10 rounded-md text-[11px] font-semibold border transition ${
                  activeSlide === s.id
                    ? "bg-white text-black border-white"
                    : "border-white/20 text-white/60 hover:border-white/40"
                }`}
              >
                {s.id}
              </button>
            ))}
      </div>

          {/* Fields for active slide */}
          <div className="p-4 space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className={label} style={{ marginBottom: 0 }}>Headline</label>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-white/40">{currentSlide.headlineSize ?? 100}%</span>
                  <input
                    type="range"
                    min={50}
                    max={180}
                    step={5}
                    value={currentSlide.headlineSize ?? 100}
                    onChange={(e) => updateSlide(currentSlide.id, "headlineSize", Number(e.target.value))}
                    className="w-20 accent-white"
                  />
                </div>
              </div>
              <Input
                value={currentSlide.headline}
                onChange={(e) => updateSlide(currentSlide.id, "headline", e.target.value)}
                className={inputCls}
                placeholder="Título principal"
        />
      </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className={label} style={{ marginBottom: 0 }}>Subheadline</label>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-white/40">{currentSlide.subheadlineSize ?? 100}%</span>
                  <input
                    type="range"
                    min={50}
                    max={180}
                    step={5}
                    value={currentSlide.subheadlineSize ?? 100}
                    onChange={(e) => updateSlide(currentSlide.id, "subheadlineSize", Number(e.target.value))}
                    className="w-20 accent-white"
                  />
                </div>
              </div>
              {currentSlide.variant !== "bullets" && (
                <Input
                  value={currentSlide.subheadline}
                  onChange={(e) => updateSlide(currentSlide.id, "subheadline", e.target.value)}
                  className={inputCls}
                  placeholder="Texto de apoio"
                />
              )}
            </div>

            {/* CTA selector — only for closing variant */}
            {currentSlide.variant === "closing" && (
              <div>
                <label className={label}>CTA do Slide Final</label>
                <div className="flex flex-col gap-1.5">
                  {CTA_PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => updateSlide(currentSlide.id, "ctaText", preset)}
                      className={`w-full rounded-md border px-3 py-2 text-left text-[10px] font-medium leading-tight transition ${
                        (currentSlide.ctaText ?? DEFAULT_CTA) === preset
                          ? "border-[#003cbb]/80 bg-[#003cbb]/15 text-[#6b9fff]"
                          : "border-white/12 bg-white/[0.03] text-white/50 hover:border-white/25 hover:text-white/70"
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                  <input
                    type="text"
                    value={
                      CTA_PRESETS.includes(currentSlide.ctaText ?? DEFAULT_CTA)
                        ? ""
                        : (currentSlide.ctaText ?? "")
                    }
                    onChange={(e) =>
                      updateSlide(currentSlide.id, "ctaText", e.target.value)
                    }
                    className={`${inputCls} mt-1`}
                    placeholder="Ou escreva um CTA personalizado…"
                  />
                </div>
              </div>
            )}

            {/* Bullet points editor — only for bullets variant */}
            {currentSlide.variant === "bullets" && (
              <div>
                <label className={label}>Bullet Points</label>
                <textarea
                  value={(currentSlide.bullets ?? []).join("\n")}
                  onChange={(e) =>
                    updateSlide(
                      currentSlide.id,
                      "bullets",
                      e.target.value.split("\n").filter((l) => l.trim().length > 0),
                    )
                  }
                  rows={5}
                  className="w-full rounded-md border border-white/15 bg-white/[0.04] px-3 py-2 text-[11px] text-white/80 leading-relaxed placeholder:text-white/25 focus:outline-none focus:ring-1 focus:ring-white resize-none"
                  placeholder={"Primeiro ponto aqui\nSegundo ponto aqui\nTerceiro ponto aqui\nQuarto ponto (opcional)"}
                />
                <p className="mt-1 text-[10px] text-white/30">Máx. 4 bullets · cada linha = 1 bullet</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={label}>Tag</label>
                <Input
                  value={currentSlide.tag}
                  onChange={(e) => updateSlide(currentSlide.id, "tag", e.target.value)}
                  className={inputCls}
                />
              </div>
              <div>
                <label className={label}>Modo</label>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => updateSlide(currentSlide.id, "lightMode", false)}
                    className={`flex-1 h-10 rounded-md border text-[10px] font-semibold transition ${
                      !currentSlide.lightMode
                        ? "bg-white/10 border-white/60 text-white"
                        : "border-white/15 text-white/40"
                    }`}
                  >
                    Dark
                  </button>
                  <button
                    type="button"
                    onClick={() => updateSlide(currentSlide.id, "lightMode", true)}
                    className={`flex-1 h-10 rounded-md border text-[10px] font-semibold transition ${
                      currentSlide.lightMode
                        ? "bg-neutral-100 border-neutral-200 text-black"
                        : "border-white/15 text-white/40"
                    }`}
                  >
                    Light
                  </button>
                </div>
              </div>
            </div>

            {/* Variant */}
            <div>
              <label className={label}>Layout</label>
              <div className="grid grid-cols-2 gap-1.5">
                {(Object.keys(VARIANT_LABELS) as SlideVariant[]).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => updateSlide(currentSlide.id, "variant", v)}
                    className={`h-9 rounded-md border text-[10px] font-semibold transition ${
                      currentSlide.variant === v
                        ? "bg-white text-black border-white"
                        : "border-white/15 text-white/55 hover:border-white/35"
                    }`}
                  >
                    {VARIANT_LABELS[v]}
                  </button>
                ))}
              </div>
            </div>

            {/* Single image upload / drag & drop */}
            <div>
              <label className={label}>Imagem do slide</label>
              <div
                ref={dropRef}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="relative flex flex-col items-center justify-center rounded-xl border border-dashed border-white/20 bg-white/[0.03] p-4 text-center transition hover:border-white/35 cursor-pointer"
                onClick={() => {
                  const inp = document.getElementById(`img-upload-${currentSlide.id}`);
                  inp?.click();
                }}
              >
                {currentSlide.backgroundImage ? (
                  <div
                    className="w-full aspect-[4/5] rounded-lg bg-cover bg-center"
                    style={{ backgroundImage: `url(${currentSlide.backgroundImage})` }}
                  />
                ) : (
                  <>
                    <ImageIcon className="h-6 w-6 mb-2 text-white/30" />
                    <p className="text-[11px] text-white/40">
                      Clique ou arraste uma imagem
                    </p>
                  </>
                )}
                <input
                  id={`img-upload-${currentSlide.id}`}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => handleSingleUpload(currentSlide.id, e.target.files)}
                />
              </div>
              {currentSlide.backgroundImage && (
                <div className="mt-2 flex gap-2 items-center">
                  <label className="flex items-center gap-2 text-[11px] text-white/60 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!currentSlide.grayscale}
                      onChange={(e) =>
                        updateSlide(currentSlide.id, "grayscale", e.target.checked)
                      }
                      className="accent-white"
                    />
                    Grayscale
                  </label>
                  <button
                    type="button"
                    onClick={() => updateSlide(currentSlide.id, "backgroundImage", undefined)}
                    className="ml-auto text-[10px] text-white/35 hover:text-red-400"
                  >
                    Remover imagem
                  </button>
                </div>
              )}
            </div>

            {/* Image prompt */}
            {currentSlide.imagePrompt && (
              <div>
                <label className={label}>Prompt para DALL-E / Nano Banana</label>
                <textarea
                  value={currentSlide.imagePrompt}
                  onChange={(e) =>
                    updateSlide(currentSlide.id, "imagePrompt", e.target.value)
                  }
                  rows={4}
                  className="w-full rounded-md border border-white/15 bg-white/[0.04] px-3 py-2 text-[11px] text-white/80 leading-relaxed placeholder:text-white/25 focus:outline-none focus:ring-1 focus:ring-white resize-none"
                />
              </div>
            )}
          </div>

          {/* ── Biblioteca de Imagens Geradas ───────────────────────────── */}
          {showImageLibrary && genImages.length > 0 && (
            <div className="border-t border-white/10 pt-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
                  Imagens Geradas
            </span>
                <button
                  type="button"
                  onClick={() => setShowImageLibrary(false)}
                  className="text-[10px] text-white/30 hover:text-white/60"
                >
                  Fechar
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {genImages.map((img) => {
                  const slideLabel = slides.find((s) => s.id === img.slideId)?.id;
                  return (
                    <div key={img.slideId} className="relative group">
                      <div className="aspect-square rounded-lg overflow-hidden bg-white/5 border border-white/10 flex items-center justify-center">
                        {img.dataUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={img.dataUrl}
                            alt={`Slide ${slideLabel}`}
                            className="w-full h-full object-cover"
                          />
                        ) : img.error ? (
                          <span className="text-[9px] text-red-400 text-center px-2">{img.error}</span>
                        ) : (
                          <div className="flex flex-col items-center gap-1">
                            <div className="w-4 h-4 border-2 border-[#003cbb]/50 border-t-[#003cbb] rounded-full animate-spin" />
                            <span className="text-[8px] text-white/30">gerando…</span>
                          </div>
                        )}
                      </div>
                      {/* Slot label */}
                      <div className="absolute top-1 left-1 bg-black/60 text-[8px] text-white/70 rounded px-1 py-0.5 font-mono">
                        {slideLabel}
                      </div>
                      {/* Model badge */}
                      {img.model && (
                        <div className={`absolute top-1 right-1 text-[7px] rounded px-1 py-0.5 font-bold ${img.model === "flux-1.1-pro" ? "bg-[#003cbb]/80 text-white" : "bg-black/60 text-white/60"}`}>
                          {img.model === "flux-1.1-pro" ? "FLUX" : "DALL-E"}
                        </div>
                      )}
                      {/* Assign buttons */}
                      {img.dataUrl && (
                        <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex flex-col items-center justify-center gap-1.5 p-2">
                          <button
                            type="button"
                            onClick={() => {
                              updateSlide(img.slideId, "backgroundImage", img.dataUrl!);
                            }}
                            className="w-full text-[9px] bg-[#003cbb] text-white rounded py-1 font-semibold"
                          >
                            → Slide {slideLabel}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              updateSlide(activeSlide, "backgroundImage", img.dataUrl!);
                            }}
                            className="w-full text-[9px] bg-white/20 text-white rounded py-1 font-semibold"
                          >
                            → Slide atual
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {isGeneratingImages && (
                <p className="text-[10px] text-white/30 text-center mt-3 animate-pulse">
                  Gerando imagens com DALL-E 3…
                </p>
              )}
            </div>
          )}
        </aside>

        {/* ── CANVAS ────────────────────────────────────────────────────────── */}
        <section className="flex-1 overflow-hidden bg-neutral-950 p-4 flex gap-4">
          {/* Mini grid — 3 cols, 7 slides */}
          <div className="flex-1 overflow-y-auto">
            <div className="grid grid-cols-3 gap-3">
              {slides.map((slide, index) => (
                <MiniSlide
                  key={slide.id}
                  slide={slide}
                  index={index}
                  isActive={slide.id === activeSlide}
                  onClick={() => setActiveSlide(slide.id)}
                />
              ))}
            </div>
          </div>

          {/* Active slide preview — fixed width */}
          <div className="w-[260px] shrink-0 flex flex-col gap-2">
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
              Preview — Slide {currentSlide.id}
            </div>
            <div className="overflow-hidden rounded-xl border border-white/15">
              <SlidePreview
                slide={currentSlide}
                activeIndex={currentIndex}
                onPositionChange={(x, y) => {
                  updateSlide(currentSlide.id, "imagePosX", x);
                  updateSlide(currentSlide.id, "imagePosY", y);
                }}
              />
            </div>
            {/* Navegação prev/next */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  const idx = slides.findIndex((s) => s.id === activeSlide);
                  if (idx > 0) setActiveSlide(slides[idx - 1].id);
                }}
                className="flex-1 h-8 rounded-md border border-white/15 text-white/60 text-xs hover:border-white/40 transition"
              >
                ← anterior
              </button>
              <button
                type="button"
                onClick={() => {
                  const idx = slides.findIndex((s) => s.id === activeSlide);
                  if (idx < slides.length - 1) setActiveSlide(slides[idx + 1].id);
                }}
                className="flex-1 h-8 rounded-md border border-white/15 text-white/60 text-xs hover:border-white/40 transition"
              >
                próximo →
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
