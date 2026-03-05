import "@testing-library/jest-dom";
import { vi } from "vitest";

// jsdom does not implement scrollIntoView — stub it to prevent errors.
Element.prototype.scrollIntoView = vi.fn();

// jsdom does not implement pointer capture APIs — stub them.
Element.prototype.setPointerCapture = vi.fn();
Element.prototype.releasePointerCapture = vi.fn();
