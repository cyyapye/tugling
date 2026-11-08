const key = 'mend-house-pilot-v1';
const seed = [
  { reference:'1204', name:'Maya Lin', email:'maya@example.test', category:'Clothing', item:'Jacket zip catches halfway', status:'expected' },
  { reference:'1205', name:'Sam Bell', email:'sam@example.test', category:'Small appliance', item:'Desk lamp switch is loose', status:'arrived' },
  { reference:'1206', name:'Dev Shah', email:'dev@example.test', category:'Other household item', item:'Wooden stool with a wobbly leg', status:'expected' }
];
function readBookings() { return JSON.parse(localStorage.getItem(key) || JSON.stringify(seed)); }
function writeBookings(bookings) { localStorage.setItem(key, JSON.stringify(bookings)); }
function cell(text) { const td = document.createElement('td'); td.textContent = text; return td; }
const page = document.body.dataset.page;
if (page === 'booking') {
  document.querySelector('#booking-form').addEventListener('submit', event => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const bookings = readBookings();
    const reference = String(Math.max(1200, ...bookings.map(booking => Number(booking.reference))) + 1);
    bookings.push({ reference, name:fields.get('name').trim(), email:fields.get('email').trim(), category:fields.get('category'), item:fields.get('item').trim(), status:'expected' });
    writeBookings(bookings);
    event.currentTarget.hidden = true;
    const result = document.querySelector('#booking-result');
    result.textContent = `Your place is reserved. Keep reference ${reference} and bring it on Thursday at 6 pm.`;
    result.hidden = false;
  });
}
if (page === 'desk') {
  function renderDesk() {
    const bookings = readBookings();
    document.querySelector('#expected').textContent = bookings.length;
    document.querySelector('#arrived').textContent = bookings.filter(booking => booking.status === 'arrived').length;
    const filter = document.querySelector('#status-filter').value;
    const visible = bookings.filter(booking => filter === 'all' || booking.status === filter);
    const rows = document.querySelector('#guest-rows');
    rows.replaceChildren();
    visible.forEach(booking => {
      const row = document.createElement('tr');
      const guest = cell(booking.name);
      const category = document.createElement('small'); category.textContent = booking.category; guest.append(category);
      const state = document.createElement('span'); state.className = `badge ${booking.status}`; state.textContent = booking.status === 'arrived' ? 'Arrived' : 'Expected';
      const statusCell = cell(''); statusCell.append(state);
      const actionCell = cell('');
      if (booking.status !== 'arrived') {
        const button = document.createElement('button'); button.className = 'button small secondary'; button.textContent = 'Mark arrived';
        button.setAttribute('aria-label', `Mark ${booking.name} arrived`);
        button.addEventListener('click', () => { booking.status = 'arrived'; writeBookings(bookings); renderDesk(); document.querySelector('#desk-status').textContent = `${booking.name} marked arrived.`; });
        actionCell.append(button);
      }
      row.append(guest, cell(booking.item), cell(booking.reference), statusCell, actionCell); rows.append(row);
    });
    document.querySelector('#empty-list').hidden = visible.length > 0;
  }
  document.querySelector('#status-filter').addEventListener('change', renderDesk);
  document.querySelector('#print-list').addEventListener('click', () => window.print());
  renderDesk();
}
if (page === 'arrivals') {
  document.querySelector('#arrival-form').addEventListener('submit', event => {
    event.preventDefault();
    const bookings = readBookings();
    const booking = bookings.find(candidate => candidate.reference === document.querySelector('#reference').value.trim());
    const result = document.querySelector('#arrival-result');
    if (!booking) { result.textContent = 'We couldn’t find that reference. Please ask the host for help.'; return; }
    booking.status = 'arrived'; writeBookings(bookings);
    result.textContent = `Thanks, ${booking.name}. Please take a seat near the welcome desk.`;
    event.currentTarget.reset();
  });
}
