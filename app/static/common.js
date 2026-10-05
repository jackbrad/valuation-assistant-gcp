// Shared by every page: citation page viewer and the light/dark switch.
const byId = (id) => document.getElementById(id);

// Citation viewer
document.addEventListener('click', (e) => {
  const c = e.target.closest('.cite');
  if (!c) return;
  byId('viewerTitle').textContent = `${c.dataset.doc} · page ${c.dataset.page}`;
  byId('viewerImg').src = `/static/doc_pages/${c.dataset.doc}-${c.dataset.page}.png`;
  byId('viewerImg').alt = `${c.dataset.doc} page ${c.dataset.page}`;
  byId('viewer').hidden = false;
  byId('viewerClose').focus();
});
const closeViewer = () => { byId('viewer').hidden = true; };
byId('viewerClose').addEventListener('click', closeViewer);
byId('viewer').addEventListener('click', (e) => { if (e.target === byId('viewer')) closeViewer(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeViewer(); });

// Theme toggle (light / dark), remembered per browser
function syncThemeIcon() {
  byId('themeIcon').textContent = document.documentElement.dataset.theme === 'dark' ? 'light_mode' : 'dark_mode';
}
byId('themeBtn').addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('clearline-theme', next); } catch (e) {}
  syncThemeIcon();
});
syncThemeIcon();

