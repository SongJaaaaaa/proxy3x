#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import mimetypes
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


BASE_DIR = Path(os.environ.get("CHAIN_BASE_DIR", "/opt/3x-ui-chain"))
SUB_DIR = BASE_DIR / "subscriptions"
DB = BASE_DIR / "db" / "x-ui.db"
DEPLOYMENT = BASE_DIR / "chain-deployment.json"
GB = 1024 * 1024 * 1024


def parse_expire(value):
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        return 0
    if value > 10_000_000_000:
        value //= 1000
    return max(value, 0)


def bytes_from_gb(value):
    try:
        return int(float(value) * GB)
    except (TypeError, ValueError):
        return 0


def load_deployment():
    if not DEPLOYMENT.is_file():
        return {}
    try:
        return json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_traffic_by_source(source):
    email = source.get("email")
    port = source.get("port")
    if not email and not port:
        return None
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT i.id, i.port, i.remark, i.total, i.expiry_time, i.settings
            FROM inbounds i
            WHERE i.enable = 1
            ORDER BY i.id
            """
        )
        for inbound in cur.fetchall():
            if port and int(inbound["port"] or 0) != int(port):
                continue
            try:
                settings = json.loads(inbound["settings"] or "{}")
            except json.JSONDecodeError:
                settings = {}
            for client in settings.get("clients") or []:
                client_email = client.get("email") or ""
                if email and client_email != email:
                    continue
                cur.execute(
                    """
                    SELECT up, down, total, expiry_time
                    FROM client_traffics
                    WHERE inbound_id = ? AND email = ?
                    """,
                    (inbound["id"], client_email),
                )
                traffic = cur.fetchone()
                return {
                    "inbound": dict(inbound),
                    "client": client,
                    "traffic": dict(traffic) if traffic else None,
                }
    finally:
        con.close()
    return None


def find_client_by_sub_id(sub_id):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, port, remark, total, expiry_time, settings
            FROM inbounds
            WHERE enable = 1
            ORDER BY id
            """
        )
        for inbound in cur.fetchall():
            try:
                settings = json.loads(inbound["settings"] or "{}")
            except json.JSONDecodeError:
                continue
            for client in settings.get("clients") or []:
                if client.get("subId") != sub_id:
                    continue
                email = client.get("email") or ""
                cur.execute(
                    """
                    SELECT up, down, total, expiry_time
                    FROM client_traffics
                    WHERE inbound_id = ? AND email = ?
                    """,
                    (inbound["id"], email),
                )
                traffic = cur.fetchone()
                return {
                    "inbound": dict(inbound),
                    "client": client,
                    "traffic": dict(traffic) if traffic else None,
                }
    finally:
        con.close()
    return None


def build_userinfo(info, total_override=0, expire_override=0):
    inbound = info["inbound"]
    client = info["client"]
    traffic = info["traffic"] or {}
    upload = int(traffic.get("up") or 0)
    download = int(traffic.get("down") or 0)
    total = int(total_override or traffic.get("total") or client.get("totalGB") or inbound.get("total") or 0)
    expire = (
        parse_expire(expire_override)
        or parse_expire(traffic.get("expiry_time"))
        or parse_expire(client.get("expiryTime"))
        or parse_expire(inbound.get("expiry_time"))
    )
    parts = [f"upload={upload}", f"download={download}", f"total={total}"]
    if expire:
        parts.append(f"expire={expire}")
    return "; ".join(parts)


def manager_subscription_userinfo(sub_id):
    deployment = load_deployment()
    packages = deployment.get("manager_packages") or []
    package = next((item for item in packages if item.get("sub_id") == sub_id), None)
    if not package:
        return None
    upload = 0
    download = 0
    expire_values = []
    for source in package.get("usage_sources") or []:
        info = read_traffic_by_source(source)
        if not info:
            continue
        traffic = info.get("traffic") or {}
        upload += int(traffic.get("up") or 0)
        download += int(traffic.get("down") or 0)
        expire = (
            parse_expire(traffic.get("expiry_time"))
            or parse_expire((info.get("client") or {}).get("expiryTime"))
            or parse_expire((info.get("inbound") or {}).get("expiry_time"))
        )
        if expire:
            expire_values.append(expire)
    total = bytes_from_gb(package.get("total_gb")) or int(package.get("total") or 0)
    parts = [f"upload={upload}", f"download={download}", f"total={total}"]
    expire = parse_expire(package.get("expire")) or (min(expire_values) if expire_values else 0)
    if expire:
        parts.append(f"expire={expire}")
    return "; ".join(parts)


def legacy_aggregate_userinfo(sub_id):
    aggregate = (load_deployment().get("aggregate_subscription") or {})
    if aggregate.get("sub_id") != sub_id:
        return None
    info = read_traffic_by_source(aggregate.get("usage_source") or {})
    total = bytes_from_gb(aggregate.get("total_gb")) or int(aggregate.get("total") or 0)
    expire = aggregate.get("expire") or aggregate.get("expiry_time")
    if info:
        return build_userinfo(info, total_override=total, expire_override=expire)
    if total:
        parts = ["upload=0", "download=0", f"total={total}"]
        expire = parse_expire(expire)
        if expire:
            parts.append(f"expire={expire}")
        return "; ".join(parts)
    return None


def subscription_userinfo(sub_id):
    return (
        manager_subscription_userinfo(sub_id)
        or legacy_aggregate_userinfo(sub_id)
        or (build_userinfo(find_client_by_sub_id(sub_id)) if find_client_by_sub_id(sub_id) else None)
    )


class SubscriptionHandler(BaseHTTPRequestHandler):
    server_version = "chain-subscriptions/1.1"

    def do_HEAD(self):
        self.serve(send_body=False)

    def do_GET(self):
        self.serve(send_body=True)

    def serve(self, send_body):
        parsed = urlparse(self.path)
        name = unquote(parsed.path.lstrip("/"))
        if not name or "/" in name or "\\" in name or name.startswith("."):
            self.send_error(404)
            return
        path = SUB_DIR / name
        if not path.is_file():
            self.send_error(404)
            return
        sub_id = path.stem
        userinfo = subscription_userinfo(sub_id)
        data = path.read_bytes() if send_body else b""
        content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
        if path.suffix == ".yaml":
            content_type = "text/yaml"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Profile-Update-Interval", "24")
        if userinfo:
            self.send_header("Subscription-Userinfo", userinfo)
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args), flush=True)


def main():
    port = int(os.environ.get("PORT", "8080"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), SubscriptionHandler)
    print(f"Serving subscriptions on 0.0.0.0:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
