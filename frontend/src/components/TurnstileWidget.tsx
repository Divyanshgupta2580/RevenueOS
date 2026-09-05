"use client";

import { useEffect, useRef, useState } from "react";

interface TurnstileProps {
  onSuccess: (token: string) => void;
  onError?: (error: unknown) => void;
  onExpire?: () => void;
}

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        params: {
          sitekey: string;
          callback: (token: string) => void;
          "error-callback"?: (error: unknown) => void;
          "expired-callback"?: () => void;
          theme?: "dark" | "light" | "auto";
        }
      ) => string;
      reset: (widgetId: string) => void;
      remove: (widgetId: string) => void;
    };
    onTurnstileLoaded?: () => void;
  }
}

export default function TurnstileWidget({ onSuccess, onError, onExpire }: TurnstileProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [widgetError, setWidgetError] = useState<string | null>(null);

  // Store latest callbacks in refs to avoid re-rendering/resetting the widget on form input keystrokes
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const onExpireRef = useRef(onExpire);

  useEffect(() => {
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
    onExpireRef.current = onExpire;
  });

  useEffect(() => {
    // In production Vercel: NEXT_PUBLIC_TURNSTILE_SITE_KEY provides the authorized production widget.
    // In preview/development: falls back to Cloudflare official testing pass key (1x00000000000000000000AA).
    const siteKey =
      process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "1x00000000000000000000AA";

    const renderWidget = () => {
      if (window.turnstile && containerRef.current && !widgetIdRef.current) {
        try {
          const id = window.turnstile.render(containerRef.current, {
            sitekey: siteKey,
            callback: (token: string) => {
              setWidgetError(null);
              onSuccessRef.current(token);
            },
            "error-callback": (err: unknown) => {
              setWidgetError("Security challenge failed. Ensure you are accessing through the authorized production domain.");
              if (onErrorRef.current) onErrorRef.current(err);
            },
            "expired-callback": () => {
              if (onExpireRef.current) onExpireRef.current();
            },
            theme: "dark",
          });
          widgetIdRef.current = id;
        } catch (renderErr) {
          if (onErrorRef.current) onErrorRef.current(renderErr);
        }
      }
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      window.onTurnstileLoaded = renderWidget;
      const scriptId = "turnstile-script";
      if (!document.getElementById(scriptId)) {
        const script = document.createElement("script");
        script.id = scriptId;
        script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoaded";
        script.async = true;
        script.defer = true;
        document.body.appendChild(script);
      }
    }

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // Ignore cleanup errors
        }
        widgetIdRef.current = null;
      }
    };
  }, []);

  return (
    <div className="flex flex-col items-center my-3">
      <div ref={containerRef} className="min-h-[65px]" />
      {widgetError && (
        <p className="text-[11px] text-rose-400 mt-1 text-center">
          {widgetError}
        </p>
      )}
    </div>
  );
}
