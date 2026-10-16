#!/usr/bin/env python3
"""Resolve a released upstream image and prepare a tested Umbrel update."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = "milind-soni/OpenMausBot"


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--version")
    args = parser.parse_args()
    headers = {"User-Agent": "umbrel-openmausbot-updater"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request("https://api.github.com/repos/" + REPO + "/releases/latest", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    tag = args.version or release["tag_name"]
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
        raise SystemExit("Expected a stable upstream release version")
    version = tag.removeprefix("v")
    current = json.loads((ROOT / "upstream.json").read_text())
    changed = version != current["version"] or args.force
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("changed=" + str(changed).lower() + "\n")
    print("Installed package upstream: " + current["version"] + "; latest release: " + version)
    if not changed or not args.apply:
        return
    image_tag = "ghcr.io/milind-soni/openmausbot-cloud-home:v" + version
    digest = json.loads(run("docker", "buildx", "imagetools", "inspect", image_tag, "--format", "{{json .Manifest.Digest}}"))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise SystemExit("Registry did not return an image digest")
    image = image_tag.split(":v")[0] + "@" + digest
    run("docker", "pull", "--platform", "linux/amd64", image)
    labels = json.loads(run("docker", "image", "inspect", image, "--format", "{{json .Config.Labels}}"))
    revision = labels.get("org.opencontainers.image.revision", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit("Upstream image is missing its source revision")
    # Check the exact source revision used to build the image, not main.
    with urllib.request.urlopen("https://raw.githubusercontent.com/" + REPO + "/" + revision + "/package.json", timeout=30) as response:
        source = json.load(response)
    if source["version"] != version:
        raise SystemExit("Image source version does not match the requested release")
    package_version = current["packageVersion"] if version == current["version"] else version + "-umbrel.1"
    dockerfile = ROOT / "Dockerfile"
    dockerfile.write_text(re.sub(r"^ARG UPSTREAM_IMAGE=.*$", "ARG UPSTREAM_IMAGE=" + image, dockerfile.read_text(), flags=re.M))
    compose = ROOT / "docker-compose.yml"
    compose.write_text(re.sub(r"docker\.io/vytor/openmausbot:[^\s]+", "docker.io/vytor/openmausbot:" + package_version, compose.read_text()))
    manifest = ROOT / "umbrel-app.yml"
    text = re.sub(r'^version: .*$', 'version: "' + package_version + '"', manifest.read_text(), flags=re.M)
    text = re.sub(r"^releaseNotes: >-\n(?:  .*\n|\n)*", "releaseNotes: >-\n  Updates OpenMausBot to " + version + ".\n", text, flags=re.M)
    manifest.write_text(text)
    (ROOT / "upstream.json").write_text(json.dumps({"version": version, "revision": revision, "image": image, "packageVersion": package_version}, indent=2) + "\n")
    print("Prepared " + package_version + ". Build and smoke-test before publication.")


if __name__ == "__main__":
    main()
