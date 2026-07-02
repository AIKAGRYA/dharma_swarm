import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicShell } from "@/components/livelihood-loom/public/PublicShell";
import { PacketDetailCard } from "@/components/livelihood-loom/public/PacketDetailCard";
import {
  loadLivelihoodLoomPackets,
  loadLivelihoodLoomPacketById,
} from "@/lib/livelihoodLoom";

export async function generateStaticParams(): Promise<{ packet_id: string }[]> {
  const packets = loadLivelihoodLoomPackets();
  return packets.map((packet) => ({ packet_id: packet.packet_id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ packet_id: string }>;
}): Promise<Metadata> {
  const { packet_id } = await params;
  const packet = loadLivelihoodLoomPacketById(packet_id);
  const title = packet
    ? `${packet.packet_id} | Livelihood Loom Proof Packet`
    : "Packet | Livelihood Loom";

  return {
    title,
    description:
      packet?.sponsor_value ??
      "Enablement packet detail for sponsor and investor diligence.",
    openGraph: {
      title,
      description:
        packet?.sponsor_value ??
        "Enablement packet detail for sponsor and investor diligence.",
      images: ["/livelihood-loom/hero-market-network.png"],
    },
  };
}

export default async function PacketDetailPage({
  params,
}: {
  params: Promise<{ packet_id: string }>;
}) {
  const { packet_id } = await params;
  const packet = loadLivelihoodLoomPacketById(packet_id);

  if (!packet) {
    notFound();
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-7xl px-5 py-24 sm:px-8">
        <PacketDetailCard packet={packet} />
      </section>
    </PublicShell>
  );
}
