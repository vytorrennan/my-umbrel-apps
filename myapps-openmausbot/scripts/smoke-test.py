#!/usr/bin/env python3
"""Test the package with isolated data and a nested Docker daemon."""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--desktop", action="store_true", help="Prepare and run the real upstream Cua desktop")
    parser.add_argument("--keep", action="store_true", help="Keep the fixture for manual browser testing")
    args = parser.parse_args()
    image = "docker.io/vytor/openmausbot:" + json.loads((ROOT / "upstream.json").read_text())["packageVersion"]
    subprocess.run(["docker", "image", "inspect", image], check=True, stdout=subprocess.DEVNULL)
    fixture = Path(tempfile.mkdtemp(prefix=".openmausbot-smoke-", dir=ROOT.parent.parent))
    fixture.chmod(0o755)
    project = "omb-smoke-" + uuid.uuid4().hex[:8]
    env = dict(os.environ, APP_DATA_DIR=str(fixture), DEVICE_DOMAIN_NAME=args.host)
    stub = fixture / "proxy.yml"
    stub.write_text(json.dumps({"services": {"app_proxy": {"image": image}}}))
    rendered = subprocess.check_output(["docker", "compose", "-f", str(ROOT / "docker-compose.yml"), "-f", str(stub), "config", "--format", "json"], env=env, text=True)
    config = json.loads(rendered)
    config.pop("name", None)
    for network in config.get("networks", {}).values():
        if not network.get("external"):
            network.pop("name", None)
    del config["services"]["app_proxy"]
    config["services"]["server"]["ports"] = [args.bind + ":18898:8080", args.bind + ":18897:8081"]
    config["services"]["server"]["environment"].update(OMB_PUBLIC_URL="http://" + args.host + ":18897", OMB_WEBHOOK_PUBLIC_URL="http://" + args.host + ":18897")
    path = fixture / "compose.json"
    path.write_text(json.dumps(config))
    for name in ["Caddyfile", "setup.mjs"]:
        target = fixture / name
        shutil.copyfile(ROOT / (name + ".template"), target)
        target.chmod(0o644)
    (fixture / "data" / "home").mkdir(parents=True)
    # A test runner may have a different UID than the app.
    subprocess.run(["docker", "run", "--rm", "--user", "root", "-v", str(fixture) + ":/fixture", image, "chown", "1000:1000", "/fixture/data/home"], check=True)
    command = ["docker", "compose", "-p", project, "-f", str(path)]

    def compose(*argv, capture=False):
        return subprocess.run(command + list(argv), check=True, text=True, stdout=subprocess.PIPE if capture else None).stdout

    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies), NoRedirect())
    web = "http://" + args.host + ":18898"
    remote = "http://" + args.host + ":18897"

    def request(base, route, body=None, origin=None, timeout=30, bearer=None, anonymous=False):
        headers = {}
        if origin is not None:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json"
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        req = urllib.request.Request(base + route, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            sender = urllib.request.build_opener(NoRedirect()) if anonymous else client
            response = sender.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        payload = response.read().decode()
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            pass
        return response.code, payload, response.headers

    try:
        compose("up", "-d", "--wait", "--wait-timeout", "180")
        assert request(web, "/umbrel-start")[0] == 200
        assert request(remote, "/umbrel-start")[0] == 404
        assert request(web, "/terminal/")[0] == 200
        assert request(remote, "/terminal/")[0] == 404
        assert request(remote, "/api/auth/session")[0] in (401, 403)
        assert request(remote, "/api/auth/pairing", {}, remote)[0] in (401, 403)
        for origin in [None, "https://foreign.invalid"]:
            assert request(web, "/umbrel-start", {}, origin)[0] == 403
        status, _, headers = request(web, "/umbrel-start", {}, web)
        assert status == 303
        code = urllib.parse.parse_qs(urllib.parse.urlparse(headers["Location"]).fragment)["code"][0]
        status, _, _ = request(remote, "/api/auth/pair", {"code": code, "label": "Package smoke test", "cookie": True}, remote)
        assert status == 200
        status, session, _ = request(remote, "/api/auth/session")
        assert status == 200 and session["kind"] == "session"
        assert request(remote, "/api/auth/pair", {"code": code}, remote)[0] in (401, 403)
        status, bots, _ = request(remote, "/api/bots")
        assert status == 200 and bots["bots"]
        status, invite, _ = request(remote, "/api/auth/pairing", {"scopes": ["client"], "label": "Native client"}, remote)
        assert status == 200
        status, native, _ = request(remote, "/api/pair", {"credential": invite["credential"], "deviceName": "Native smoke test"}, remote, anonymous=True)
        assert status == 200
        status, native_session, _ = request(remote, "/api/auth/session", bearer=native["token"], anonymous=True)
        assert status == 200 and native_session["scopes"] == ["client"]
        assert request(remote, "/api/auth/pairing", {}, remote, bearer=native["token"], anonymous=True)[0] == 403
        assert request(remote, "/hooks/nonexistent", {}, remote)[0] == 404
        status, hook, _ = request(remote, "/api/webhooks", {"name": "Smoke test", "prompt": "Test event", "botId": bots["bots"][0]["id"], "enabled": False, "verificationPending": True}, remote)
        assert status == 201
        endpoint = urllib.parse.urlparse(hook["credential"]["endpointUrl"]).path
        assert request(remote, endpoint, {}, anonymous=True)[0] == 401
        secret_url = urllib.parse.urlparse(hook["credential"]["url"]).path
        assert request(remote, secret_url, {"test": True}, anonymous=True)[0] == 202
        compose("exec", "-T", "server", "sh", "-ec", "docker version; docker buildx version; ssh -V; python3 --version; uv --version; claude --version; codex --version; grok --version")
        compose("exec", "-T", "server", "docker", "run", "--rm", "--user", "1000:1000", "-v", "/data:/data", "busybox:1.37", "sh", "-ec", "echo durable > /data/smoke-desktop")
        if args.desktop:
            print("Preparing the upstream Cua desktop image. This may take several minutes.", flush=True)
            assert request(remote, "/api/local-computer/pull", {}, remote, timeout=1200)[0] == 200
            status, result, _ = request(remote, "/api/local-computer/run", {}, remote, timeout=240)
            assert status == 200, result
            ready = False
            for _ in range(60):
                status, result, _ = request(remote, "/api/local-computer/screenshot", {}, remote)
                if status == 200 and result.get("image"):
                    ready = True
                    break
                time.sleep(2)
            assert ready, "Cua desktop did not produce a screenshot"
            assert request(remote, "/api/local-computer/stop", {}, remote)[0] == 200
        compose("down", "--volumes", "--timeout", "5")
        compose("up", "-d", "--wait", "--wait-timeout", "180")
        status, restored, _ = request(remote, "/api/auth/session")
        assert status == 200 and restored["id"] == session["id"]
        assert compose("exec", "-T", "server", "cat", "/data/smoke-desktop", capture=True).strip() == "durable"
        print("PASS: pairing, origin checks, native client API, webhook routing, tools, nested desktops, and persistence", flush=True)
    except BaseException:
        compose("logs", "--tail", "60")
        raise
    finally:
        if args.keep:
            print("Fixture retained at " + str(fixture) + ", project " + project, flush=True)
        else:
            compose("down", "--volumes", "--timeout", "5")
            subprocess.run(["docker", "run", "--rm", "--user", "root", "-v", str(fixture) + ":/fixture", image, "rm", "-rf", "/fixture/data"], check=True)
            shutil.rmtree(fixture)


if __name__ == "__main__":
    main()
