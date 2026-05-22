"use client";

/**
 * ZoneLanding — shared landing page for the 7 verb-shaped zones.
 *
 * One template, parameterized by zone id. Renders the zone header
 * (label + verb + description) and a grid of route cards. Each card
 * is a hairline Nihonga rectangle with mono ALLCAPS label + Inter
 * description + arrow CTA.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { colors } from "@/lib/theme";
import { Numeral } from "@/components/primitives/Numeral";
import { ZONES, type ZoneId } from "@/components/dashboard/ZoneTabs";

interface ZoneLandingProps {
  zoneId: ZoneId;
}

export function ZoneLanding({ zoneId }: ZoneLandingProps) {
  const zone = ZONES.find((z) => z.id === zoneId);
  if (!zone) {
    return (
      <div
        className="font-mono text-xs uppercase"
        style={{ color: colors.sumi[600], letterSpacing: "0.14em", padding: 24 }}
      >
        Unknown zone: {zoneId}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Zone header */}
      <header
        className="flex flex-col gap-2"
        style={{
          borderLeft: `2px solid ${colors.aozora}`,
          paddingLeft: 16,
        }}
      >
        <div className="flex items-baseline gap-4">
          <h1
            className="font-mono text-3xl uppercase tabular-nums"
            style={{
              color: colors.aozora,
              letterSpacing: "0.10em",
              fontWeight: 500,
            }}
          >
            {zone.label}
          </h1>
          <span
            className="font-mono text-sm uppercase"
            style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
          >
            {zone.verb}
          </span>
          <div className="flex-1" />
          <Numeral
            value={zone.routes.length}
            tone="rest"
            size="md"
            unit={zone.routes.length === 1 ? "surface" : "surfaces"}
          />
        </div>
        <p
          className="text-sm"
          style={{ color: colors.torinoko, opacity: 0.85, maxWidth: 720 }}
        >
          {zone.description}
        </p>
      </header>

      {/* Route grid */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {zone.routes.map((route) => (
          <Link
            key={route.path}
            href={route.path}
            className="group flex flex-col gap-2 transition-colors"
            style={{
              padding: "14px 16px",
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
              textDecoration: "none",
              minHeight: 110,
            }}
          >
            <div className="flex items-center justify-between">
              <span
                className="font-mono text-xs uppercase tabular-nums"
                style={{
                  color: colors.aozora,
                  letterSpacing: "0.12em",
                  fontWeight: 500,
                }}
              >
                {route.label}
              </span>
              <ArrowRight
                size={14}
                style={{ color: colors.sumi[600] }}
                className="transition-transform group-hover:translate-x-1"
              />
            </div>
            <p
              className="text-xs"
              style={{ color: colors.torinoko, opacity: 0.85, lineHeight: 1.5 }}
            >
              {route.description}
            </p>
            <span
              className="font-mono text-[10px] tabular-nums"
              style={{ color: colors.sumi[600], marginTop: "auto" }}
            >
              {route.path}
            </span>
          </Link>
        ))}
      </div>

      {/* Footer hint */}
      <footer
        className="font-mono text-[10px] uppercase"
        style={{
          color: colors.sumi[600],
          letterSpacing: "0.12em",
          borderTop: `1px solid ${colors.sumi[700]}`,
          paddingTop: 12,
        }}
      >
        ⌘K to jump anywhere · 7 zones · {ZONES.reduce((n, z) => n + z.routes.length, 0)} surfaces total
      </footer>
    </div>
  );
}
