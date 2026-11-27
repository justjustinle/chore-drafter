// Small building blocks shared by every screen.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

// ---------- Parchment window ----------

export function Window({
  title,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`window ${className}`}>
      {(title || actions) && (
        <div className="window-title">
          {title && <h2>{title}</h2>}
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

// ---------- Avatar ----------

const AVATAR_COLOURS = ["#bae6fd", "#bbf7d0", "#fde68a", "#fbcfe8", "#ddd6fe", "#fed7aa", "#a5f3fc"];

export function Avatar({
  memberId,
  name,
  crown = false,
  large = false,
}: {
  memberId: number;
  name: string;
  crown?: boolean;
  large?: boolean;
}) {
  const colour = AVATAR_COLOURS[memberId % AVATAR_COLOURS.length];
  return (
    <span
      className={`avatar${large ? " large" : ""}`}
      style={{ ["--c" as string]: colour }}
      aria-hidden="true"
      title={name}
    >
      {crown && <span className="crown">👑</span>}
      {name.charAt(0).toUpperCase()}
    </span>
  );
}

// ---------- Effort as slime pips ----------

export function Pips({ value, max = 10 }: { value: number; max?: number }) {
  return (
    <span className="pips" role="img" aria-label={`${value} effort points out of ${max}`}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} className={`pip${i < value ? " on" : ""}`} />
      ))}
    </span>
  );
}

export function Tokens({ value }: { value: number }) {
  return (
    <span className="token" aria-label={`${value} tokens`}>
      {value}
    </span>
  );
}

// ---------- Button with a tooltip explaining why it is disabled ----------

export function TipButton({
  tip,
  className = "btn",
  disabled,
  onClick,
  children,
  ...rest
}: {
  tip?: string;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  "aria-keyshortcuts"?: string;
}) {
  return (
    <span className="tip" data-tip={disabled && tip ? tip : undefined}>
      <button
        type="button"
        className={className}
        disabled={disabled}
        onClick={onClick}
        aria-describedby={undefined}
        title={disabled && tip ? tip : undefined}
        {...rest}
      >
        {children}
      </button>
    </span>
  );
}

// ---------- Modal ----------

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="backdrop" onClick={onClose}>
      <div className="window modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="window-title">
          <h2>{title}</h2>
          <button type="button" className="btn quiet small" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------- Toasts ----------

type ToastTone = "info" | "warn" | "ok";
interface ToastItem {
  id: number;
  text: string;
  tone: ToastTone;
}

const ToastContext = createContext<(text: string, tone?: ToastTone) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const show = useCallback((text: string, tone: ToastTone = "info") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current.slice(-2), { id, text, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((t) => t.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            <span aria-hidden="true">{t.tone === "warn" ? "⚠️" : t.tone === "ok" ? "✅" : "📜"}</span>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ---------- Reduced motion ----------

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

// ---------- Flavour text ----------

const FLAVOURS = [
  "A humble quest for a humble hero",
  "The guild has posted a bounty",
  "Rumoured to be tougher than it looks",
  "Only the brave take this one",
  "A quick errand before tea",
  "Legends speak of this chore",
];

/** A light RPG line shown UNDER the real chore name, never instead of it. */
export function flavourFor(choreId: number): string {
  return FLAVOURS[choreId % FLAVOURS.length];
}
