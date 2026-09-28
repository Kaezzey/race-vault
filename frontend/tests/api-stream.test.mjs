import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
});
const { generateGroundedAnswer } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

test("decodes split UTF-8 and frames, delivering drafts before completion", async (t) => {
  const drafts = [];
  let cancelled = false;
  const bytes = new TextEncoder().encode(
    ': keepalive\n\ndata: {"type":"draft","text":"Tyre — cold"}\n\n',
  );
  let index = 0;
  t.mock.method(globalThis, "fetch", async () => new Response(new ReadableStream({
    pull(controller) {
      if (index < bytes.length) {
        controller.enqueue(bytes.slice(index, ++index));
      } else {
        assert.deepEqual(drafts, ["Tyre — cold"]);
        controller.enqueue(new TextEncoder().encode(
          'data: {"type":"complete","response":{"answer":"Final [E1]"}}\n\n',
        ));
      }
    },
    cancel() { cancelled = true; },
  }, { highWaterMark: 0 })));
  const response = await generateGroundedAnswer("tyres", {}, (text) => drafts.push(text));
  assert.equal(response.answer, "Final [E1]");
  assert.equal(cancelled, true);
});

test("rejects an interrupted stream instead of returning the draft", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(
    'data: {"type":"draft","text":"Partial"}\n\n',
  ));
  await assert.rejects(generateGroundedAnswer("tyres", {}, () => {}), /before completion/);
});

test("preserves error codes received after streaming starts", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(
    'data: {"type":"error","status":502,"error":{"code":"grounded_answer_invalid","message":"Validation failed"}}\n\n',
  ));
  await assert.rejects(generateGroundedAnswer("tyres", {}, () => {}), {
    code: "grounded_answer_invalid", status: 502,
  });
});
