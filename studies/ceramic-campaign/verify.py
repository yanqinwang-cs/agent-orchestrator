"""Isolated local browser verification; needs preinstalled websockets and Chrome.

Usage: python3 studies/ceramic-campaign/verify.py \
    --evidence /absolute/outside/project --phase initial
No downloads, installations, live accounts or project runtime changes.
"""

import argparse
import asyncio
import base64
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import websockets
from PIL import Image

ROOT = Path(__file__).resolve().parent


class CDP:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0

    async def call(self, method, params=None):
        self.sequence += 1
        message_id = self.sequence
        await self.socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            reply = json.loads(await asyncio.wait_for(self.socket.recv(), timeout=15))
            if reply.get("id") == message_id:
                if "error" in reply:
                    raise RuntimeError(reply)
                return reply.get("result", {})

    async def evaluate(self, expression):
        result = await self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        assert "exceptionDetails" not in result, result
        return result["result"].get("value")

    async def key(self, key, shift=False):
        code = {"Tab": 9, "Enter": 13, "Escape": 27, "Space": 32}[key]
        for kind in ["keyDown", "keyUp"]:
            params = {
                "type": kind,
                "key": " " if key == "Space" else key,
                "code": key,
                "windowsVirtualKeyCode": code,
                "modifiers": 8 if shift else 0,
            }
            if kind == "keyDown" and key in ["Enter", "Space"]:
                params["text"] = "\r" if key == "Enter" else " "
            await self.call("Input.dispatchKeyEvent", params)

    async def contrast(self, out, name):
        nodes = await self.evaluate(
            """(()=>{
              let w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),n,a=[];
              while(n=w.nextNode()){
                if(!n.textContent.trim() ||
                   n.parentElement.closest('script,style,.visually-hidden,.skip'))continue;
                if(document.querySelector('dialog').open !==
                   !!n.parentElement.closest('dialog'))continue;
                let s=getComputedStyle(n.parentElement),r=document.createRange();
                r.selectNodeContents(n);
                for(let b of r.getClientRects())if(b.width&&b.height)a.push({
                  text:n.textContent.trim(),color:s.color,
                  size:parseFloat(s.fontSize),weight:s.fontWeight,
                  rect:{x:b.x+scrollX,y:b.y+scrollY,width:b.width,height:b.height}
                });
              }
              return a;
            })()"""
        )
        await self.evaluate(
            "window.hideText=document.createElement('style');hideText.textContent='*{color:transparent!important;text-shadow:none!important}';document.head.append(hideText)"
        )
        await self.picture(out / f"{name}-backgrounds.png", True)
        await self.evaluate("hideText.remove()")
        image = Image.open(out / f"{name}-backgrounds.png").convert("RGB")
        dpr = await self.evaluate("devicePixelRatio")

        def lum(rgb):
            values = [v / 255 for v in rgb]
            linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
            return sum(v * w for v, w in zip(linear, [0.2126, 0.7152, 0.0722], strict=True))

        def ratio(a, b):
            x, y = sorted([lum(a), lum(b)])
            return (y + 0.05) / (x + 0.05)

        results = []
        for n in nodes:
            color = tuple(map(int, n["color"].split("(")[1].split(")")[0].split(", ")[:3]))
            b = n["rect"]
            x0, y0 = max(0, int(b["x"] * dpr)), max(0, int(b["y"] * dpr))
            x1, y1 = (
                min(image.width, int((b["x"] + b["width"]) * dpr)),
                min(image.height, int((b["y"] + b["height"]) * dpr)),
            )
            pixels = image.crop((x0, y0, x1, y1))
            colors = pixels.getcolors(pixels.width * pixels.height)
            worst = min((ratio(color, c), c) for _, c in colors)
            n["minimum_contrast"] = round(worst[0], 3)
            n["worst_background"] = worst[1]
            n["required"] = (
                3
                if n["size"] >= 24
                or (n["size"] >= 18.67 and n["weight"].isdigit() and int(n["weight"]) >= 700)
                else 4.5
            )
            assert worst[0] >= n["required"], n
            results.append(n)
        return results

    async def picture(self, path, full=False):
        params = {"format": "png", "captureBeyondViewport": full}
        if full:
            size = (await self.call("Page.getLayoutMetrics"))["cssContentSize"]
            params["clip"] = {
                "x": 0,
                "y": 0,
                "width": size["width"],
                "height": size["height"],
                "scale": 1,
            }
        image = await self.call("Page.captureScreenshot", params)
        path.write_bytes(base64.b64decode(image["data"]))


async def inspect(port, out, phase):
    pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
    async with websockets.connect(
        pages[0]["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024
    ) as socket:
        cdp = CDP(socket)
        await cdp.call("Page.enable")
        await cdp.call("Runtime.enable")
        await cdp.call("Page.bringToFront")
        await cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
        report = {
            "phase": phase,
            "browser": json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version"))[
                "Browser"
            ],
            "views": [],
        }
        for name, width, height, zoom in [
            ("desktop", 1440, 1080, 1),
            ("phone", 390, 844, 1),
            ("small", 320, 844, 1),
            ("zoom200", 720, 540, 2),
        ]:
            await cdp.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            )
            navigation = await cdp.call("Page.navigate", {"url": inspect.url + "/"})
            print("Navigate", navigation, flush=True)
            assert "errorText" not in navigation, navigation
            for _ in range(100):
                if await cdp.evaluate(
                    "document.readyState === 'complete' && !!document.querySelector('.scene img')"
                    " && document.querySelector('.scene img').complete"
                ):
                    break
                await asyncio.sleep(0.05)
            loaded = await cdp.evaluate(
                "document.querySelector('.scene img').decode().then(()=>true)"
            )
            assert loaded
            # 200% desktop zoom: a 1440x1080 physical window has 720x540 CSS pixels.
            # The screenshot is expanded to those physical pixels via CDP scale.
            if zoom == 2:
                await cdp.call(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": width, "height": height, "deviceScaleFactor": 2, "mobile": False},
                )
            await cdp.picture(out / f"{phase}-{name}.png")
            await cdp.picture(out / f"{phase}-{name}-full.png", True)
            state = await cdp.evaluate(
                """JSON.stringify({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth,image:{width:document.images[0].naturalWidth,height:document.images[0].naturalHeight},text:document.body.innerText,boxes:[...document.querySelectorAll('h1,.proposition,.offer,button,footer')].map(e=>({tag:e.tagName,box:e.getBoundingClientRect().toJSON(),font:getComputedStyle(e).fontSize}))})"""
            )
            state = json.loads(state)
            state["contrast"] = await cdp.contrast(out, f"{phase}-{name}")
            assert state["width"] == width and state["height"] == height
            assert state["scrollWidth"] == width, state
            assert state["image"] == {"width": 2400, "height": 3600}
            for forbidden in [
                "palette",
                "hypothes",
                "gradient",
                "R03",
                "image-derived",
                "candidate",
                "contrast",
            ]:
                assert forbidden not in state["text"].lower(), forbidden
            assert "S$90" in state["text"] and "Not for sale" in state["text"]
            # Keyboard activation, containment, Escape and return, then pointer + Close.
            await cdp.evaluate("document.querySelector('.skip').focus()")
            await cdp.key("Enter")
            await cdp.key("Tab")
            assert await cdp.evaluate("document.activeElement.id === 'details'")
            await cdp.picture(out / f"{phase}-{name}-focus.png")
            await cdp.key("Enter")
            await asyncio.sleep(0.1)
            print(
                "Keyboard state",
                await cdp.evaluate(
                    "JSON.stringify({active:document.activeElement.outerHTML,open:document.querySelector('dialog').open,focus:document.hasFocus()})"
                ),
                flush=True,
            )
            assert await cdp.evaluate("document.querySelector('dialog').open")
            assert await cdp.evaluate("document.activeElement.textContent === 'Close'")
            containment_checks = []
            for shift in [False, False, False, True, True, True]:
                await cdp.key("Tab", shift)
                containment_checks.append(
                    await cdp.evaluate(
                        "document.querySelector('dialog').contains(document.activeElement)"
                    )
                )
            contained = all(containment_checks)
            state["tab_checks"] = containment_checks
            print("Dialog containment", name, contained, flush=True)
            if phase == "corrected":
                assert contained
            await cdp.evaluate("document.querySelector('dialog button').focus()")
            await cdp.picture(out / f"{phase}-{name}-dialog.png")
            state["dialog_contrast"] = await cdp.contrast(out, f"{phase}-{name}-dialog")
            ax = await cdp.call("Accessibility.getFullAXTree")
            assert any(
                n.get("role", {}).get("value") == "dialog"
                and n.get("name", {}).get("value") == "Ember vase"
                for n in ax["nodes"]
            )
            assert any(
                n.get("role", {}).get("value") == "button"
                and n.get("name", {}).get("value") == "Close"
                for n in ax["nodes"]
            )
            (out / f"{phase}-{name}-accessibility.json").write_text(json.dumps(ax, indent=2))
            await cdp.key("Escape")
            assert await cdp.evaluate(
                "!document.querySelector('dialog').open && document.activeElement.id==='details'"
            )
            await cdp.evaluate(
                "document.querySelector('#details').scrollIntoView({block:'center'})"
            )
            point = await cdp.evaluate(
                "(()=>{let r=document.querySelector('#details').getBoundingClientRect();"
                "return {x:r.x+r.width/2,y:r.y+r.height/2}})()"
            )
            for kind in ["mousePressed", "mouseReleased"]:
                await cdp.call(
                    "Input.dispatchMouseEvent",
                    {"type": kind, **point, "button": "left", "clickCount": 1},
                )
            assert await cdp.evaluate("document.querySelector('dialog').open")
            await cdp.key("Enter")
            assert await cdp.evaluate(
                "!document.querySelector('dialog').open && document.activeElement.id==='details'"
            )
            state["tab_containment"] = contained
            state["interaction"] = (
                "Keyboard skip/Tab/Enter, modal focus, Escape/focus return, pointer open, "
                "Close/focus return passed; Tab containment recorded separately"
            )
            report["views"].append(state)
        # Native accessibility names/roles are recorded above; no screen-reader claim.
        report["photo_sha256"] = hashlib.sha256(
            (ROOT / "site/ceramic.jpg").read_bytes()
        ).hexdigest()
        (out / f"{phase}-checks.json").write_text(json.dumps(report, indent=2) + "\n")
        if inspect.record:
            await record_demo(cdp, out)
        print(
            json.dumps(
                {
                    "phase": phase,
                    "views": [
                        {
                            "width": v["width"],
                            "height": v["height"],
                            "overflow": v["scrollWidth"] - v["width"],
                            "interaction": v["interaction"],
                        }
                        for v in report["views"]
                    ],
                },
                indent=2,
            )
        )


async def record_demo(cdp, out):
    """Capture a real-time keyboard journey; frames are intermediate, not deliverables."""
    await cdp.call(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 1280,
            "height": 720,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    await cdp.call("Page.navigate", {"url": inspect.url + "/"})
    await asyncio.sleep(0.5)
    await cdp.evaluate("document.querySelector('.scene img').decode()")
    await cdp.evaluate("document.querySelector('#details').scrollIntoView({block:'center'});")
    await cdp.evaluate("document.querySelector('#details').focus()")
    with tempfile.TemporaryDirectory(prefix="ago108-recording-") as tmp:
        folder = Path(tmp)
        started = time.monotonic()
        actions = [(1.5, "Enter"), (3, "Tab"), (4, "Escape"), (5.5, "Space"), (7, "Enter")]
        frames = []
        while time.monotonic() - started < 8.5:
            elapsed = time.monotonic() - started
            while actions and elapsed >= actions[0][0]:
                _, key = actions.pop(0)
                await cdp.key(key)
            path = folder / f"frame-{len(frames):04}.png"
            await cdp.picture(path)
            frames.append((path, elapsed))
            await asyncio.sleep(0.12)
        # The existing bundled encoder has no H.264; use a once-playing GIF,
        # without installing anything. Frame timing preserves the real journey.
        images = [Image.open(p).convert("RGB") for p, _ in frames]
        durations = [
            max(100, int((frames[i + 1][1] - elapsed) * 1000)) if i + 1 < len(frames) else 150
            for i, (_, elapsed) in enumerate(frames)
        ]
        images[0].save(
            out / "dialog-demo.gif",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            optimize=True,
            disposal=1,
        )
        assert (out / "dialog-demo.gif").stat().st_size < 8 * 1024 * 1024
        # The poster is an actual open-dialog frame from this recording.
        poster = min(frames, key=lambda f: abs(f[1] - 2.5))[0]
        shutil.copyfile(poster, out / "dialog-demo-poster.png")
    assert await cdp.evaluate("!document.querySelector('dialog').open")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--phase", choices=["initial", "corrected"], required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument(
        "--chrome",
        default=str(
            Path.home()
            / "Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64"
            / "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        ),
    )
    args = parser.parse_args()
    out = args.evidence.resolve()
    assert not out.is_relative_to(ROOT.parents[1]), "Evidence must stay outside the working copy"
    out.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT / "site")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    inspect.url = f"http://127.0.0.1:{server.server_port}"
    inspect.record = args.record
    assert urllib.request.urlopen(inspect.url).status == 200
    print("Serving", inspect.url, flush=True)
    with tempfile.TemporaryDirectory(prefix="ago108-browser-") as profile:
        chrome = subprocess.Popen(
            [
                args.chrome,
                "--headless=new",
                f"--user-data-dir={profile}",
                "--remote-debugging-port=0",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--no-proxy-server",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            active = Path(profile) / "DevToolsActivePort"
            for _ in range(100):
                if active.exists():
                    break
                time.sleep(0.05)
            port = int(active.read_text().splitlines()[0])
            asyncio.run(inspect(port, out, args.phase))
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)
            server.shutdown()


if __name__ == "__main__":
    main()
