const viewer = document.getElementById('viewer');
const nativeImage = document.getElementById('native-image');
const viewport = viewer.querySelector('.viewport');
let opener;
document.querySelectorAll('[data-inspect]').forEach(button => {
  button.addEventListener('click', () => {
    const image = document.getElementById(button.dataset.inspect);
    opener = button;
    nativeImage.src = image.src;
    nativeImage.alt = image.alt;
    nativeImage.width = Number(image.getAttribute('width'));
    nativeImage.height = Number(image.getAttribute('height'));
    document.getElementById('viewer-title').textContent = button.getAttribute('aria-label').replace('Inspect ', '').replace(' at native size', '') + ' · Native size';
    viewer.showModal();
    viewport.scrollTop = 0;
    viewport.scrollLeft = 0;
    document.getElementById('close-viewer').focus();
  });
});
document.getElementById('close-viewer').addEventListener('click', () => viewer.close());
viewer.addEventListener('close', () => opener?.focus());
