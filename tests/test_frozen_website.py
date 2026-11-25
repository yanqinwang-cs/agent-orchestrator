"""Offline HTTP boundary checks for the local sample; no optional browser dependency."""

import base64
import functools
import hashlib
import json
import re
import struct
import threading
import unittest
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

WEBSITE = Path(__file__).resolve().parents[1] / "website"
SAMPLE = "samples/four-instructed-runs/"
ORIGINAL_SHA = "dcea2bbb71fec9ec1a1726b40f4feb6cb5f989a7f0f4433d31f27c0791f6793a"


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def attributes(self, tag):
        return [attrs for name, attrs in self.elements if name == tag]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class FrozenWebsiteTests(unittest.TestCase):
    server: ThreadingHTTPServer
    thread: threading.Thread
    base: str

    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=str(WEBSITE))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def fetch(self, path):
        with urlopen(urljoin(self.base, path), timeout=5) as response:
            self.assertEqual(response.status, 200)
            return response.read()

    def test_open_and_download_original_are_exact(self):
        document = Document(self.fetch(SAMPLE).decode())
        originals = [
            a for a in document.attributes("a") if a.get("href") == "DEFAULT-EVIDENCE.html"
        ]
        self.assertEqual(len(originals), 2)
        self.assertEqual(originals[1]["download"], "DEFAULT-EVIDENCE.html")
        for anchor in originals:
            downloaded = self.fetch(urljoin(SAMPLE, anchor["href"]))
            self.assertEqual(len(downloaded), 4551392)
            self.assertEqual(hashlib.sha256(downloaded).hexdigest(), ORIGINAL_SHA)
            self.assertEqual(downloaded, (WEBSITE / SAMPLE / anchor["href"]).read_bytes())

    def test_all_eight_served_images_match_original_and_provenance(self):
        original = self.fetch(SAMPLE + "DEFAULT-EVIDENCE.html")
        embedded = re.findall(rb"data:image/png;base64,([A-Za-z0-9+/=]+)", original)
        provenance = json.loads(self.fetch(SAMPLE + "PROVENANCE.json"))
        records = provenance["embedded_pngs"]
        self.assertEqual(len(embedded), 8)
        self.assertEqual(len(records), 8)
        document = Document(self.fetch(SAMPLE).decode())
        gallery = {image["src"]: image for image in document.attributes("img") if "src" in image}
        self.assertEqual(len(gallery), 8)
        for record, encoded in zip(records, embedded, strict=True):
            path = f"images/{record['name']}.png"
            with self.subTest(image=path):
                data = self.fetch(SAMPLE + path)
                self.assertEqual(data, base64.b64decode(encoded, validate=True))
                self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                dimensions = struct.unpack(">II", data[16:24])
                self.assertEqual(dimensions, (record["width"], record["height"]))
                self.assertEqual(
                    dimensions, (int(gallery[path]["width"]), int(gallery[path]["height"]))
                )
                self.assertTrue(gallery[path]["alt"])

    def test_new_local_navigation_and_assets_resolve(self):
        for page in [SAMPLE, SAMPLE + "REVIEW.html"]:
            document = Document(self.fetch(page).decode())
            for tag, attr in [("a", "href"), ("link", "href"), ("script", "src")]:
                for element in document.attributes(tag):
                    target = element[attr]
                    self.assertFalse(target.startswith(("http:", "https:", "//")))
                    self.fetch(urljoin(page, target))
        original = Document(self.fetch(SAMPLE + "DEFAULT-EVIDENCE.html").decode())
        for anchor in original.attributes("a"):
            self.fetch(urljoin(SAMPLE + "DEFAULT-EVIDENCE.html", anchor["href"]))
        self.fetch("discovery.html")


if __name__ == "__main__":
    unittest.main()
