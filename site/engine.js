const FORBIDDEN = new Set(["__proto__", "prototype", "constructor", "_id"]);
export function validateDocument(value) {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw Error("Use a JSON object.");
  let count = 0;
  function check(v, depth = 0) {
    if (depth > 10 || ++count > 2000) throw Error("Document is too complex.");
    if (v === null || typeof v === "boolean" || typeof v === "string") return;
    if (typeof v === "number") {
      if (!Number.isFinite(v)) throw Error("Numbers must be finite.");
      return;
    }
    if (Array.isArray(v)) {
      v.forEach((x) => check(x, depth + 1));
      return;
    }
    if (typeof v !== "object") throw Error("Unsupported JSON value.");
    for (const [key, item] of Object.entries(v)) {
      if (
        FORBIDDEN.has(key) ||
        key.startsWith("$") ||
        key.includes(".") ||
        key.length > 120
      )
        throw Error("Unsafe document key: " + key);
      check(item, depth + 1);
    }
  }
  check(value);
  const text = JSON.stringify(value);
  if (text.length > 30000) throw Error("Document exceeds 30,000 characters.");
  return JSON.parse(text);
}
export function validateRows(rows) {
  if (!Array.isArray(rows) || rows.length > 500)
    throw Error("Use up to 500 documents.");
  const ids = new Set();
  return rows.map((row) => {
    if (
      !row ||
      typeof row.id !== "string" ||
      !/^[-a-zA-Z0-9]{1,80}$/.test(row.id) ||
      ids.has(row.id)
    )
      throw Error("Invalid or duplicate document ID.");
    ids.add(row.id);
    return { id: row.id, document: validateDocument(row.document) };
  });
}
export function upsert(rows, id, document) {
  return validateRows([
    ...rows.filter((r) => r.id !== id),
    { id, document: validateDocument(document) },
  ]);
}
export function endpointURL(text) {
  const u = new URL(text);
  if (
    u.pathname !== "/" ||
    u.search ||
    u.hash ||
    u.username ||
    !(
      u.protocol === "https:" ||
      (u.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(u.hostname))
    )
  )
    throw Error("Use an HTTPS origin (or localhost for development).");
  return u.origin;
}
