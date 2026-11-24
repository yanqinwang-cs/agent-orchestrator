'use strict';
// Source categories are deliberately empty. The frozen study is not a source sample.
const params = new URLSearchParams(location.search);
const query = params.get('q') || '';
const links = [...document.querySelectorAll('[data-purpose]')];
const requested = params.get('purpose') || 'all';
const purpose = links.some(link => link.dataset.purpose === requested) ? requested : 'all';
document.querySelector('#reference-query').value = query;
document.querySelector('[name="purpose"]').value = purpose;
for (const link of links) {
  const next = new URLSearchParams();
  if (query) next.set('q', query);
  if (link.dataset.purpose !== 'all') next.set('purpose', link.dataset.purpose);
  link.href = './' + (next.size ? '?' + next : '');
  link.removeAttribute('aria-current');
  if (link.dataset.purpose === purpose) link.setAttribute('aria-current', 'page');
}
const label = links.find(link => link.dataset.purpose === purpose).textContent.replace(' · 0', '');
document.querySelector('#result-count').textContent = `0 source samples · ${label}`;
document.querySelector('#clear-filters').hidden = !query && purpose === 'all';
const study = document.querySelector('.entry');
const matches = study.textContent.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
study.hidden = !matches;
document.querySelector('#study-count').textContent = matches ? '1 study' : '0 studies';
document.querySelector('#study-empty').hidden = matches;
// Native GET navigation retains submitted search and purpose on Back and reload.
if (params.has('q') || params.has('purpose')) document.querySelector('#result-count').focus();
