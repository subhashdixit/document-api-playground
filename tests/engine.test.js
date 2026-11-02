import test from "node:test";
import assert from "node:assert/strict";
import {
  validateDocument,
  validateRows,
  upsert,
  endpointURL,
} from "../site/engine.js";
test("nested plain JSON round trips without mutation", () => {
  const d = { name: "Example", skills: ["Python"], nested: { a: 1 } };
  const copy = validateDocument(d);
  copy.nested.a = 2;
  assert.equal(d.nested.a, 1);
});
test("operators and prototype keys are rejected at any depth", () => {
  for (const text of [
    '{"$where":"x"}',
    '{"a.b":1}',
    '{"nested":{"__proto__":{}}}',
    '{"constructor":1}',
  ])
    assert.throws(() => validateDocument(JSON.parse(text)));
  assert.throws(() => validateDocument([1]));
});
test("ID updates preserve other documents and reject duplicates", () => {
  const a = [{ id: "a", document: { x: 1 } }];
  const b = upsert(a, "b", { x: 2 });
  assert.equal(b.length, 2);
  assert.equal(upsert(b, "a", { x: 3 })[1].document.x, 3);
  assert.equal(a[0].document.x, 1);
  assert.throws(() => validateRows([a[0], a[0]]));
});
test("endpoint permits HTTPS and localhost only without URL credentials", () => {
  assert.equal(endpointURL("https://example.test/"), "https://example.test");
  assert.equal(endpointURL("http://localhost:8001"), "http://localhost:8001");
  for (const u of [
    "http://example.test",
    "https://name:secret@example.test",
    "javascript:bad",
    "https://example.test/private",
  ])
    assert.throws(() => endpointURL(u));
});

test("a substantial supported local collection round trips without dropping records", () => {
  const rows = Array.from({ length: 500 }, (_, i) => ({
    id: "record-" + i,
    document: { description: "x".repeat(3000) },
  }));
  const text = JSON.stringify({ schema: 1, documents: validateRows(rows) });
  assert.ok(text.length > 1024 * 1024);
  assert.deepEqual(validateRows(JSON.parse(text).documents), rows);
});
