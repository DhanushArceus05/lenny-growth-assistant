"use client";

import { useMemo } from "react";
import DOMPurify from "dompurify";

interface SandboxedIframeProps {
  content: string;
  title: string;
}

/**
 * Renders untrusted model-generated HTML.
 *
 * What this permits: the artifact's own scripts and styles run, so an interactive
 * HTML snippet (a calculator, a styled one-pager) works as intended.
 *
 * What this blocks:
 *  - `allow-same-origin` is never set alongside `allow-scripts`, so the iframe gets
 *    a unique opaque origin — it CANNOT read this app's cookies, localStorage,
 *    sessionStorage, or DOM, and any same-origin fetch() it attempts is blocked by
 *    the browser as cross-origin.
 *  - `srcDoc` (not `src` pointing at a same-origin URL) means the content is never
 *    served from the app's own origin in the first place.
 *  - No `allow-top-navigation`, `allow-popups`, or `allow-forms` — the artifact
 *    can't navigate the parent tab, spawn popups, or submit forms anywhere.
 *  - DOMPurify sanitization runs before the content ever reaches the iframe, as a
 *    second layer independent of the sandbox — belt-and-suspenders, not the primary
 *    boundary (the sandbox attributes are).
 */
export function SandboxedIframe({ content, title }: SandboxedIframeProps) {
  const cleanHtml = useMemo(() => {
    return DOMPurify.sanitize(content, {
      WHOLE_DOCUMENT: true,
      // <script> is explicitly allowed here even though DOMPurify strips it by
      // default: the sandboxed iframe (no allow-same-origin) is the actual security
      // boundary that neutralizes what a script can do — it can't reach parent
      // cookies/localStorage/DOM/fetch. Blocking <script> here would silently break
      // every interactive HTML artifact while adding no real protection beyond what
      // the sandbox already provides. DOMPurify's role is to still strip dangerous
      // *markup* (e.g. meta-refresh redirects, base-href hijacks, nested iframes).
      ADD_TAGS: ["style", "link", "script"],
      ADD_ATTR: ["target"],
      FORBID_TAGS: ["base", "meta"],
    });
  }, [content]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-slate-soft bg-white">
      <div className="flex items-center justify-between border-b border-slate-soft bg-ink-raised px-4 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-parchment/70">{title}</span>
        <span className="rounded border border-amber/30 bg-amber-soft px-2 py-0.5 text-xs text-amber">
          Sandboxed preview
        </span>
      </div>
      <iframe
        title={title}
        srcDoc={cleanHtml}
        sandbox="allow-scripts"
        className="h-full w-full flex-1 border-none bg-white"
      />
    </div>
  );
}
