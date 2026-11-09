export function Overview({ visits, openRequests }) {
  return <main><h1>Overview</h1><div className="summary">
    <section><h2>Visits today</h2><strong>{visits}</strong><p>Booked visits for this location.</p></section>
    <section><h2>Open requests</h2><strong>{openRequests}</strong><p>Requests awaiting triage.</p></section>
  </div></main>;
}
