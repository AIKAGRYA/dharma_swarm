// Print the ScenicStrip Great Wave straight to the terminal (ds wave).
// Same asset the TUI renders; lets the operator see the art without the app.
import {SCENIC_VARIANTS, SCENIC_WIDTHS} from "../src/components/scenicArt";

const ESC = "";
const columns = process.stdout.columns ?? 100;
const width = SCENIC_WIDTHS.find((candidate) => candidate <= columns - 2) ?? SCENIC_WIDTHS[SCENIC_WIDTHS.length - 1];
const rows = SCENIC_VARIANTS[String(width)] ?? [];

function rgb(hex: string): string {
  return `${parseInt(hex.slice(1, 3), 16)};${parseInt(hex.slice(3, 5), 16)};${parseInt(hex.slice(5, 7), 16)}`;
}

const out: string[] = [""];
for (const row of rows) {
  let line = " ";
  for (const segment of row) {
    line += `${ESC}[38;2;${rgb(segment.fg)}m${ESC}[48;2;${rgb(segment.bg)}m` + "▀".repeat(segment.n);
  }
  line += `${ESC}[0m`;
  out.push(line);
}
out.push("");
process.stdout.write(out.join("\n") + "\n");
