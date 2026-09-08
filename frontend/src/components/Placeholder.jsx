/**
 * Honest placeholder for a page that is not built yet. It states what will be
 * here and which phase it lands in, so anyone opening the skeleton can tell
 * the difference between "not built" and "broken".
 */
export default function Placeholder({ phase, day, children }) {
  return (
    <div className="placeholder">
      <div className="placeholder-tag">
        Phase {phase} &middot; {day}
      </div>
      <ul className="placeholder-list">{children}</ul>
    </div>
  );
}
