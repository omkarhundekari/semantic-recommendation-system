const stars = [
  [8, 14, 1.4],
  [17, 31, 1],
  [28, 8, 1.2],
  [38, 21, 0.8],
  [49, 11, 1.6],
  [61, 28, 1],
  [72, 7, 1.1],
  [83, 19, 1.5],
  [93, 10, 0.9],
  [12, 67, 1],
  [23, 79, 1.4],
  [35, 61, 0.8],
  [47, 86, 1.3],
  [58, 69, 1],
  [68, 91, 0.9],
  [77, 72, 1.5],
  [89, 84, 1],
  [96, 58, 1.2],
] as const;

export default function SolvynBackdrop() {
  return (
    <div
      aria-hidden="true"
      className="solvyn-cosmos"
    >
      <div className="solvyn-nebula solvyn-nebula-a" />
      <div className="solvyn-nebula solvyn-nebula-b" />
      <div className="solvyn-nebula solvyn-nebula-c" />

      <div className="solvyn-star-field">
        {stars.map(([left, top, size], index) => (
          <span
            key={`${left}-${top}`}
            className="solvyn-star"
            style={{
              left: `${left}%`,
              top: `${top}%`,
              width: `${size}px`,
              height: `${size}px`,
              animationDelay: `${index * -0.37}s`,
            }}
          />
        ))}
      </div>

      <div className="solvyn-orbit solvyn-orbit-a" />
      <div className="solvyn-orbit solvyn-orbit-b" />

      <div className="solvyn-horizon" />
    </div>
  );
}
