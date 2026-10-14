"""The open-source libraries Stemquill is built on, and their licenses.

The Windows app ships these libraries inside it, so it has to ship their licenses too.
`packaging/build.ps1` writes them all to THIRD_PARTY_LICENSES.txt next to Stemquill.exe,
including the optional chord add-on's:

    python -m stemquill.licenses --out dist/Stemquill/THIRD_PARTY_LICENSES.txt --addon dist/addons/chords

The About dialog shows that file. A pip or pipx install has no such file (pip installed each
library with its own license), so the dialog lists what's installed instead.
"""

import argparse
import hashlib
import os
import re
import sys
from importlib import metadata

APP = "stemquill"
FILE_NAME = "THIRD_PARTY_LICENSES.txt"
# Left out of the Windows build by packaging/stemquill.spec, so not shipped
NOT_BUNDLED = {"pip", "setuptools", "wheel", "scikit-learn"}
ADDON_TITLE = "Chord detection add-on (installed only if you tick it in the installer)"

HEADER = """\
Stemquill - open-source licenses
================================

Stemquill is Copyright (c) 2026 Skynr Labs and is licensed under the MIT License.
Source code: https://github.com/skynrlabs/Stemquill

The Windows app also includes the open-source libraries listed below, each under its own
license, and so does the optional chord detection add-on (basic-pitch by Spotify) if you
install it. The full text of every license follows the list.

Many thanks to everyone who builds and maintains these libraries.
"""

_KNOWN_TEXTS = (
    ("Apache License", "Apache-2.0"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("MIT License", "MIT"),
    ("Permission is hereby granted, free of charge", "MIT"),
)
_LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|notice|thirdpartynotices|license_notes)", re.IGNORECASE)


def _canon(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _license_of(dist):
    m = dist.metadata
    expr = m.get("License-Expression")
    if expr:
        return expr
    classifiers = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return ", ".join(classifiers)
    text = (m.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 60:
        return text
    for _, path in _license_files(dist):  # no metadata: recognise the license file itself
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                head = fh.read(2000)
        except OSError:
            continue
        for marker, name in _KNOWN_TEXTS:
            if marker in head:
                return name
    return "see license text"


def _homepage(dist):
    m = dist.metadata
    if m.get("Home-page"):
        return m["Home-page"]
    for url in m.get_all("Project-URL") or []:
        label, _, link = url.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return link.strip()
    return ""


def _wanted(requirement):
    """Whether a Requires-Dist line applies here (skips extras like [dev] and other platforms)."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        return "extra ==" not in requirement
    req = Requirement(requirement)
    return req.marker is None or req.marker.evaluate({"extra": ""})


def _requirement_name(requirement):
    return re.match(r"[A-Za-z0-9._-]+", requirement).group(0)


def libraries(root=APP, exclude=()):
    """Every library `root` needs at run time (not the app itself), sorted by name."""
    skip = {_canon(n) for n in (*NOT_BUNDLED, *exclude)}
    found, todo = {}, [root]
    while todo:
        name = _canon(todo.pop())
        if name in found or name in skip:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[name] = dist
        todo += [_requirement_name(r) for r in dist.requires or [] if _wanted(r)]
    found.pop(_canon(root), None)
    return sorted(found.values(), key=lambda d: _canon(d.metadata["Name"]))


def _license_files(dist):
    """The license, copying and notice files a library ships, without vendored or test copies."""
    for f in dist.files or []:
        p = str(f).replace("\\", "/")
        base = p.rsplit("/", 1)[-1]
        if not _LICENSE_NAME.match(base) or base.endswith((".py", ".pyc")):
            continue
        if any(part in p for part in ("/_vendor/", "/tests/", "/test/")):
            continue
        yield p, f.locate()


def _platform_licenses():
    """Python and Tcl/Tk, which PyInstaller bundles too."""
    out = []
    for name in ("LICENSE.txt", "LICENSE"):
        for base in (
            sys.base_prefix,
            os.path.join(sys.base_prefix, "lib", f"python{sys.version_info[0]}.{sys.version_info[1]}"),
        ):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                out.append((f"Python {sys.version.split()[0]}", "PSF-2.0", "https://www.python.org", [(name, path)]))
                break
        if out:
            break
    try:
        import tkinter

        tcl = tkinter.Tcl()
        for lib in ("tcl_library", "tk_library"):
            try:
                path = os.path.join(tcl.eval(f"set {lib}"), "license.terms")
            except tkinter.TclError:
                continue
            if os.path.isfile(path):
                label = "Tcl" if lib == "tcl_library" else "Tk"
                out.append((label, "TCL", "https://www.tcl-lang.org", [("license.terms", path)]))
    except ImportError:
        pass
    return out


def _entries(dists):
    for d in dists:
        m = d.metadata
        yield f"{m['Name']} {m['Version']}", _license_of(d), _homepage(d), list(_license_files(d))


def addon_libraries(folder, skip=()):
    """The libraries installed in an add-on folder, minus ones the app already has."""
    have = {_canon(n) for n in skip}
    dists = {_canon(d.metadata["Name"]): d for d in metadata.distributions(path=[folder])}
    return [d for name, d in sorted(dists.items()) if name not in have]


def full_text(exclude=(), addon=None):
    """The whole THIRD_PARTY_LICENSES.txt: a list of libraries, then every license text in full."""
    app_libs = libraries(exclude=exclude)
    sections = [("Included in the app", list(_entries(app_libs)) + _platform_licenses())]
    if addon:
        extra = addon_libraries(addon, skip=[d.metadata["Name"] for d in app_libs])
        sections.append((ADDON_TITLE, list(_entries(extra))))
    lines = [HEADER]
    for title, entries in sections:
        lines += ["", title, "-" * len(title)]
        lines += [f"  {name:<34} {lic}" + (f"\n  {'':<34} {url}" if url else "") for name, lic, url, _ in entries]
    seen = set()
    for _, entries in sections:
        for name, lic, url, files in entries:
            lines += ["", "", "=" * 100, f"{name}  ({lic})", *([url] if url else []), "=" * 100]
            if not files:
                lines.append("(no license file shipped; see the project's home page)")
            for label, path in files:
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        text = fh.read().strip()
                except OSError:
                    continue
                digest = hashlib.sha1(text.encode()).hexdigest()
                lines += ["", f"--- {label}", ""]
                lines.append(text if digest not in seen else "(same text as shown above)")
                seen.add(digest)
    return "\n".join(lines) + "\n"


def bundled_file():
    """THIRD_PARTY_LICENSES.txt next to the app, if this is the packaged Windows app."""
    if getattr(sys, "frozen", False):
        path = os.path.join(os.path.dirname(sys.executable), FILE_NAME)
        if os.path.isfile(path):
            return path
    return None


def dialog_text():
    """What the Open-source licenses window shows."""
    path = bundled_file()
    if path:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    lines = [
        HEADER,
        "Installed from source or with pip: each library below was installed with its own license file.",
        "",
    ]
    app_libs = libraries()
    groups = [("", app_libs)]
    try:
        chords = metadata.distribution("basic-pitch")
        have = [d.metadata["Name"] for d in app_libs]
        groups.append(("Optional chord detection:", [chords, *libraries(root="basic-pitch", exclude=have)]))
    except metadata.PackageNotFoundError:
        pass
    for title, dists in groups:
        if title:
            lines += ["", title, ""]
        for name, lic, url, _ in _entries(dists):
            lines.append(f"  {name:<34} {lic}")
            if url:
                lines.append(f"  {'':<34} {url}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Write the licenses of every library the app ships with.")
    p.add_argument("--out", required=True, help="file to write, e.g. dist/Stemquill/THIRD_PARTY_LICENSES.txt")
    p.add_argument("--exclude", action="append", default=[], help="a library left out of the build")
    p.add_argument("--addon", help="folder of the chord add-on, e.g. dist/addons/chords")
    args = p.parse_args(argv)
    text = full_text(exclude=args.exclude, addon=args.addon)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"Wrote {args.out} ({len(libraries(exclude=args.exclude))} libraries)")


if __name__ == "__main__":
    main()
