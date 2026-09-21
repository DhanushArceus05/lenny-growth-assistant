/**
 * Focused security test for the artifact HTML rendering path. This is the single
 * highest-risk surface in the app (rendering fully untrusted, LLM-generated HTML),
 * so these assertions check the actual DOM output of the component, not just that
 * it renders without throwing.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SandboxedIframe } from "../SandboxedIframe";

describe("SandboxedIframe", () => {
  it("sets sandbox=allow-scripts and never includes allow-same-origin", () => {
    render(<SandboxedIframe content="<p>hello</p>" title="Test artifact" />);
    const iframe = screen.getByTitle("Test artifact") as HTMLIFrameElement;

    expect(iframe.getAttribute("sandbox")).toBe("allow-scripts");
    expect(iframe.getAttribute("sandbox")).not.toContain("allow-same-origin");
  });

  it("uses srcDoc rather than a src URL, so content never loads from the app's own origin", () => {
    render(<SandboxedIframe content="<p>hello</p>" title="Test artifact" />);
    const iframe = screen.getByTitle("Test artifact") as HTMLIFrameElement;

    expect(iframe.getAttribute("src")).toBeNull();
    expect(iframe.srcdoc).toContain("hello");
  });

  it("strips base and meta tags that could be used to hijack relative URLs or redirect", () => {
    const malicious = `<html><head><base href="https://evil.example/"><meta http-equiv="refresh" content="0;url=https://evil.example"></head><body>content</body></html>`;
    render(<SandboxedIframe content={malicious} title="Test artifact" />);
    const iframe = screen.getByTitle("Test artifact") as HTMLIFrameElement;

    expect(iframe.srcdoc.toLowerCase()).not.toContain("<base");
    expect(iframe.srcdoc.toLowerCase()).not.toContain("<meta");
  });

  it("strips inline event-handler attributes (e.g. onerror) from arbitrary elements", () => {
    const malicious = `<img src="x" onerror="window.parent.postMessage(document.cookie, '*')">`;
    render(<SandboxedIframe content={malicious} title="Test artifact" />);
    const iframe = screen.getByTitle("Test artifact") as HTMLIFrameElement;

    expect(iframe.srcdoc.toLowerCase()).not.toContain("onerror");
  });

  it("does not fabricate an allow-same-origin permission under any content input", () => {
    // Adversarial content trying to smuggle sandbox-affecting markup shouldn't
    // change the iframe's own sandbox attribute, since that's set by this
    // component, not derived from the artifact content.
    const malicious = `<iframe sandbox="allow-scripts allow-same-origin"></iframe>`;
    render(<SandboxedIframe content={malicious} title="Test artifact" />);
    const outerIframe = screen.getByTitle("Test artifact") as HTMLIFrameElement;

    expect(outerIframe.getAttribute("sandbox")).toBe("allow-scripts");
  });
});
