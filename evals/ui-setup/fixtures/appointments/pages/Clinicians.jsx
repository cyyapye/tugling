import { Button, EmptyState, Field } from "../ui";

export function Clinicians({ rows, query, onQuery, onInvite, pending, error }) {
  if (pending) return <p role="status">Loading clinicians…</p>;
  if (error) return <p role="alert">Clinicians could not load. Try again.</p>;
  return <main><h1>Clinicians</h1>
    <Field id="clinician-query" label="Find a clinician" value={query} onChange={onQuery}
      hint="Search by clinician name." />
    {rows.length ? <ul>{rows.map(row => <li key={row.id}>{row.name}</li>)}</ul>
      : <EmptyState title="No clinicians" detail="Invite a clinician to get started."
        action={<Button onClick={onInvite}>Invite clinician</Button>} />}
  </main>;
}
