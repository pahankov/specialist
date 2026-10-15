interface StarsProps {
  value: number;
  size?: number;
}

/** Fractional star fill (4.8 paints 96% of the fifth star gold). */
function Stars({ value, size = 20 }: StarsProps) {
  const pct = Math.max(0, Math.min(100, (value / 5) * 100));
  const row = (filled: boolean) => (
    <span
      aria-hidden
      style={{
        display: 'inline-flex',
        gap: 2,
        fontSize: size,
        lineHeight: 1,
        color: filled ? '#f5a623' : '#d8dce3',
      }}
    >
      {['★', '★', '★', '★', '★']}
    </span>
  );
  return (
    <span
      role="img"
      aria-label={`Оценка ${value} из 5`}
      title={`${value} из 5`}
      style={{ position: 'relative', display: 'inline-block', lineHeight: 1 }}
    >
      {row(false)}
      <span
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
          width: `${pct}%`,
          whiteSpace: 'nowrap',
        }}
      >
        {row(true)}
      </span>
    </span>
  );
}

export default Stars;
