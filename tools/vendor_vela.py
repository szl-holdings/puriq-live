"""Acquire an exact Vela browser distribution; no package scripts are executed.

The archive SHA-512 and the browser file's SHA-256 must match the reviewed
0.7.3 release. Credentials, redirects, alternate registries and floating versions
are intentionally unsupported. Run during the image build, never at page load.
"""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = "https://registry.npmjs.org/@luxalgo/vela/-/vela-0.7.3.tgz"
SHA512 = "SYJ1gUVBluFlPjOcWHKsu4zchkMhxYw6DDIuhuiXEBHinGQkkAwC//XvaXLWzYo2i02L7OZG5FSCfFcZCgIzWw=="
PINS = {
 "LICENSE": "1eb85fc97224598dad1852b5d6483bbcf0aa8608790dcc657a5a2a761ae9c8c6",
 "NOTICE": "3ee3e438cbffc0937b2e0ddbf27db2f8055fa486e0d9858f6d805ee6ce97fcd8",
 "dist/vela.global.min.js": "ea73dafeffb2f0aa14ca6163e7e427810ead692a29a552a426a774de62e520dd",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("distribution redirects are forbidden")


def install(raw: bytes, destination: Path) -> None:
    if len(raw) > 8_000_000 or base64.b64encode(hashlib.sha512(raw).digest()).decode() != SHA512:
        raise ValueError("Vela archive integrity mismatch")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for name in ("dist/vela.global.min.js", "LICENSE", "NOTICE"):
            member = archive.getmember("package/" + name)
            if not member.isfile() or member.size > 2_000_000:
                raise ValueError("invalid Vela distribution member")
            data = archive.extractfile(member).read(2_000_001)
            data.decode("utf-8")
            if name in PINS and hashlib.sha256(data).hexdigest() != PINS[name]:
                raise ValueError("Vela browser distribution digest mismatch")
            files[Path(name).name] = data
    if destination.exists():
        raise ValueError("refusing to overwrite an existing vendor directory")
    destination.mkdir(parents=True)
    for name, data in files.items():
        (destination / name).write_bytes(data)


def main():
    request = urllib.request.Request(URL, headers={"User-Agent": "SZL-PURIQ-build/1.0"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(8_000_001)
    install(raw, Path(__file__).resolve().parents[1] / "static" / "vendor" / "vela")


if __name__ == "__main__":
    main()
