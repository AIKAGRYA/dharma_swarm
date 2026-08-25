"use client";

import { SadhanaOperatorControl } from "@/components/cockpit/SadhanaOperatorControl";
import { useMissionSarathi } from "@/hooks/useMissionSarathi";
import { normalOperatorControlsAuthorized } from "@/lib/sadhanaOperatorControl";

const SADHANA_MISSION_ID = "sadhana-10-20260823";

export default function SadhanaControlPage() {
  const { projection, isLoading, sourceErrors } = useMissionSarathi(
    SADHANA_MISSION_ID,
  );
  const normalControlsDisabled = !normalOperatorControlsAuthorized(projection);

  return (
    <main className="mx-auto flex w-full min-w-0 max-w-[30rem] flex-col gap-3">
      <p className="m-0 text-[11px] leading-relaxed text-sumi-500">
        Focused phone confirmation, linked from the Constellation. This route
        does not broaden control authority.
      </p>
      {sourceErrors.length > 0 && (
        <p className="m-0 rounded-lg border border-kohaku/20 bg-kohaku/5 px-3 py-2 text-[11px] leading-relaxed text-sumi-400">
          Authority evidence is unavailable. Accepted requests will remain
          explicitly unproven until a valid projection arrives.
        </p>
      )}
      <SadhanaOperatorControl
        snapshot={projection}
        disabled={isLoading}
        normalControlsDisabled={normalControlsDisabled}
      />
    </main>
  );
}
