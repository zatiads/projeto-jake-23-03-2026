import path from "node:path";
import { readFile } from "node:fs/promises";
import React from "react";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

export const SLIDE_WIDTH = 1080;
export const SLIDE_HEIGHT = 1350;
const CONTENT_PADDING = 80;

export type RenderSlideInput = {
  id: string;
  headline: string;
  subheadline: string;
  tag: string;
  variant?: "cover" | "split" | "statement" | "closing" | "bullets";
  backgroundImage?: string;
  grayscale?: boolean;
  overlayOpacity?: number;
  lightMode?: boolean;
  headlineSize?: number;
  subheadlineSize?: number;
  bullets?: string[];
  ctaText?: string;
  imagePosX?: number;
  imagePosY?: number;
};

let interFontsPromise: Promise<{ regular: Buffer; semibold: Buffer; black: Buffer }> | null = null;
const imageDataUrlCache = new Map<string, string | null>();
const renderPngCache = new Map<string, Buffer>();
const MAX_CACHE_ITEMS = 60;

function touchCacheEntry<T>(cache: Map<string, T>, key: string, value: T) {
  if (cache.has(key)) {
    cache.delete(key);
  }
  cache.set(key, value);
  if (cache.size > MAX_CACHE_ITEMS) {
    const firstKey = cache.keys().next().value;
    if (firstKey) {
      cache.delete(firstKey);
    }
  }
}

function getRenderKey(input: RenderSlideInput) {
  return JSON.stringify({
    id: input.id,
    headline: input.headline,
    subheadline: input.subheadline,
    tag: input.tag,
    variant: input.variant ?? "split",
    backgroundImage: input.backgroundImage ?? "",
    grayscale: Boolean(input.grayscale),
    overlayOpacity: Math.min(Math.max(input.overlayOpacity ?? 0.45, 0), 0.95),
    lightMode: Boolean(input.lightMode),
    headlineSize: input.headlineSize ?? 100,
    subheadlineSize: input.subheadlineSize ?? 100,
  });
}

async function loadInterFonts() {
  if (!interFontsPromise) {
    interFontsPromise = (async () => {
      // Fonts are in public/fonts/ — always included in the Vercel deployment bundle
      const base = path.join(process.cwd(), "public", "fonts");
      const [regular, semibold, black] = await Promise.all([
        readFile(path.join(base, "inter-400.woff")),
        readFile(path.join(base, "inter-700.woff")),
        readFile(path.join(base, "inter-900.woff")),
      ]);
      return { regular, semibold, black };
    })();
  }
  return interFontsPromise;
}

async function toDataUrl(imageUrl: string) {
  if (!imageUrl) {
    return null;
  }

  if (imageUrl.startsWith("data:image")) {
    return imageUrl;
  }

  if (!imageUrl.startsWith("http://") && !imageUrl.startsWith("https://")) {
    return null;
  }

  if (imageDataUrlCache.has(imageUrl)) {
    return imageDataUrlCache.get(imageUrl) ?? null;
  }

  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      touchCacheEntry(imageDataUrlCache, imageUrl, null);
      return null;
    }

    const contentType = response.headers.get("content-type") ?? "image/jpeg";
    const buffer = Buffer.from(await response.arrayBuffer());
    const dataUrl = `data:${contentType};base64,${buffer.toString("base64")}`;
    touchCacheEntry(imageDataUrlCache, imageUrl, dataUrl);
    return dataUrl;
  } catch {
    touchCacheEntry(imageDataUrlCache, imageUrl, null);
    return null;
  }
}

export async function renderSlideToPng(input: RenderSlideInput) {
  const renderKey = getRenderKey(input);
  if (renderPngCache.has(renderKey)) {
    const cached = renderPngCache.get(renderKey);
    if (cached) {
      return cached;
    }
  }

  const fonts = await loadInterFonts();
  const imageDataUrl = await toDataUrl(input.backgroundImage ?? "");
  const overlayOpacity = Math.min(Math.max(input.overlayOpacity ?? 0.45, 0), 0.95);
  const variant = input.variant ?? "split";
  const hlMultiplier = (input.headlineSize ?? 100) / 100;
  const subMultiplier = (input.subheadlineSize ?? 100) / 100;
  const darkMode = !input.lightMode;
  const bgColor = darkMode ? "#02021A" : "#F5F5F7";
  const titleColor = darkMode ? "#F2F2DE" : "#121225";
  const supportColor = darkMode ? "rgba(242,242,222,0.92)" : "rgba(18,18,37,0.95)";
  const metaColor = darkMode ? "rgba(242,242,222,0.9)" : "rgba(18,18,37,0.9)";
  const useLightOverlayText = darkMode;

  const svg = await satori(
    <div
      style={{
        width: `${SLIDE_WIDTH}px`,
        height: `${SLIDE_HEIGHT}px`,
        display: "flex",
        position: "relative",
        overflow: "hidden",
        backgroundColor: bgColor,
        color: titleColor,
        fontFamily: "Inter",
      }}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          gap: "26px",
          padding: `${CONTENT_PADDING}px`,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 20,
            fontWeight: 500,
            color: metaColor,
          }}
        >
          <div>@brunozatii</div>
          <div>Fevereiro 2026 ®</div>
        </div>

        {/* Accent lines — blue brand color */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 80, height: 3, borderRadius: 99, backgroundColor: "#003CBB" }} />
          <div style={{ flex: 1, height: 3, borderRadius: 99, backgroundColor: darkMode ? "rgba(0,60,187,0.25)" : "rgba(0,60,187,0.18)" }} />
        </div>

        {/* Headline — line-clamp 3 */}
        {variant === "cover" ? (
          <div
            style={{
              fontSize: Math.round(88 * hlMultiplier),
              fontWeight: 900,
              letterSpacing: "-0.05em",
              lineHeight: 1.03,
              color: titleColor,
              maxWidth: "940px",
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {input.headline}
          </div>
        ) : (
          <div
            style={{
              fontSize: Math.round(74 * hlMultiplier),
              fontWeight: 900,
              letterSpacing: "-0.05em",
              lineHeight: 1.08,
              color: titleColor,
              maxWidth: "920px",
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {input.headline}
          </div>
        )}

        {/* Content block — adapts by variant */}
        {variant === "bullets" ? (
          // ── Numbered editorial bullets (vertically centred) ────────────────
          <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            {(input.bullets ?? []).slice(0, 4).map((bullet, i) => (
              <div key={i}>
                {i > 0 && (
                  <div
                    style={{
                      width: "100%",
                      height: 1,
                      backgroundColor: darkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                      margin: "30px 0",
                    }}
                  />
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
                  <div
                    style={{
                      flexShrink: 0,
                      fontSize: Math.round(46 * subMultiplier),
                      fontWeight: 900,
                      color: "#003CBB",
                      minWidth: 72,
                      lineHeight: 1,
                      letterSpacing: "-0.04em",
                    }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      fontSize: Math.round(52 * subMultiplier),
                      fontWeight: 700,
                      lineHeight: 1.25,
                      letterSpacing: "-0.03em",
                      color: supportColor,
                    }}
                  >
                    {bullet}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : variant === "statement" ? (
          <div
            style={{
              width: "100%",
              height: 4,
              borderRadius: 99,
              backgroundColor: darkMode ? "rgba(0,60,187,0.25)" : "rgba(0,60,187,0.18)",
            }}
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: 420, // fixed height, consistent across all variants
              borderRadius: "16px",
              overflow: "hidden",
              position: "relative",
              backgroundColor: darkMode ? "#121229" : "#E9E9EE",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {imageDataUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageDataUrl}
                alt="Slide visual"
                width={SLIDE_WIDTH}
                height={SLIDE_HEIGHT}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  objectPosition: `${input.imagePosX ?? 50}% ${input.imagePosY ?? 50}%`,
                  filter: input.grayscale ? "grayscale(100%)" : "none",
                }}
              />
            ) : (
              <div
                style={{
                  fontSize: 30,
                  color: darkMode ? "rgba(242,242,222,0.5)" : "rgba(18,18,37,0.45)",
                }}
              >
                Sem imagem
              </div>
            )}
            {imageDataUrl && useLightOverlayText ? (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backgroundColor: `rgba(0,0,0,${overlayOpacity})`,
                }}
              />
            ) : null}
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "18px",
          }}
        >
          {/* CTA badge — closing variant */}
          {variant === "closing" && (input.ctaText ?? "Siga @brunozatii para mais conteúdos") && (
            <div
              style={{
                display: "inline-flex",
                alignSelf: "flex-start",
                border: `1px solid ${darkMode ? "rgba(242,242,222,0.35)" : "rgba(17,17,38,0.3)"}`,
                borderRadius: 9999,
                padding: "10px 28px",
                fontSize: 38,
                fontWeight: 500,
                color: darkMode ? "rgba(242,242,222,0.82)" : "rgba(17,17,38,0.75)",
                marginBottom: 8,
              }}
            >
              {input.ctaText ?? "Siga @brunozatii para mais conteúdos"}
            </div>
          )}

          {/* Subheadline — hidden for bullets variant */}
          {variant !== "bullets" && (
            <div
              style={{
                fontSize: Math.round(50 * subMultiplier),
                fontWeight: 700,
                lineHeight: 1.25,
                letterSpacing: "-0.03em",
                color: supportColor,
                maxWidth: "920px",
                display: "-webkit-box",
                WebkitLineClamp: 4,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {input.subheadline}
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div
              style={{
                display: "flex",
                gap: "10px",
              }}
            >
              {Array.from({ length: 10 }).map((_, index) => {
                const active = index + 1 === Number(input.id);
                return (
                  <div
                    key={`${input.id}-${index}`}
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "9999px",
                      backgroundColor: active
                        ? darkMode
                          ? "#F2F2DE"
                          : "#121225"
                        : darkMode
                          ? "rgba(242,242,222,0.25)"
                          : "rgba(18,18,37,0.2)",
                    }}
                  />
                );
              })}
            </div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 600,
                letterSpacing: "0.12em",
                color: darkMode ? "rgba(242,242,222,0.65)" : "rgba(18,18,37,0.58)",
                textAlign: "right",
              }}
            >
              {input.id}/07
            </div>
          </div>
        </div>
      </div>
    </div>,
    {
      width: SLIDE_WIDTH,
      height: SLIDE_HEIGHT,
      fonts: [
        {
          name: "Inter",
          data: fonts.regular,
          weight: 400,
          style: "normal",
        },
        {
          name: "Inter",
          data: fonts.semibold,
          weight: 700,
          style: "normal",
        },
        {
          name: "Inter",
          data: fonts.black,
          weight: 900,
          style: "normal",
        },
      ],
    }
  );

  const png = new Resvg(svg).render().asPng();
  const buffer = Buffer.from(png);
  touchCacheEntry(renderPngCache, renderKey, buffer);
  return buffer;
}
