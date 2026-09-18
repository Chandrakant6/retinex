export const LEVEL_COLORS = ['#2e7d46', '#8a9c1e', '#c99a1e', '#d9722c', '#b13a3a'];
export const LEVEL_LABELS = ['No DR', 'Mild', 'Moderate', 'Severe', 'PDR'];

/**
 * Minimal dependency-free multi-line chart (no charting library — this
 * project has three data series on a shared time axis, which plain SVG
 * handles fine without pulling in Recharts/D3 just for this).
 */
export function LineChart({ series, width = 640, height = 220, xLabel, yLabel }) {
  const pad = { top: 12, right: 16, bottom: 28, left: 44 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const allPoints = series.flatMap((s) => s.points);
  const maxX = Math.max(1, ...allPoints.map((p) => p.x));
  const maxY = Math.max(1, ...allPoints.map((p) => p.y));

  const sx = (x) => pad.left + (x / maxX) * innerW;
  const sy = (y) => pad.top + innerH - (y / maxY) * innerH;

  const pathFor = (points) =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(' ');

  const yTicks = 4;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={yLabel}>
      {Array.from({ length: yTicks + 1 }).map((_, i) => {
        const val = (maxY / yTicks) * i;
        const y = sy(val);
        return (
          <g key={i}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e9edeb" strokeWidth="1" />
            <text x={pad.left - 8} y={y + 4} fontSize="10" fill="#8a9793" textAnchor="end">
              {Math.round(val)}
            </text>
          </g>
        );
      })}
      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} stroke="#c7d1ce" />
      <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} stroke="#c7d1ce" />
      <text x={pad.left} y={height - 6} fontSize="10" fill="#8a9793">{xLabel}</text>

      {series.map((s) => (
        <path key={s.name} d={pathFor(s.points)} fill="none" stroke={s.color} strokeWidth="2" />
      ))}
    </svg>
  );
}
