type Holding = { id: string; name: string; value: string };

export function Holdings({ rows }: { rows: Holding[] }) {
  return (
    <section className="holdings" aria-labelledby="holdings-title">
      <h2 id="holdings-title">Holdings</h2>
      <div className="holdingsTable">
        {rows.map((row) => (
          <div className="holdingRow" key={row.id}>
            <span>{row.name}</span>
            <span>{row.value}</span>
            <button type="button">View</button>
          </div>
        ))}
      </div>
    </section>
  );
}
