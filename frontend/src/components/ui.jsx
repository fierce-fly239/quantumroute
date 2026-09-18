/** The design's recurring pieces, as components. Page header with the eyebrow
 *  and the purple full stop, stat cards, cards with a head, the purple note.
 *  Layout and colour only; every value rendered through these comes from the
 *  page that uses them, which gets it from the API. */
import { Check } from "./icons.jsx";

export function PageHead({ eyebrow, status, statusTone, title, lede, actions }) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">
          <span className="eyebrow-dot" />
          <span className="eyebrow-text">{eyebrow}</span>
          {status && (
            <>
              <span className="eyebrow-sep" />
              <span className={`pill${statusTone ? ` pill-${statusTone}` : ""}`}>{status}</span>
            </>
          )}
        </div>
        <h1>
          {title}<span className="h1-dot">.</span>
        </h1>
        {lede && <p className="page-lede">{lede}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Stat({ icon, label, value, foot, tone = "mint", good = false, delay }) {
  return (
    <div className={`stat stat-${tone}${good ? " stat-good" : ""} rise${delay ? ` rise-${delay}` : ""}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-main">
        <div className="stat-l">{label}</div>
        <div className="stat-n">{value}</div>
      </div>
      {foot && <div className="stat-foot">{foot}</div>}
    </div>
  );
}

export function Card({ title, icon, sub, pill, pillTone, action, children, flush = false, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          <div>
            <h2>
              {icon}
              {title}
              {pill && <span className={`pill${pillTone ? ` pill-${pillTone}` : ""}`}>{pill}</span>}
            </h2>
            {sub && <div className="card-sub">{sub}</div>}
          </div>
          {action}
        </div>
      )}
      <div className={flush ? "card-body-flush" : "card-body"}>{children}</div>
    </section>
  );
}

export function Note({ eyebrow, icon, title, children, actions, tone = "" }) {
  return (
    <div className={`note${tone ? ` note-${tone}` : ""}`}>
      <div className="note-eyebrow">{icon}<span>{eyebrow}</span></div>
      {title && <h3>{title}</h3>}
      {typeof children === "string" ? <p>{children}</p> : children}
      {actions && <div className="note-actions">{actions}</div>}
    </div>
  );
}

export function CheckItem({ done, live, children }) {
  return (
    <div className={`check${done ? " is-done" : ""}${live ? " is-live" : ""}`}>
      <span className="check-mark">{done && <Check />}</span>
      <span>{children}</span>
    </div>
  );
}

export function Bar({ pct, tone = "mint", label, value }) {
  return (
    <div>
      {(label || value) && (
        <div className="bar-row"><span>{label}</span><span className="mono">{value}</span></div>
      )}
      <div className={`bar bar-${tone}`}><span style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
    </div>
  );
}

export function Toast({ text }) {
  if (!text) return null;
  return <div className="toast" role="status"><Check />{text}</div>;
}
