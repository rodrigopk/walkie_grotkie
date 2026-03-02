import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const thisDir = path.dirname(fileURLToPath(import.meta.url));
const grotPngPath = path.resolve(thisDir, "../public/grot.png");

test("startup flow supports invalid and valid open file", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("startup-start-new")).toBeVisible();
  await expect(page.getByTestId("startup-load-grot")).toBeVisible();
  await expect(page.getByTestId("startup-open-file")).toBeVisible();

  await page.getByTestId("startup-file-input").setInputFiles({
    name: "bad.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not-a-png"),
  });
  await expect(page.getByTestId("startup-error")).toContainText("Expected image/png");

  await page.getByTestId("startup-file-input").setInputFiles(grotPngPath);
  await expect(page.getByTestId("toolbar-export")).toBeVisible();
  await expect(page.getByTestId("canvas-viewport-wrapper")).toBeVisible();
});

test("bridge and UI can update tool state and paint operations", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("startup-start-new").click();
  await expect(page.getByTestId("toolbar-export")).toBeVisible();

  await page.waitForFunction(() => Boolean(window.pixelEditorApi));

  await page.evaluate(() => {
    window.pixelEditorApi?.setPixel(1, 1, "#ff0000");
  });

  const pixelAfterBrush = await page.evaluate(() => window.pixelEditorApi?.getPixel(1, 1));
  expect(pixelAfterBrush).toEqual([255, 0, 0, 255]);

  await page.getByTestId("toolbar-undo").click();
  const pixelAfterUndo = await page.evaluate(() => window.pixelEditorApi?.getPixel(1, 1));
  expect(pixelAfterUndo).toEqual([0, 0, 0, 255]);

  await page.getByTestId("toolbar-redo").click();
  const pixelAfterRedo = await page.evaluate(() => window.pixelEditorApi?.getPixel(1, 1));
  expect(pixelAfterRedo).toEqual([255, 0, 0, 255]);

  await page.getByTestId("tool-picker").click();
  const stateAfterUiToolSwitch = await page.evaluate(() => window.pixelEditorApi?.getState());
  expect(stateAfterUiToolSwitch?.tool).toBe("picker");

  await page.evaluate(() => {
    window.pixelEditorApi?.fill(0, 0, "#00ff00");
  });
  const pixelAfterFill = await page.evaluate(() => window.pixelEditorApi?.getPixel(0, 0));
  expect(pixelAfterFill).toEqual([0, 255, 0, 255]);
});

test("export/import roundtrip preserves buffer hash", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("startup-start-new").click();
  await page.waitForFunction(() => Boolean(window.pixelEditorApi));

  await page.evaluate(() => {
    window.pixelEditorApi?.setPixel(2, 2, "#112233");
    window.pixelEditorApi?.setPixel(3, 4, "#abcdef");
    window.pixelEditorApi?.setPixel(63, 63, "#ffffff");
  });

  const expectedHash = await page.evaluate(() => window.pixelEditorApi?.getBufferHash());
  expect(expectedHash).toBeTruthy();

  const pngBytes = await page.evaluate(async () => {
    const blob = await window.pixelEditorApi!.exportPngBlob();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    return Array.from(bytes);
  });

  await page.getByTestId("toolbar-import-input").setInputFiles({
    name: "roundtrip.png",
    mimeType: "image/png",
    buffer: Buffer.from(pngBytes),
  });

  const importedHash = await page.evaluate(() => window.pixelEditorApi?.getBufferHash());
  expect(importedHash).toBe(expectedHash);
});

