const trigger = document.querySelector('#details');
const detail = document.querySelector('dialog');
trigger.addEventListener('click', () => detail.showModal());
detail.addEventListener('close', () => trigger.focus());
// This dialog has a single focusable control. Keep both Tab directions on it.
detail.addEventListener('keydown', (event) => {
  if (event.key === 'Tab') {
    event.preventDefault();
    detail.querySelector('button').focus();
  }
});
