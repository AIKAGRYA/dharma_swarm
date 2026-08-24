import { createServer } from "node:http";
import { createRequire } from "node:module";
import { lstatSync, chmodSync } from "node:fs";
import path from "node:path";

const SOCKET_PATH = "/run/dharma-sadhana/dashboard/constellation.sock";
const SOCKET_DIRECTORY = path.dirname(SOCKET_PATH);
const OUTER_PARENT = "/run/dharma-sadhana";

function fail(message) {
  process.stderr.write(`SADHANA dashboard refused startup: ${message}\n`);
  process.exit(1);
}

if (process.getuid?.() === 0 || process.getgid?.() === 0) {
  fail("dedicated non-root identity required");
}
if (process.env.SADHANA_DASHBOARD_SOCKET !== SOCKET_PATH) {
  fail("Unix socket binding differs");
}

const outer = lstatSync(OUTER_PARENT);
const directory = lstatSync(SOCKET_DIRECTORY);
if (
  !outer.isDirectory() ||
  outer.isSymbolicLink() ||
  outer.uid !== 0 ||
  outer.gid !== 0 ||
  (outer.mode & 0o777) !== 0o711
) {
  fail("outer runtime custody differs");
}
if (
  !directory.isDirectory() ||
  directory.isSymbolicLink() ||
  directory.uid !== process.getuid() ||
  directory.gid !== process.getgid() ||
  (directory.mode & 0o777) !== 0o700
) {
  fail("exclusive socket-directory custody differs");
}
try {
  lstatSync(SOCKET_PATH);
  fail("socket path already exists");
} catch (error) {
  if (error?.code !== "ENOENT") {
    throw error;
  }
}

const dashboardRoot = process.cwd();
const require = createRequire(path.join(dashboardRoot, "package.json"));
const next = require("next");
const app = next({ dev: false, dir: dashboardRoot });
await app.prepare();
const handler = app.getRequestHandler();
const server = createServer((request, response) => handler(request, response));

process.umask(0o177);
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(SOCKET_PATH, resolve);
});
chmodSync(SOCKET_PATH, 0o600);
const admitted = lstatSync(SOCKET_PATH);
if (
  !admitted.isSocket() ||
  admitted.isSymbolicLink() ||
  admitted.uid !== process.getuid() ||
  admitted.gid !== process.getgid() ||
  (admitted.mode & 0o777) !== 0o600 ||
  admitted.nlink !== 1
) {
  server.close();
  fail("created socket custody differs");
}

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    server.close((error) => process.exit(error ? 1 : 0));
  });
}
