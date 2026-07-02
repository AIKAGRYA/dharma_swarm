import { CheckCircle2, Download, FileText, HelpCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DataRoomFileListProps {
  files: Record<string, string>;
  receipts?: Array<{ name: string; path: string; status: string }>;
  className?: string;
}

function statusIcon(status: string) {
  const s = status.toLowerCase();
  if (s.includes("ok") || s.includes("allowed") || s.includes("complete") || s === "green") {
    return <CheckCircle2 size={16} className="text-rokusho" aria-hidden="true" />;
  }
  if (s.includes("block") || s.includes("error") || s.includes("fail") || s === "red") {
    return <XCircle size={16} className="text-bengara" aria-hidden="true" />;
  }
  return <HelpCircle size={16} className="text-kinpaku" aria-hidden="true" />;
}

function FileRow({ name, path }: { name: string; path: string }) {
  const isUrl = path.startsWith("http://") || path.startsWith("https://");
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-3">
      <div className="flex min-w-0 items-start gap-3">
        <FileText size={18} className="shrink-0 text-[#60736b]" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#181a20]">{name}</p>
          <p className="min-w-0 break-all text-xs text-[#5d5f68]">{path}</p>
        </div>
      </div>
      {!isUrl ? (
        <span className="shrink-0 rounded-md bg-[#f4f1ea] px-2 py-1 text-xs font-semibold uppercase text-[#60736b]">
          local
        </span>
      ) : (
        <a
          href={path}
          download
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[#181a20]/10 px-2 py-1 text-xs font-semibold text-[#0d615f] transition hover:bg-[#f4f1ea]"
        >
          <Download size={14} aria-hidden="true" />
          JSON
        </a>
      )}
    </li>
  );
}

export function DataRoomFileList({ files, receipts, className }: DataRoomFileListProps) {
  return (
    <div className={cn("space-y-6", className)}>
      <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
        <h3 className="font-heading text-lg font-semibold text-[#181a20]">Report files</h3>
        <ul className="mt-4 divide-y divide-[#181a20]/10">
          {Object.entries(files).map(([name, path]) => (
            <FileRow key={name} name={name} path={path} />
          ))}
        </ul>
      </div>

      {receipts && receipts.length > 0 && (
        <div className="rounded-lg border border-[#181a20]/10 bg-white p-5">
          <h3 className="font-heading text-lg font-semibold text-[#181a20]">Receipts</h3>
          <ul className="mt-4 divide-y divide-[#181a20]/10">
            {receipts.map((receipt) => (
              <li key={receipt.path} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-3">
                <div className="flex min-w-0 items-start gap-3">
                  {statusIcon(receipt.status)}
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[#181a20]">{receipt.name}</p>
                    <p className="min-w-0 break-all text-xs text-[#5d5f68]">{receipt.path}</p>
                  </div>
                </div>
                <span className="shrink-0 rounded-md bg-[#f4f1ea] px-2 py-1 text-xs font-semibold uppercase text-[#60736b]">
                  {receipt.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
