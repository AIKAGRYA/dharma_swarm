import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PublicHeroCta {
  label: string;
  href: string;
  variant?: "primary" | "secondary";
  external?: boolean;
}

export interface PublicHeroProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  image?: string;
  imageAlt?: string;
  ctas?: PublicHeroCta[];
  className?: string;
}

export function PublicHero({ eyebrow, title, subtitle, image, imageAlt, ctas, className }: PublicHeroProps) {
  const hasImage = Boolean(image);

  return (
    <section
      className={cn(
        "relative overflow-hidden",
        hasImage ? "min-h-[70svh] bg-[#11131a] text-white" : "bg-[#181a20] text-white",
        className,
      )}
    >
      {hasImage && image && (
        <>
          <Image
            src={image}
            alt={imageAlt ?? ""}
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(8,9,13,0.92)_0%,rgba(8,9,13,0.72)_40%,rgba(8,9,13,0.2)_80%)]" />
        </>
      )}

      <div className="relative z-10 mx-auto flex min-h-[70svh] max-w-7xl flex-col justify-center px-5 pb-16 pt-32 sm:px-8">
        <div className="max-w-3xl">
          {eyebrow && (
            <p className="mb-5 inline-flex items-center gap-2 rounded-lg border border-[#d4a855]/40 bg-[#d4a855]/10 px-3 py-2 text-xs font-semibold uppercase text-[#f5d38b]">
              <Sparkles size={14} aria-hidden="true" />
              {eyebrow}
            </p>
          )}
          <h1 className="font-heading text-5xl font-semibold leading-[1.02] sm:text-7xl lg:text-8xl">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-6 max-w-2xl text-xl font-medium leading-relaxed text-white/80 sm:text-2xl">
              {subtitle}
            </p>
          )}
          {ctas && ctas.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-3">
              {ctas.map((cta, index) => {
                const isPrimary = cta.variant === "primary" || index === 0;
                const classes = cn(
                  "inline-flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-semibold transition",
                  isPrimary
                    ? "bg-[#4fd1d9] text-[#071013] hover:bg-[#7be8ee]"
                    : "border border-white/20 bg-white/[0.08] text-white hover:bg-white/[0.14]",
                );
                const content = (
                  <>
                    {cta.label}
                    <ArrowRight size={17} />
                  </>
                );
                return cta.external || cta.href.startsWith("http") ? (
                  <a key={cta.href} href={cta.href} className={classes}>
                    {content}
                  </a>
                ) : (
                  <Link key={cta.href} href={cta.href} className={classes}>
                    {content}
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
