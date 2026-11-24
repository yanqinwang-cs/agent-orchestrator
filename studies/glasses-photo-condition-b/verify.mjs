// Dependency-free browser integration check. Requires an isolated Chrome CDP endpoint.
// node verify.mjs [debug-port=9444] [site=http://127.0.0.1:8766]
import assert from 'node:assert/strict';
const port = process.argv[2] || '9444';
const site = process.argv[3] || 'http://127.0.0.1:8766';
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {method: 'PUT'})).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(resolve => { ws.onopen = resolve; });
let id = 0;
const pending = new Map();
const problems = [];
ws.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown' || message.method === 'Network.loadingFailed') problems.push(message);
  if (message.id) {
    const callback = pending.get(message.id);
    pending.delete(message.id);
    message.error ? callback.reject(message.error) : callback.resolve(message.result);
  }
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const callId = ++id;
  pending.set(callId, {resolve, reject});
  ws.send(JSON.stringify({id: callId, method, params}));
});
const read = async expression => {
  const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  assert.ok(!result.exceptionDetails, 'Browser evaluation must not throw');
  return result.result.value;
};
const key = async (key, code, keyCode, modifiers = 0) => {
  const params = {key, code, windowsVirtualKeyCode: keyCode, modifiers};
  await send('Input.dispatchKeyEvent', {type: 'keyDown', ...params, ...(key === 'Enter' ? {text: '\r'} : {})});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', ...params});
};
const click = async selector => {
  await read(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'})`);
  const point = await read(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await send('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
  await send('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
};
try {
  await send('Page.enable');
  await send('Page.bringToFront');
  await send('Runtime.enable');
  await send('Network.enable');
  for (const [width, height] of [[1440,1080],[390,844],[320,844],[650,900],[768,1024],[1024,768]]) {
    await send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
    await send('Page.navigate', {url: site});
    await read('new Promise(r=>document.readyState==="complete"?r():window.addEventListener("load",r,{once:true}))');
    await read('document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.decode())))');
    const metrics = await read(`({width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,images:[...document.images].every(i=>i.complete&&i.naturalWidth>0&&i.alt.length>0),name:document.querySelector('#frame-name').textContent,price:document.querySelector('.price').textContent})`);
    assert.equal(metrics.width, width);
    assert.equal(metrics.height, height);
    assert.equal(metrics.overflow, false);
    assert.equal(metrics.images, true);
    assert.match(metrics.name, /The Round/);
    assert.match(metrics.price, /S\$120/);
    // Use real forward tab navigation, not programmatic focus or browser-chrome Shift+Tab.
    for (let i = 0; i < 5 && await read('document.activeElement.className') !== 'view-frame'; i++) {
      await key('Tab', 'Tab', 9);
    }
    assert.equal(await read('document.activeElement.className'), 'view-frame');
    const focusStyle = await read('getComputedStyle(document.activeElement).outlineStyle');
    assert.notEqual(focusStyle, 'none');
    await key('Enter', 'Enter', 13);
    assert.equal(await read('document.querySelector("dialog").open'), true);
    assert.equal(await read('document.activeElement.className'), 'close');
    assert.equal(await read('document.querySelector("dialog").getAttribute("aria-labelledby")'), 'dialog-title');
    // A native modal keeps tab navigation out of the campaign behind it.
    for (let i = 0; i < 3; i++) {
      await key('Tab', 'Tab', 9);
      assert.equal(await read('!document.activeElement.closest(".page")'), true);
    }
    await key('Escape', 'Escape', 27);
    assert.equal(await read('document.querySelector("dialog").open'), false);
    assert.equal(await read('document.activeElement.className'), 'view-frame');
    await click('.view-frame');
    assert.equal(await read('document.querySelector("dialog").open'), true);
    await click('.close');
    assert.equal(await read('document.querySelector("dialog").open'), false);
    console.log(JSON.stringify({viewport: [width,height], metrics, keyboard: 'Enter opens; modal tab containment; Escape closes and restores focus', pointer: 'View frame opens; Close dismisses', result:'passed'}));
  }
  assert.equal(problems.length, 0, 'No browser exceptions or failed resource requests');
  console.log('All browser integration checks passed. Visual quality is a separate assessment.');
} finally {
  await send('Page.close');
  ws.close();
}
