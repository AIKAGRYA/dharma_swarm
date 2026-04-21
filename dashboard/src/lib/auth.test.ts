import assert from "node:assert/strict";
import test from "node:test";

import {
  clearDashboardApiToken,
  consumeDesktopShellBootstrapHash,
  readDashboardApiToken,
} from "./auth.ts";

function installWindow(hash: string): { restore: () => void; replacements: string[] } {
  const originalWindow = globalThis.window;
  const replacements: string[] = [];
  const store = new Map<string, string>();

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: {
        getItem(key: string) {
          return store.has(key) ? store.get(key)! : null;
        },
        setItem(key: string, value: string) {
          store.set(key, value);
        },
        removeItem(key: string) {
          store.delete(key);
        },
      },
      location: {
        hash,
        pathname: "/dashboard/command-post",
        search: "",
      },
      history: {
        state: null,
        replaceState(_state: unknown, _title: string, url: string) {
          replacements.push(url);
        },
      },
    },
  });

  return {
    replacements,
    restore() {
      clearDashboardApiToken();
      if (originalWindow === undefined) {
        // @ts-expect-error synthetic window cleanup in node tests
        delete globalThis.window;
        return;
      }
      Object.defineProperty(globalThis, "window", {
        configurable: true,
        value: originalWindow,
      });
    },
  };
}

test("consumeDesktopShellBootstrapHash persists token and strips bootstrap fragment", () => {
  const env = installWindow("#desktop_api_key=desk-top-123&view=runtime");

  try {
    const token = consumeDesktopShellBootstrapHash();
    assert.equal(token, "desk-top-123");
    assert.equal(readDashboardApiToken(), "desk-top-123");
    assert.deepEqual(env.replacements, ["/dashboard/command-post#view=runtime"]);
  } finally {
    env.restore();
  }
});
