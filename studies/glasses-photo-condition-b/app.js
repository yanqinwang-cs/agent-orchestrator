'use strict';
const dialog = document.querySelector('dialog');
const trigger = document.querySelector('.view-frame');
trigger.addEventListener('click', () => dialog.showModal());
document.querySelector('.close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => {
  if (event.target !== dialog) return;
  const box = dialog.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
});
