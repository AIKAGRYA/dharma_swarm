"use client";

import { AlertTriangle, Clock3, Inbox } from "lucide-react";
import {
  nodeReadFailureView,
} from "./a2aNodeReadModel";

export function SurfaceMessage({
  kind,
  title,
  detail,
}: {
  kind: "empty" | "error" | "loading" | "unknown";
  title: string;
  detail: string;
}) {
  const Icon =
    kind === "error" || kind === "unknown"
      ? AlertTriangle
      : kind === "loading"
        ? Clock3
        : Inbox;
  const alert = kind === "error" || kind === "unknown";
  return (
    <div
      className={`rounded-2xl border px-4 py-5 ${
        kind === "error"
          ? "border-bengara/30 bg-bengara/[0.06]"
          : kind === "unknown"
            ? "border-fuji/35 bg-fuji/[0.07]"
            : "border-sumi-700/35 bg-sumi-900/55"
      }`}
      role={alert ? "alert" : "status"}
    >
      <div className="flex items-start gap-3">
        <Icon
          size={16}
          className={
            kind === "error"
              ? "mt-0.5 text-bengara"
              : kind === "unknown"
                ? "mt-0.5 text-fuji"
                : "mt-0.5 text-kitsurubami/75"
          }
          aria-hidden="true"
        />
        <div>
          <p
            className={`text-sm font-medium ${
              kind === "error"
                ? "text-bengara"
                : kind === "unknown"
                  ? "text-fuji"
                  : "text-torinoko"
            }`}
          >
            {title}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-kitsurubami/75">
            {detail}
          </p>
        </div>
      </div>
    </div>
  );
}

export function FailureMessage({
  failure,
}: {
  failure: ReturnType<typeof nodeReadFailureView>;
}) {
  return (
    <SurfaceMessage
      kind={failure.surfaceKind}
      title={failure.title}
      detail={failure.detail}
    />
  );
}
