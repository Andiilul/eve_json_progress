// inspect_jsonl_features.js
//
// Usage:
//   node inspect_jsonl_features.js <file.jsonl> [headN] [randN] [targetField] [flattenDepth]
//
// Defaults:
//   headN        = 1000000
//   randN        = 200000
//   targetField  = "Target"
//   flattenDepth = 1   (0=top-level only, 1=include one level nested, 2=deeper)
//
// Output:
//   - inspect_result.txt

const fs = require("fs");
const readline = require("readline");
const path = require("path");

// --------------------
// Deterministic RNG for reproducible reservoir sampling
// --------------------
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(42);
function randInt(maxExclusive) {
  return Math.floor(rng() * maxExclusive);
}

// --------------------
// Feature extraction (dot-path keys)
// --------------------
function isPlainObject(x) {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function collectFeatures(obj, flattenDepth = 1) {
  // Returns an array of feature paths found in this record (unique per record)
  const out = new Set();

  function walk(node, prefix, depthLeft) {
    if (node === null || node === undefined) {
      if (prefix) out.add(prefix);
      return;
    }

    if (Array.isArray(node)) {
      if (prefix) out.add(prefix + "[]");
      // We typically stop at arrays to avoid explosion.
      return;
    }

    if (!isPlainObject(node)) {
      if (prefix) out.add(prefix);
      return;
    }

    // node is object
    if (depthLeft < 0) {
      if (prefix) out.add(prefix);
      return;
    }

    for (const k of Object.keys(node)) {
      const p = prefix ? `${prefix}.${k}` : k;
      if (depthLeft === 0) {
        out.add(p);
      } else {
        walk(node[k], p, depthLeft - 1);
      }
    }
  }

  // depthLeft = flattenDepth (0 means only top-level keys)
  walk(obj, "", flattenDepth);
  return [...out];
}

function bump(map, key, delta = 1) {
  map.set(key, (map.get(key) || 0) + delta);
  if (map.get(key) <= 0) map.delete(key);
}

function formatCounts(map, limit = 30) {
  const entries = [...map.entries()].sort((a, b) => b[1] - a[1]);
  const lines = [];
  for (const [k, v] of entries.slice(0, limit)) lines.push(`  ${k}: ${v.toLocaleString()}`);
  if (entries.length > limit) lines.push(`  ... and ${entries.length - limit} more`);
  if (!lines.length) lines.push("  (none)");
  return lines;
}

function safeTargetValue(obj, targetField) {
  if (!obj || typeof obj !== "object") return "(missing)";
  if (!(targetField in obj)) return "(missing)";
  const v = obj[targetField];
  if (v === null || v === undefined) return "(null)";
  if (typeof v === "object") return "(object)";
  return String(v).trim();
}

// --------------------
// Args
// --------------------
const file = process.argv[2];
const headN = parseInt(process.argv[3] || "1000000", 10);
const randN = parseInt(process.argv[4] || "200000", 10);
const targetField = process.argv[5] || "Target";
const flattenDepth = parseInt(process.argv[6] || "1", 10);

const outPath = "inspect_result.txt";

if (!file || !fs.existsSync(file)) {
  console.error("❌ File not found:", file);
  process.exit(1);
}
if (!Number.isFinite(headN) || headN <= 0) {
  console.error("❌ Invalid headN:", process.argv[3]);
  process.exit(1);
}
if (!Number.isFinite(randN) || randN <= 0) {
  console.error("❌ Invalid randN:", process.argv[4]);
  process.exit(1);
}
if (!Number.isFinite(flattenDepth) || flattenDepth < 0 || flattenDepth > 5) {
  console.error("❌ Invalid flattenDepth (0..5 recommended):", process.argv[6]);
  process.exit(1);
}

// Detect likely JSON array file (not JSONL). We'll warn early.
// If the file starts with '[' (after whitespace), JSONL streaming won't work correctly.
try {
  const fd = fs.openSync(file, "r");
  const buf = Buffer.alloc(2048);
  const n = fs.readSync(fd, buf, 0, buf.length, 0);
  fs.closeSync(fd);
  const head = buf.slice(0, n).toString("utf8");
  const firstNonWs = head.match(/[^\s]/)?.[0];
  if (firstNonWs === "[") {
    console.error("❌ This looks like a single JSON ARRAY file (starts with '[').");
    console.error("   This script is for JSONL/NDJSON (one JSON object per line).");
    console.error("   Convert it to JSONL first, or use a streaming JSON parser library (e.g., stream-json).");
    process.exit(1);
  }
} catch (_) {
  // ignore peek errors
}

// --------------------
// Streaming read (JSONL)
// --------------------
const rl = readline.createInterface({
  input: fs.createReadStream(file),
  crlfDelay: Infinity,
});

let totalLines = 0;
let emptyLines = 0;
let parseErrors = 0;
let recordsSeen = 0;

// HEAD stats
let headRecords = 0;
const headTargetCount = new Map();
const headFeatureCount = new Map(); // feature -> presence count across head

// RANDOM stats (reservoir)
let reservoirFilled = 0;
const reservoirTargets = new Array(randN);
const reservoirFeatures = new Array(randN); // each is array of features (unique for that record)
const randTargetCount = new Map();
const randFeatureCount = new Map();

function addToRand(i, t, feats) {
  reservoirTargets[i] = t;
  reservoirFeatures[i] = feats;

  bump(randTargetCount, t, +1);
  for (const f of feats) bump(randFeatureCount, f, +1);
}

function removeFromRand(i) {
  const t = reservoirTargets[i];
  const feats = reservoirFeatures[i];
  if (t !== undefined) bump(randTargetCount, t, -1);
  if (Array.isArray(feats)) for (const f of feats) bump(randFeatureCount, f, -1);
}

rl.on("line", (line) => {
  totalLines++;
  const s = line.trim();
  if (!s) {
    emptyLines++;
    return;
  }

  let obj;
  try {
    obj = JSON.parse(s);
  } catch (e) {
    parseErrors++;
    return;
  }

  // we only handle object records
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    // treat non-object as parse error for our purpose
    parseErrors++;
    return;
  }

  recordsSeen++;

  const t = safeTargetValue(obj, targetField);
  const feats = collectFeatures(obj, flattenDepth);

  // HEAD (first headN records)
  if (headRecords < headN) {
    headRecords++;
    bump(headTargetCount, t, +1);
    for (const f of feats) bump(headFeatureCount, f, +1);
  }

  // RANDOM reservoir sample (size randN)
  if (reservoirFilled < randN) {
    addToRand(reservoirFilled, t, feats);
    reservoirFilled++;
  } else {
    // Reservoir sampling replacement
    const j = randInt(recordsSeen); // 0..recordsSeen-1
    if (j < randN) {
      removeFromRand(j);
      addToRand(j, t, feats);
    }
  }
});

rl.on("close", () => {
  // Summaries
  const out = [];
  out.push("✅ JSONL Feature Inspection");
  out.push(`Input file        : ${file}`);
  out.push(`Target field      : ${targetField}`);
  out.push(`Flatten depth     : ${flattenDepth}`);
  out.push(`HEAD N            : ${headN.toLocaleString()}`);
  out.push(`RANDOM N          : ${randN.toLocaleString()}`);
  out.push("");

  out.push("=== File scan stats ===");
  out.push(`Total lines       : ${totalLines.toLocaleString()}`);
  out.push(`Empty lines       : ${emptyLines.toLocaleString()}`);
  out.push(`Parse errors      : ${parseErrors.toLocaleString()}`);
  out.push(`Valid records     : ${recordsSeen.toLocaleString()}`);
  out.push("");

  out.push("=== HEAD (first N records) ===");
  out.push(`Records analyzed  : ${headRecords.toLocaleString()}`);
  out.push(`Unique features   : ${headFeatureCount.size.toLocaleString()}`);
  out.push(`Target unique     : ${headTargetCount.size}`);
  out.push("Target distribution:");
  out.push(...formatCounts(headTargetCount, 20));
  out.push("");
  out.push("Top features by presence (HEAD):");
  out.push(...formatCounts(headFeatureCount, 50));
  out.push("");

  out.push("=== RANDOM (reservoir sample over whole file) ===");
  out.push(`Records sampled   : ${reservoirFilled.toLocaleString()}`);
  out.push(`Unique features   : ${randFeatureCount.size.toLocaleString()}`);
  out.push(`Target unique     : ${randTargetCount.size}`);
  out.push("Target distribution:");
  out.push(...formatCounts(randTargetCount, 20));
  out.push("");
  out.push("Top features by presence (RANDOM):");
  out.push(...formatCounts(randFeatureCount, 50));
  out.push("");

  // Bias hint: HEAD single-class but RANDOM has >=2
  if (headTargetCount.size <= 1 && randTargetCount.size >= 2) {
    out.push("⚠️  NOTE: HEAD sample is single-class but RANDOM sample has multiple classes.");
    out.push("    Your file is likely ORDERED (e.g., attacks first then benign).");
    out.push("    Any pipeline phase using `iloc[:N]` (head) will be biased.");
    out.push("");
  }

  const text = out.join("\n");

  console.log(text);
  fs.writeFileSync(outPath, text, "utf8");
  console.log(`📝 Saved to: ${outPath}`);
});