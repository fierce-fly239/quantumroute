/** Best-cost-so-far against iteration, for one or two algorithms.
 *
 *  Plain SVG rather than a charting library: two line series on linear axes is
 *  not worth 200 KB of dependency, and a hand-drawn path is one thing fewer to
 *  break the night before a demo.
 *
 *  The y-axis does NOT start at zero, on purpose. Costs here sit around 180 or
 *  1400 and the interesting movement is a few percent; a zero-based axis would
 *  render every run as an identical flat line. The axis labels state the range
 *  so the scale is never implied to be something it is not.
 */
const PAD = { top: 14, right: 14, bottom: 26, left: 54 };
const W = 900;
const H = 300;

export default function ConvergenceChart({ series, height = 300 }) {
  const active = series.filter((s) => s.values && s.values.length > 1);
  if (!active.length) {
    return <div className="chart-empty">Nothing to plot yet.</div>;
  }

  const length = Math.max(...active.map((s) => s.values.length));
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of active) {
    for (const v of s.values) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  // A flat series would make span 0 and every point land on the same pixel.
  const span = hi - lo || Math.max(1, hi * 0.01);
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const x = (i) => PAD.left + (length === 1 ? 0 : (i / (length - 1)) * innerW);
  const y = (v) => PAD.top + (1 - (v - lo) / span) * innerH;

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => hi - t * span);

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={height} role="img"
           aria-label="Convergence: best cost found so far at each iteration">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)}
                  stroke="currentColor" strokeOpacity="0.12" strokeWidth="1" />
            <text x={PAD.left - 9} y={y(t) + 4} textAnchor="end"
                  fontSize="12" fill="currentColor" fillOpacity="0.55"
                  fontFamily="DM Mono, ui-monospace, Menlo, monospace">
              {t >= 1000 ? Math.round(t) : t.toFixed(1)}
            </text>
          </g>
        ))}

        {active.map((s) => {
          const d = s.values
            .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
            .join(" ");
          return (
            <path key={s.label} d={d} fill="none" stroke={s.colour} strokeWidth="2.2"
                  strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          );
        })}

        <text x={PAD.left} y={H - 7} fontSize="12" fill="currentColor" fillOpacity="0.55"
              fontFamily="DM Mono, ui-monospace, Menlo, monospace">0</text>
        <text x={W - PAD.right} y={H - 7} textAnchor="end" fontSize="12"
              fill="currentColor" fillOpacity="0.55"
              fontFamily="DM Mono, ui-monospace, Menlo, monospace">
          iteration {length - 1}
        </text>
      </svg>

      <div className="chart-legend">
        {active.map((s) => (
          <span key={s.label} className="legend-item">
            <span className="swatch" style={{ background: s.colour }} />
            {s.label}
            <span className="chart-final">{s.values[s.values.length - 1].toFixed(2)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
