import { Button } from "../ui";

export function Appointments({ rows, query, onQuery, onCreate, pending, error }) {
  if (pending) return <p role="status">Loading appointments…</p>;
  if (error) return <p role="alert">Appointments could not load. Try again.</p>;
  return <main><h1>Appointments</h1>
    <div className="field"><label htmlFor="patient-query">Find a patient</label>
      <input id="patient-query" value={query} onChange={onQuery} />
      <p>Search by patient name.</p></div>
    {rows.length ? <ul>{rows.map(row => <li key={row.id}>{row.name}</li>)}</ul>
      : <section className="empty"><h2>No appointments</h2><p>Start by booking a visit.</p>
        <Button onClick={onCreate}>Book visit</Button></section>}
  </main>;
}
