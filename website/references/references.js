'use strict';
// Metadata stays in static reference entries, separate from the simulated catalog.
const params = new URLSearchParams(location.search);
const query = params.get('q') || '';
const filters = [...document.querySelectorAll('[data-filter]')];
const requested = params.get('topic') || 'all';
const topic = filters.some(a => a.dataset.filter === requested) ? requested : 'all';
document.querySelector('#reference-query').value = query;
document.querySelector('[name="topic"]').value = topic;
for (const link of filters) {
  const next = new URLSearchParams();
  if (query) next.set('q', query);
  if (link.dataset.filter !== 'all') next.set('topic', link.dataset.filter);
  link.href = './' + (next.size ? '?' + next : '');
  if (link.dataset.filter === topic) link.setAttribute('aria-current', 'page');
}
let count = 0;
for (const entry of document.querySelectorAll('.entry')) {
  const match = (topic === 'all' || entry.dataset.topic === topic) &&
    entry.textContent.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  entry.hidden = !match;
  if (match) count++;
}
for (const collection of document.querySelectorAll('.collection')) {
  collection.hidden = ![...collection.querySelectorAll('.entry')].some(e => !e.hidden);
}
document.querySelector('#result-count').textContent = `${count} reference${count === 1 ? '' : 's'}`;
document.querySelector('#empty').hidden = count > 0;
// Full, safe GET navigations make Back/reload recovery native, with no stored user data.
if (params.has('q') || params.has('topic')) document.querySelector('#result-count').focus();
