"use client";

/**
 * CommandPalette — Cmd+K as primary navigation (Phase 4 plan).
 *
 * Opens on Cmd/Ctrl+K, closes on Esc. Lists every route grouped by its
 * verb-shaped zone (COCKPIT / TALK / WATCH / JUDGE / MAP / SENSE /
 * REMEMBER). Type to filter; Enter to navigate.
 *
 * Per command-plane-design-lock:
 *   - mono ALLCAPS group labels, 0.12em tracking
 *   - hairline border on the palette frame, no glow
 *   - aozora active selection accent only
 *   - centered overlay at top-third of viewport
 */

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { colors } from "@/lib/theme";
import { ZONES } from "@/components/dashboard/ZoneTabs";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Cmd+K / Ctrl+K toggles
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }
      // Esc closes
      if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function go(path: string) {
    setOpen(false);
    router.push(path);
  }

  if (!open) return null;

  return (
    <div
      onClick={() => setOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "12vh",
        backgroundColor: `color-mix(in srgb, ${colors.sumi[950]} 70%, transparent)`,
        backdropFilter: "blur(2px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(640px, 92vw)",
          maxHeight: "70vh",
          display: "flex",
          flexDirection: "column",
          backgroundColor: colors.sumi[900],
          border: `1px solid ${colors.sumi[700]}`,
        }}
      >
        <Command
          loop
          shouldFilter
          style={{ display: "flex", flexDirection: "column", maxHeight: "70vh" }}
        >
          <div
            style={{
              borderBottom: `1px solid ${colors.sumi[700]}`,
              padding: "0 12px",
              height: 40,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span
              className="font-mono text-xs uppercase tabular-nums"
              style={{ color: colors.sumi[600], letterSpacing: "0.14em" }}
            >
              ⌘K
            </span>
            <Command.Input
              autoFocus
              placeholder="Jump to anywhere..."
              className="flex-1 bg-transparent font-mono text-sm focus:outline-none"
              style={{
                color: colors.torinoko,
                caretColor: colors.aozora,
              }}
            />
            <span
              className="font-mono text-[10px] uppercase"
              style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
            >
              esc to close
            </span>
          </div>

          <Command.List
            style={{
              overflow: "auto",
              padding: "4px 0",
            }}
          >
            <Command.Empty
              className="font-mono text-xs uppercase"
              style={{
                padding: "16px 12px",
                color: colors.sumi[600],
                letterSpacing: "0.12em",
              }}
            >
              No matches.
            </Command.Empty>

            {/* Zone landings — primary navigation */}
            <Command.Group heading="ZONES · jump to landing">
              {ZONES.map((zone) => (
                <Command.Item
                  key={zone.id}
                  value={`${zone.label} ${zone.verb} ${zone.landingPath}`}
                  onSelect={() => go(zone.landingPath)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "6px 12px",
                    height: 28,
                    fontSize: 13,
                    color: colors.torinoko,
                    cursor: "pointer",
                  }}
                >
                  <span
                    className="font-mono text-[10px] uppercase tabular-nums"
                    style={{
                      color: colors.aozora,
                      letterSpacing: "0.12em",
                      width: 64,
                      fontWeight: 500,
                    }}
                  >
                    {zone.label}
                  </span>
                  <span style={{ color: colors.torinoko }}>{zone.verb}</span>
                  <span
                    className="font-mono text-[10px]"
                    style={{ color: colors.sumi[600], marginLeft: "auto" }}
                  >
                    {zone.landingPath}
                  </span>
                </Command.Item>
              ))}
            </Command.Group>

            {ZONES.map((zone) => (
              <Command.Group
                key={zone.id}
                heading={`${zone.label} · ${zone.verb}`}
                style={{}}
              >
                {zone.routes.map((route) => (
                  <Command.Item
                    key={route.path}
                    value={`${zone.label} ${route.label} ${route.path}`}
                    onSelect={() => go(route.path)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "6px 12px",
                      height: 28,
                      fontSize: 13,
                      color: colors.torinoko,
                      cursor: "pointer",
                    }}
                  >
                    <span
                      className="font-mono text-[10px] uppercase tabular-nums"
                      style={{
                        color: colors.sumi[600],
                        letterSpacing: "0.10em",
                        width: 64,
                      }}
                    >
                      {zone.label}
                    </span>
                    <span style={{ color: colors.torinoko }}>
                      {route.label}
                    </span>
                    <span
                      className="font-mono text-[10px]"
                      style={{ color: colors.sumi[600], marginLeft: "auto" }}
                    >
                      {route.path}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>

        {/* Inline styles for cmdk's selected-item state — cmdk applies
            data-selected="true" to the focused item; tint with aozora. */}
        <style jsx global>{`
          [cmdk-item][data-selected="true"] {
            background-color: color-mix(in srgb, ${colors.aozora} 8%, transparent);
            border-left: 2px solid ${colors.aozora};
            padding-left: 10px !important;
          }
          [cmdk-group-heading] {
            padding: 8px 12px 4px 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: ${colors.sumi[600]};
          }
        `}</style>
      </div>
    </div>
  );
}
