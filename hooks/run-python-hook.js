#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

// Same list as valid_extensions in validate-schema.py. The hook fires on every
// Edit and Write, so skip the Python probe for files that cannot hold JSON-LD.
const SCHEMA_FILE_EXTENSIONS = [".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs"];

// The skip belongs to the schema hook only; any other hook script always runs.
const SCHEMA_HOOK_SCRIPT = "validate-schema.py";

function isSchemaHook(hookScript) {
  return path.basename(hookScript) === SCHEMA_HOOK_SCRIPT;
}

function cannotHoldSchema(filePath) {
  // An unsubstituted "${tool_input.file_path}" leaves the path to the stdin event.
  if (!filePath || filePath.includes("${")) {
    return false;
  }
  const lower = filePath.toLowerCase();
  return !SCHEMA_FILE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function stripWrappingQuotes(value) {
  return value.replace(/^["']|["']$/g, "");
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.CLAUDE_SEO_PYTHON) {
    candidates.push({
      label: "CLAUDE_SEO_PYTHON",
      exe: stripWrappingQuotes(process.env.CLAUDE_SEO_PYTHON),
      args: [],
    });
  }
  candidates.push(
    { label: "py -3", exe: "py", args: ["-3"] },
    { label: "python3", exe: "python3", args: [] },
    { label: "python", exe: "python", args: [] },
  );
  return candidates;
}

function isStoreStubOutput(text) {
  return /Microsoft Store|WindowsApps|App execution alias|was not found/i.test(text);
}

function probe(candidate) {
  const script = "import sys; print(sys.executable); print(sys.version.split()[0])";
  const result = spawnSync(candidate.exe, [...candidate.args, "-c", script], {
    encoding: "utf8",
  });
  const output = `${result.stdout || ""}\n${result.stderr || ""}`;
  return result.status === 0 && Boolean((result.stdout || "").trim()) && !isStoreStubOutput(output);
}

function main() {
  const [, , hookScript, ...hookArgs] = process.argv;
  if (!hookScript || (isSchemaHook(hookScript) && cannotHoldSchema(hookArgs[0]))) {
    process.exit(0);
  }

  for (const candidate of pythonCandidates()) {
    if (!probe(candidate)) {
      continue;
    }
    const result = spawnSync(candidate.exe, [...candidate.args, hookScript, ...hookArgs], {
      stdio: "inherit",
    });
    if (result.error) {
      continue;
    }
    process.exit(result.status === null ? 1 : result.status);
  }

  console.error(
    "Claude SEO hook could not find Python. Tried CLAUDE_SEO_PYTHON, py -3, python3, python.",
  );
  process.exit(1);
}

main();
