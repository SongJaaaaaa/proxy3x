#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http import cookies
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    ALT_SUBSCRIPTION_DOMAIN,
    APP_DIR,
    BLOCK_OUTBOUND_TAG,
    CHAIN_DB,
    CHAIN_DIR,
    CREDENTIALS_PATH,
    DEFAULT_NODE_NAME,
    DEFAULT_PACKAGE_EXPIRE_SECONDS,
    DEFAULT_PACKAGE_TOTAL_GB,
    DEFAULT_SERVER,
    DEFAULT_UPSTREAM_EXPIRE_SECONDS,
    DEPLOYMENT_PATH,
    DIRECT_OUTBOUND_TAG,
    ENABLE_SING_BOX_STATS,
    ENTERTAINMENT_NODE_NAME,
    FRONTEND_DIR,
    GB,
    INITIAL_CREDENTIALS_PATH,
    LEGACY_NODE_NAMES,
    LEGACY_SINGLE_NODE_NAMES,
    NODE_SERVER,
    OUTBOUND_TEST_URL,
    PACKAGE_TYPE_CHAIN,
    PACKAGE_TYPE_MIXED,
    PANEL_BASE_URL,
    REALITY_SNI,
    RESIDENTIAL_NODE_NAME,
    RULES_PATH,
    SESSION_MAX_AGE,
    SHADOWROCKET_NODE_SERVER,
    SING_BOX_API_LISTEN,
    SING_BOX_CONFIG_PATH,
    SING_BOX_SERVICE,
    SOCKS_FACTORY_DIR,
    SOCKS_PORT_END,
    SOCKS_PORT_START,
    STATSQUERY_BIN,
    SUBSCRIPTIONS_DIR,
    SUPPORTED_SOURCE_PROTOCOLS,
    XUI_CONTAINER,
)
from db import connect_manager_db


def now():
    return int(time.time())


def json_dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def pretty_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def slugify(value):
    value = (value or "").strip()
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return value or f"user-{secrets.token_hex(3)}"


def bytes_from_gb(value):
    try:
        return int(float(value or 0) * GB)
    except (TypeError, ValueError):
        return 0


def gb_from_bytes(value):
    try:
        return round(int(value or 0) / GB, 3)
    except (TypeError, ValueError):
        return 0


def format_speed(value):
    value = int(value or 0)
    if value <= 0:
        return "未测速"
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.2f} MB/s"
    return f"{value / 1024:.1f} KB/s"


def default_expires_at(base=None):
    return int(base or now()) + DEFAULT_PACKAGE_EXPIRE_SECONDS


def default_upstream_expires_at(base=None):
    return int(base or now()) + DEFAULT_UPSTREAM_EXPIRE_SECONDS


def parse_datetime_value(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return int(datetime.strptime(text, fmt).timestamp())
            except ValueError:
                pass
    try:
        ts = int(float(value or 0))
    except (TypeError, ValueError):
        return 0
    if ts > 100000000000:
        ts = ts // 1000
    return ts


def parse_expires_at(value, base=None):
    ts = parse_datetime_value(value)
    return ts if ts > 0 else default_expires_at(base)


def parse_upstream_expires_at(value, base=None):
    ts = parse_datetime_value(value)
    return ts if ts > 0 else default_upstream_expires_at(base)


def package_is_expired(package, at=None):
    expires_at = int(package["expires_at"] or 0)
    return bool(expires_at and expires_at <= int(at or now()))


def upstream_is_expired(upstream, at=None):
    try:
        expires_at = int(upstream["expires_at"] or 0)
    except (KeyError, TypeError, ValueError):
        expires_at = 0
    return bool(expires_at and expires_at <= int(at or now()))


def read_text(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def backup_file(path, suffix):
    path = Path(path)
    if not path.exists():
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{path.name}.{suffix}-{stamp}"
    shutil.copy2(path, target)
    return str(target)


def init_db():
    with connect_manager_db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS upstreams (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              protocol TEXT NOT NULL DEFAULT 'auto',
              host TEXT NOT NULL,
              port INTEGER NOT NULL,
              username TEXT NOT NULL DEFAULT '',
              password TEXT NOT NULL DEFAULT '',
              remark TEXT NOT NULL DEFAULT '',
              assigned_to TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT '未检测',
              last_error TEXT NOT NULL DEFAULT '',
              last_check_at INTEGER NOT NULL DEFAULT 0,
              latency_ms INTEGER NOT NULL DEFAULT 0,
              speed_bps INTEGER NOT NULL DEFAULT 0,
              last_speed_at INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS packages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              sub_id TEXT NOT NULL UNIQUE,
              total_gb REAL NOT NULL DEFAULT 100,
              residential_gb REAL NOT NULL DEFAULT 50,
              notes TEXT NOT NULL DEFAULT '',
              upstream_id INTEGER,
              direct_email TEXT NOT NULL DEFAULT '',
              direct_port INTEGER,
              residential_email TEXT NOT NULL DEFAULT '',
              residential_port INTEGER,
              direct_entry_json TEXT NOT NULL DEFAULT '',
              residential_entry_json TEXT NOT NULL DEFAULT '',
              enabled INTEGER NOT NULL DEFAULT 1,
              direct_enabled INTEGER NOT NULL DEFAULT 1,
              residential_enabled INTEGER NOT NULL DEFAULT 1,
              expires_at INTEGER NOT NULL DEFAULT 0,
              disabled_reason TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              level TEXT NOT NULL DEFAULT '信息',
              message TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS socks_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              url TEXT NOT NULL,
              total_gb REAL NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              node_count INTEGER NOT NULL DEFAULT 0,
              endpoint_count INTEGER NOT NULL DEFAULT 0,
              last_refresh_at INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS socks_nodes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id INTEGER NOT NULL,
              node_key TEXT NOT NULL,
              name TEXT NOT NULL,
              protocol TEXT NOT NULL,
              server TEXT NOT NULL DEFAULT '',
              port INTEGER NOT NULL DEFAULT 0,
              raw_uri TEXT NOT NULL DEFAULT '',
              config_json TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT '未检测',
              latency_ms INTEGER NOT NULL DEFAULT 0,
              speed_bps INTEGER NOT NULL DEFAULT 0,
              last_speed_at INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              UNIQUE(source_id, node_key)
            );

            CREATE TABLE IF NOT EXISTS socks_endpoints (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id INTEGER NOT NULL,
              node_id INTEGER NOT NULL,
              listen_port INTEGER NOT NULL UNIQUE,
              username TEXT NOT NULL,
              password TEXT NOT NULL,
              quota_gb REAL NOT NULL DEFAULT 0,
              upload_bytes INTEGER NOT NULL DEFAULT 0,
              download_bytes INTEGER NOT NULL DEFAULT 0,
              latency_ms INTEGER NOT NULL DEFAULT 0,
              speed_bps INTEGER NOT NULL DEFAULT 0,
              last_speed_at INTEGER NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              expires_at INTEGER NOT NULL DEFAULT 0,
              remark TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS package_bindings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              package_id INTEGER NOT NULL,
              upstream_id INTEGER NOT NULL,
              display_name TEXT NOT NULL DEFAULT '',
              email TEXT NOT NULL DEFAULT '',
              port INTEGER,
              entry_json TEXT NOT NULL DEFAULT '',
              enabled INTEGER NOT NULL DEFAULT 1,
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              UNIQUE(package_id, upstream_id)
            );
            """
        )
        columns = {row["name"] for row in con.execute("PRAGMA table_info(packages)").fetchall()}
        if "expires_at" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN expires_at INTEGER NOT NULL DEFAULT 0")
        if "disabled_reason" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN disabled_reason TEXT NOT NULL DEFAULT ''")
        if "package_type" not in columns:
            con.execute(f"ALTER TABLE packages ADD COLUMN package_type TEXT NOT NULL DEFAULT '{PACKAGE_TYPE_CHAIN}'")
        if "direct_node_enabled" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN direct_node_enabled INTEGER NOT NULL DEFAULT 1")
        if "residential_node_enabled" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN residential_node_enabled INTEGER NOT NULL DEFAULT 0")
        con.execute(
            """
            UPDATE packages
            SET expires_at = created_at + ?
            WHERE expires_at IS NULL OR expires_at = 0
            """,
            (DEFAULT_PACKAGE_EXPIRE_SECONDS,),
        )
        con.execute(
            """
            UPDATE packages
            SET direct_node_enabled = CASE WHEN direct_port IS NOT NULL AND direct_port > 0 THEN 1 ELSE 0 END
            """,
        )
        con.execute(
            """
            UPDATE packages
            SET residential_node_enabled = CASE WHEN residential_port IS NOT NULL AND residential_port > 0 THEN 1 ELSE 0 END
            """,
        )
        # SOCKS5 额度字段：用于上游用量进度条的分母（GB）。0 = 未设额度，前端不画进度条。
        upstream_columns = {row["name"] for row in con.execute("PRAGMA table_info(upstreams)").fetchall()}
        if "quota_gb" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN quota_gb REAL NOT NULL DEFAULT 0")
        if "expires_at" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN expires_at INTEGER NOT NULL DEFAULT 0")
        if "speed_bps" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN speed_bps INTEGER NOT NULL DEFAULT 0")
        if "last_speed_at" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN last_speed_at INTEGER NOT NULL DEFAULT 0")
        if "latency_ms" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0")
        con.execute(
            """
            UPDATE upstreams
            SET expires_at = ?
            WHERE expires_at IS NULL OR expires_at = 0
            """,
            (default_upstream_expires_at(),),
        )
        node_columns = {row["name"] for row in con.execute("PRAGMA table_info(socks_nodes)").fetchall()}
        if "speed_bps" not in node_columns:
            con.execute("ALTER TABLE socks_nodes ADD COLUMN speed_bps INTEGER NOT NULL DEFAULT 0")
        if "last_speed_at" not in node_columns:
            con.execute("ALTER TABLE socks_nodes ADD COLUMN last_speed_at INTEGER NOT NULL DEFAULT 0")
        endpoint_columns = {row["name"] for row in con.execute("PRAGMA table_info(socks_endpoints)").fetchall()}
        if "speed_bps" not in endpoint_columns:
            con.execute("ALTER TABLE socks_endpoints ADD COLUMN speed_bps INTEGER NOT NULL DEFAULT 0")
        if "last_speed_at" not in endpoint_columns:
            con.execute("ALTER TABLE socks_endpoints ADD COLUMN last_speed_at INTEGER NOT NULL DEFAULT 0")
        if "latency_ms" not in endpoint_columns:
            con.execute("ALTER TABLE socks_endpoints ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0")
        current = now()
        con.execute(
            """
            INSERT OR IGNORE INTO package_bindings(
              package_id, upstream_id, display_name, email, port, entry_json,
              enabled, sort_order, created_at, updated_at
            )
            SELECT id, upstream_id, '', direct_email, direct_port, direct_entry_json,
                   direct_node_enabled, 0, ?, ?
            FROM packages
            WHERE upstream_id IS NOT NULL
              AND direct_port IS NOT NULL
              AND direct_port > 0
            """,
            (current, current),
        )


def log_event(level, message):
    init_db()
    with connect_manager_db() as con:
        con.execute(
            "INSERT INTO events(level, message, created_at) VALUES (?, ?, ?)",
            (level, message, now()),
        )


def run_background(name, target, *args):
    def wrapped():
        try:
            target(*args)
        except Exception as exc:
            log_event("警告", f"{name}失败：{exc}")

    thread = threading.Thread(target=wrapped, name=f"proxy3x-{name}", daemon=True)
    thread.start()


def load_credentials():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CREDENTIALS_PATH.exists():
        return json.loads(read_text(CREDENTIALS_PATH))

    password = secrets.token_urlsafe(16)
    salt = secrets.token_hex(16)
    secret = secrets.token_hex(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    data = {
        "username": "admin",
        "salt": salt,
        "password_hash": digest,
        "session_secret": secret,
        "created_at": now(),
    }
    write_text(CREDENTIALS_PATH, pretty_json(data))
    os.chmod(CREDENTIALS_PATH, 0o600)
    write_text(INITIAL_CREDENTIALS_PATH, f"访问地址=https://proxy3x.sjiaa.cc.cd/\n用户名=admin\n密码={password}\n")
    os.chmod(INITIAL_CREDENTIALS_PATH, 0o600)
    return data


def verify_password(username, password):
    creds = load_credentials()
    if username != creds.get("username"):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode(),
        creds["salt"].encode(),
        200_000,
    ).hex()
    return hmac.compare_digest(digest, creds.get("password_hash", ""))


def sign_session(username, ts=None):
    creds = load_credentials()
    ts = ts or now()
    payload = f"{username}:{ts}"
    sig = hmac.new(creds["session_secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    return token


def read_session(token):
    if not token:
        return None
    creds = load_credentials()
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        username, ts_text, sig = raw.rsplit(":", 2)
        ts = int(ts_text)
    except Exception:
        return None
    if now() - ts > SESSION_MAX_AGE:
        return None
    payload = f"{username}:{ts}"
    expected = hmac.new(creds["session_secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return username


def read_panel_credentials():
    values = {}
    for line in read_text(CHAIN_DIR / "panel-credentials.txt").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    if not values.get("username") or not values.get("password"):
        raise RuntimeError("没有找到 3x-ui 面板凭据")
    return values["username"], values["password"]


def has_panel_credentials():
    username, password = "", ""
    for line in read_text(CHAIN_DIR / "panel-credentials.txt").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "username":
            username = value.strip()
        elif key.strip() == "password":
            password = value.strip()
    return bool(username and password)


class PanelClient:
    def __init__(self):
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))
        self.csrf = ""

    def request(self, method, path, body=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        req = Request(PANEL_BASE_URL + path, data=data, headers=headers, method=method)
        with self.opener.open(req, timeout=25) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
        text = payload.decode("utf-8", "replace")
        match = re.search(r'<meta name="csrf-token" content="([^"]+)"', text)
        if match:
            self.csrf = match.group(1)
        if "application/json" in content_type:
            return json.loads(text)
        return text

    def login(self):
        username, password = read_panel_credentials()
        self.request("GET", "/")
        result = self.request("POST", "/login", {"username": username, "password": password})
        if not isinstance(result, dict) or not result.get("success"):
            raise RuntimeError("3x-ui 登录失败")
        self.request("GET", "/panel/")

    def get_json(self, path):
        result = self.request("GET", path)
        if not isinstance(result, dict) or not result.get("success"):
            raise RuntimeError(f"3x-ui 接口失败：{path}")
        return result.get("obj")

    def post_json(self, path, body=None):
        result = self.request("POST", path, body)
        if not isinstance(result, dict) or not result.get("success"):
            raise RuntimeError(f"3x-ui 接口失败：{path}")
        return result.get("obj")

    def post_form(self, path, fields):
        headers = {}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        data = urlencode(fields).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(PANEL_BASE_URL + path, data=data, headers=headers, method="POST")
        with self.opener.open(req, timeout=25) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
        text = payload.decode("utf-8", "replace")
        if "application/json" in content_type:
            result = json.loads(text)
            if not result.get("success"):
                raise RuntimeError(f"3x-ui 接口失败：{path}")
            return result.get("obj")
        return text


def get_panel_client():
    client = PanelClient()
    client.login()
    return client


def read_deployment():
    try:
        return json.loads(read_text(DEPLOYMENT_PATH) or "{}")
    except json.JSONDecodeError:
        return {}


def write_deployment(data):
    DEPLOYMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = pretty_json(data)
    if read_text(DEPLOYMENT_PATH) == text:
        return
    backup_file(DEPLOYMENT_PATH, "before-proxy3x")
    write_text(DEPLOYMENT_PATH, text)


def server_host():
    data = read_deployment()
    return data.get("server") or DEFAULT_SERVER


def node_host():
    data = read_deployment()
    return data.get("node_server") or NODE_SERVER


def load_rules():
    text = read_text(RULES_PATH)
    rules = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^-\s*['\"]?(.*?)['\"]?\s*$", line)
        if match:
            rule = match.group(1).strip()
            if rule:
                rules.append(rule.replace("性价比机场", "手动选择"))
    if not rules:
        rules = [
            "DOMAIN-SUFFIX,local,DIRECT",
            "IP-CIDR,127.0.0.0/8,DIRECT",
            "IP-CIDR,10.0.0.0/8,DIRECT",
            "GEOIP,CN,DIRECT",
            "MATCH,手动选择",
        ]
    if not any(rule.startswith("MATCH,") for rule in rules):
        rules.append("MATCH,手动选择")
    return rules


def next_free_port():
    used = set()
    with connect_manager_db() as con:
        for row in con.execute("SELECT direct_port, residential_port FROM packages"):
            if row["direct_port"]:
                used.add(int(row["direct_port"]))
            if row["residential_port"]:
                used.add(int(row["residential_port"]))
        for row in con.execute("SELECT port FROM package_bindings WHERE port IS NOT NULL"):
            if row["port"]:
                used.add(int(row["port"]))
    if CHAIN_DB.exists():
        con = sqlite3.connect(f"file:{CHAIN_DB}?mode=ro", uri=True)
        try:
            for (port,) in con.execute("SELECT port FROM inbounds"):
                if port:
                    used.add(int(port))
        finally:
            con.close()
    for port in range(31001, 31100):
        if port == 31080:
            continue
        if port not in used:
            return port
    raise RuntimeError("31001-31099 没有可用端口")


def make_inbound(spec):
    client = get_panel_client()
    cert = client.get_json("/panel/api/server/getNewX25519Cert")
    short_id = secrets.token_hex(4)
    client_id = str(uuid.uuid4())
    total_bytes = int(spec.get("total_bytes") or 0)
    email = spec["email"]
    sub_id = spec["sub_id"]

    settings = {
        "clients": [
            {
                "id": client_id,
                "flow": "xtls-rprx-vision",
                "email": email,
                "limitIp": 0,
                "totalGB": total_bytes,
                "expiryTime": 0,
                "enable": True,
                "tgId": "",
                "subId": sub_id,
                "reset": 0,
            }
        ],
        "decryption": "none",
        "fallbacks": [],
    }
    stream_settings = {
        "network": "tcp",
        "security": "reality",
        "externalProxy": [],
        "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
        "realitySettings": {
            "show": False,
            "xver": 0,
            "dest": f"{REALITY_SNI}:443",
            "serverNames": [REALITY_SNI],
            "privateKey": cert["privateKey"],
            "minClientVer": "",
            "maxClientVer": "",
            "maxTimeDiff": 0,
            "shortIds": [short_id],
        },
    }
    sniffing = {
        "enabled": True,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": False,
        "routeOnly": False,
    }
    allocate = {"strategy": "always", "refresh": 5, "concurrency": 3}
    body = {
        "up": 0,
        "down": 0,
        "total": total_bytes,
        "remark": spec["remark"],
        "enable": True,
        "expiryTime": 0,
        "listen": "0.0.0.0",
        "port": int(spec["port"]),
        "protocol": "vless",
        "settings": json_dumps(settings),
        "streamSettings": json_dumps(stream_settings),
        "sniffing": json_dumps(sniffing),
        "allocate": json_dumps(allocate),
    }
    client.post_json("/panel/api/inbounds/add", body)
    return {
        "sub_id": sub_id,
        "email": email,
        "remark": spec["remark"],
        "node_name": spec["node_name"],
        "port": int(spec["port"]),
        "uuid": client_id,
        "public_key": cert["publicKey"],
        "short_id": short_id,
        "sni": REALITY_SNI,
        "total_gb": round(total_bytes / GB, 3) if total_bytes else 0,
    }


def local_mock_inbound(spec):
    total_bytes = int(spec.get("total_bytes") or 0)
    return {
        "sub_id": spec["sub_id"],
        "email": spec["email"],
        "remark": spec["remark"],
        "node_name": spec["node_name"],
        "port": int(spec["port"]),
        "uuid": str(uuid.uuid4()),
        "public_key": "local-dev-public-key",
        "short_id": secrets.token_hex(4),
        "sni": REALITY_SNI,
        "total_gb": round(total_bytes / GB, 3) if total_bytes else 0,
        "local_dev": True,
    }


def make_inbound_best_effort(spec):
    if os.name == "nt" and not has_panel_credentials():
        return local_mock_inbound(spec)
    return make_inbound(spec)


def vless_uri(entry, node_name):
    params = {
        "encryption": "none",
        "flow": "xtls-rprx-vision",
        "fp": "chrome",
        "pbk": entry["public_key"],
        "security": "reality",
        "sid": entry["short_id"],
        "sni": entry.get("sni") or REALITY_SNI,
        "spx": "/",
        "type": "tcp",
    }
    query = "&".join(f"{key}={quote(str(value), safe='')}" for key, value in params.items())
    return f"vless://{entry['uuid']}@{node_host()}:{entry['port']}?{query}#{quote(node_name)}"


def clash_node(entry, node_name):
    return f"""  - name: \"{node_name}\"
    type: vless
    server: \"{node_host()}\"
    port: {int(entry["port"])}
    uuid: \"{entry["uuid"]}\"
    network: tcp
    tls: true
    udp: true
    flow: xtls-rprx-vision
    servername: \"{entry.get("sni") or REALITY_SNI}\"
    client-fingerprint: chrome
    reality-opts:
      public-key: \"{entry["public_key"]}\"
      short-id: \"{entry["short_id"]}\""""


def package_nodes(package):
    package = dict(package)
    bindings = package_binding_rows(package["id"])
    if bindings:
        nodes = []
        for row in bindings:
            entry = json.loads(row["entry_json"] or "{}")
            if not entry:
                continue
            name = binding_display_name(row) or entry.get("node_name") or DEFAULT_NODE_NAME
            nodes.append((name, entry))
        return nodes
    entries = []
    node_specs = [
        ("direct_entry_json", bool(package.get("direct_node_enabled", 1))),
        ("residential_entry_json", bool(package.get("residential_node_enabled", 0))),
    ]
    for key, enabled in node_specs:
        if not enabled:
            continue
        entry = json.loads(package[key] or "{}")
        if entry:
            entries.append((entry.get("node_name") or DEFAULT_NODE_NAME, entry))
    nodes = []
    single_node = len(entries) == 1
    for name, entry in entries:
        if name in LEGACY_NODE_NAMES or (single_node and name in LEGACY_SINGLE_NODE_NAMES):
            name = DEFAULT_NODE_NAME
        nodes.append((name, entry))
    return nodes


def package_binding_rows(package_id):
    with connect_manager_db() as con:
        return con.execute(
            """
            SELECT b.*, u.protocol, u.host, u.port AS upstream_port, u.username, u.password,
                   u.remark AS upstream_remark, u.expires_at AS upstream_expires_at
            FROM package_bindings b
            JOIN upstreams u ON u.id = b.upstream_id
            WHERE b.package_id = ? AND b.enabled = 1
            ORDER BY b.sort_order, b.id
            """,
            (package_id,),
        ).fetchall()


def package_binding_all_rows(package_id):
    with connect_manager_db() as con:
        return con.execute(
            """
            SELECT b.*, u.protocol, u.host, u.port AS upstream_port, u.username, u.password,
                   u.remark AS upstream_remark, u.expires_at AS upstream_expires_at
            FROM package_bindings b
            JOIN upstreams u ON u.id = b.upstream_id
            WHERE b.package_id = ?
            ORDER BY b.sort_order, b.id
            """,
            (package_id,),
        ).fetchall()


def package_binding_public_rows(package_id):
    rows = package_binding_rows(package_id)
    return [
        {
            "id": row["id"],
            "upstream_id": row["upstream_id"],
            "display_name": binding_display_name(row),
            "port": row["port"],
            "email": row["email"],
            "sort_order": row["sort_order"],
            "enabled": bool(row["enabled"]),
        }
        for row in rows
    ]


def binding_upstream(row):
    return {
        "id": row["upstream_id"],
        "protocol": row["protocol"],
        "host": row["host"],
        "port": row["upstream_port"],
        "username": row["username"],
        "password": row["password"],
        "remark": row["upstream_remark"],
        "expires_at": row["upstream_expires_at"],
    }


def binding_display_name(row):
    return row["display_name"] or upstream_display_name(binding_upstream(row))


def package_runtime_entries(package):
    package = dict(package)
    rows = package_binding_all_rows(package["id"])
    entries = [
        {"port": row["port"], "email": row["email"], "enabled": bool(row["enabled"]), "kind": "binding"}
        for row in rows
        if row["port"] and row["email"]
    ]
    if entries:
        return entries
    legacy = []
    if package.get("direct_port") and package.get("direct_email"):
        legacy.append(
            {
                "port": package.get("direct_port"),
                "email": package.get("direct_email"),
                "enabled": bool(package.get("direct_enabled", 1)),
                "kind": "direct",
            }
        )
    if package.get("residential_port") and package.get("residential_email"):
        legacy.append(
            {
                "port": package.get("residential_port"),
                "email": package.get("residential_email"),
                "enabled": bool(package.get("residential_enabled", 0)),
                "kind": "residential",
            }
        )
    return legacy


def build_clash_yaml(package):
    if not package["enabled"] or package_is_expired(package):
        return ""
    nodes = package_nodes(package)
    if not nodes:
        return ""

    node_names = [name for name, _ in nodes]
    proxies = "\n".join(clash_node(entry, name) for name, entry in nodes)
    group_items = "\n".join(f"      - \"{name}\"" for name in node_names)
    rules = "\n".join(f"  - \"{rule}\"" for rule in load_rules())
    return f"""port: 7890
socks-port: 7891
allow-lan: true
mode: rule
log-level: info

proxies:
{proxies}

proxy-groups:
  - name: \"手动选择\"
    type: select
    proxies:
{group_items}
  - name: \"自动选择\"
    type: url-test
    proxies:
{group_items}
    url: \"https://www.gstatic.com/generate_204\"
    interval: 300
  - name: \"故障转移\"
    type: fallback
    proxies:
{group_items}
    url: \"https://www.gstatic.com/generate_204\"
    interval: 300

rules:
{rules}
"""


def build_shadowrocket_list(package):
    if not package["enabled"] or package_is_expired(package):
        return ""
    lines = [vless_uri(entry, name) for name, entry in package_nodes(package)]
    return "\n".join(lines) + ("\n" if lines else "")


def generate_subscriptions():
    SUBSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    with connect_manager_db() as con:
        packages = con.execute("SELECT * FROM packages ORDER BY id").fetchall()
    for package in packages:
        yaml_text = build_clash_yaml(package)
        list_text = build_shadowrocket_list(package)
        if yaml_text:
            write_text(SUBSCRIPTIONS_DIR / f"{package['sub_id']}.yaml", yaml_text)
        else:
            delete_subscription_files(package["sub_id"])
        if list_text:
            write_text(SUBSCRIPTIONS_DIR / f"{package['sub_id']}.list", list_text)
        elif not yaml_text:
            delete_subscription_files(package["sub_id"])
    update_deployment_manager_metadata()


def package_userinfo(package):
    usage = package_usage(package)
    return "; ".join(
        [
            f"upload={usage['upload']}",
            f"download={usage['download']}",
            f"total={bytes_from_gb(package['total_gb'])}",
            f"expire={int(package['expires_at'] or 0)}",
        ]
    )


def subscription_kind(headers, params):
    kind = (params.get("type") or params.get("target") or [""])[0].lower()
    if kind in ("shadowrocket", "list", "sr"):
        return "shadowrocket"
    if kind in ("clash", "yaml", "meta"):
        return "clash"
    ua = (headers.get("User-Agent") or "").lower()
    if "shadowrocket" in ua:
        return "shadowrocket"
    return "clash"


def package_subscription_response(package, kind):
    if kind == "shadowrocket":
        return build_shadowrocket_list(package), "text/plain; charset=utf-8"
    return build_clash_yaml(package), "text/yaml; charset=utf-8"


def delete_subscription_files(sub_id):
    for suffix in ("yaml", "list"):
        target = SUBSCRIPTIONS_DIR / f"{sub_id}.{suffix}"
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def update_deployment_manager_metadata():
    data = read_deployment()
    data.setdefault("server", DEFAULT_SERVER)
    data.setdefault("node_server", NODE_SERVER)
    with connect_manager_db() as con:
        packages = con.execute("SELECT * FROM packages ORDER BY id").fetchall()
        upstreams = con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()

    manager_packages = []
    for p in packages:
        sources = [
            {"email": item["email"], "port": int(item["port"])}
            for item in package_runtime_entries(p)
            if item["email"] and item["port"]
        ]
        bindings = package_binding_public_rows(p["id"])
        manager_packages.append(
            {
                "sub_id": p["sub_id"],
                "name": p["name"],
                "total_gb": p["total_gb"],
                "residential_gb": p["residential_gb"],
                "expire": int(p["expires_at"] or 0),
                "usage_sources": sources,
                "bindings": bindings,
            }
        )

    data["manager_packages"] = manager_packages
    public_packages = []
    for p in packages:
        bindings = package_binding_public_rows(p["id"])
        public_packages.append(
            {
                "sub_id": p["sub_id"],
                "name": p["name"],
                "direct_port": p["direct_port"],
                "residential_port": p["residential_port"],
                "upstream_id": p["upstream_id"],
                "upstream_ids": [int(row["upstream_id"]) for row in bindings],
            }
        )
    data["proxy3x_manager"] = {
        "updated_at": now(),
        "panel": "https://proxy3x.sjiaa.cc.cd/",
        "packages": public_packages,
        "upstreams": [
            {
                "id": u["id"],
                "protocol": u["protocol"],
                "host": u["host"],
                "port": u["port"],
                "remark": u["remark"],
                "assigned_to": u["assigned_to"],
                "status": u["status"],
            }
            for u in upstreams
        ],
    }
    write_deployment(data)


def import_existing_packages():
    init_db()
    data = read_deployment()
    entries = data.get("entries") or []
    imported = 0
    with connect_manager_db() as con:
        for entry in entries:
            if not entry.get("sub_id") or not entry.get("email") or not entry.get("port"):
                continue
            exists = con.execute("SELECT id FROM packages WHERE sub_id = ?", (entry["sub_id"],)).fetchone()
            if exists:
                continue
            direct_entry = dict(entry)
            direct_entry["node_name"] = "🇺🇸 娱乐流量"
            con.execute(
                """
                INSERT INTO packages(
                  name, sub_id, total_gb, residential_gb, notes, direct_email, direct_port,
                  direct_entry_json, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.get("sub_id"),
                    entry.get("sub_id"),
                    100,
                    50,
                    "从现有 3x-ui 订阅导入，历史用量保留在 3x-ui 数据库中。",
                    entry.get("email"),
                    int(entry.get("port")),
                    json_dumps(direct_entry),
                    default_expires_at(),
                    now(),
                    now(),
                ),
            )
            sync_client_limit(int(entry.get("port")), entry.get("email"), 100 * GB)
            imported += 1
    if imported:
        log_event("信息", f"已导入现有订阅 {imported} 个")
        generate_subscriptions()
    return imported


def b64_decode_text(text):
    text = (text or "").strip()
    text = re.sub(r"\s+", "", text)
    if not text:
        return ""
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        return raw.decode("utf-8", "replace")
    except Exception:
        return ""


def parse_subscription_userinfo(value):
    info = {}
    for part in str(value or "").split(";"):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip().lower()
        try:
            info[key] = int(float(val.strip()))
        except (TypeError, ValueError):
            continue
    return info


def fetch_subscription(url):
    req = Request(
        url,
        headers={
            "User-Agent": "proxy3x-manager/1.0",
            "Accept": "text/plain,text/yaml,application/yaml,*/*",
        },
    )
    opener = build_opener(ProxyHandler({}))
    with opener.open(req, timeout=35) as resp:
        text = resp.read().decode("utf-8", "replace")
        userinfo = parse_subscription_userinfo(resp.headers.get("Subscription-Userinfo"))
        total = int(userinfo.get("total") or 0)
        return {"text": text, "total_gb": gb_from_bytes(total) if total > 0 else 0}


def fetch_subscription_text(url):
    return fetch_subscription(url)["text"]


def clean_node_name(name, fallback="未命名节点"):
    name = unquote(str(name or "").strip())
    name = re.sub(r"\s+", " ", name)
    return name[:80] if name else fallback


def source_node_key(raw):
    return hashlib.sha1((raw or "").encode("utf-8", "ignore")).hexdigest()


def split_csv_like(text):
    items = []
    buf = ""
    quote_ch = ""
    for ch in text:
        if quote_ch:
            buf += ch
            if ch == quote_ch:
                quote_ch = ""
            continue
        if ch in ("'", '"'):
            quote_ch = ch
            buf += ch
            continue
        if ch == ",":
            items.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(buf.strip())
    return items


def yaml_value(text):
    text = str(text or "").strip()
    if len(text) >= 2 and text[0] in ("'", '"') and text[-1] == text[0]:
        return text[1:-1]
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def parse_inline_proxy(text):
    text = text.strip().strip("{}").strip()
    data = {}
    for item in split_csv_like(text):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        data[key.strip()] = yaml_value(value)
    return data


def parse_clash_proxies(text):
    proxies = []
    in_proxies = False
    current = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if re.match(r"^\S[^:]*:\s*$", raw):
            key = raw.split(":", 1)[0].strip()
            in_proxies = key == "proxies"
            if not in_proxies and current:
                proxies.append(current)
                current = None
            continue
        if not in_proxies:
            continue
        line = raw.strip()
        if line.startswith("- "):
            if current:
                proxies.append(current)
            body = line[2:].strip()
            current = parse_inline_proxy(body) if body.startswith("{") else {}
            if ":" in body and not body.startswith("{"):
                key, value = body.split(":", 1)
                current[key.strip()] = yaml_value(value)
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = yaml_value(value)
    if current:
        proxies.append(current)
    return proxies


def tls_from_query(params, enabled=False):
    tls = {}
    security = (params.get("security") or params.get("tls") or [""])[0]
    if enabled or security in ("tls", "reality"):
        tls["enabled"] = True
    sni = (params.get("sni") or params.get("servername") or params.get("peer") or [""])[0]
    if sni:
        tls["server_name"] = sni
    fp = (params.get("fp") or [""])[0]
    if fp:
        tls["utls"] = {"enabled": True, "fingerprint": fp}
    if (params.get("allowInsecure") or params.get("allow_insecure") or params.get("skip-cert-verify") or [""])[0] in ("1", "true", "True"):
        tls["insecure"] = True
    if security == "reality":
        reality = {"enabled": True}
        pbk = (params.get("pbk") or params.get("public-key") or [""])[0]
        sid = (params.get("sid") or params.get("short-id") or [""])[0]
        if pbk:
            reality["public_key"] = pbk
        if sid:
            reality["short_id"] = sid
        tls["reality"] = reality
    return tls


def uri_transport(params):
    network = (params.get("type") or params.get("network") or [""])[0]
    if network == "ws":
        headers = {}
        host = (params.get("host") or [""])[0]
        if host:
            headers["Host"] = host
        return {"type": "ws", "path": (params.get("path") or ["/"])[0] or "/", "headers": headers}
    if network == "grpc":
        service = (params.get("serviceName") or params.get("service_name") or [""])[0]
        data = {"type": "grpc"}
        if service:
            data["service_name"] = service
        return data
    return None


def vmess_transport(cfg):
    net = str(cfg.get("net") or cfg.get("network") or "").lower()
    if net == "ws":
        headers = {}
        host = cfg.get("host") or ""
        if host:
            headers["Host"] = host
        return {"type": "ws", "path": cfg.get("path") or "/", "headers": headers}
    if net == "grpc":
        service = cfg.get("path") or cfg.get("serviceName") or ""
        data = {"type": "grpc"}
        if service:
            data["service_name"] = service
        return data
    return None


def clash_transport(item):
    net = str(item.get("network") or item.get("net") or "").lower()
    if net == "ws":
        headers = {}
        host = item.get("host") or item.get("Host") or item.get("ws-host")
        if host:
            headers["Host"] = host
        return {"type": "ws", "path": item.get("path") or item.get("ws-path") or "/", "headers": headers}
    if net == "grpc":
        service = item.get("grpc-service-name") or item.get("serviceName") or item.get("service_name")
        data = {"type": "grpc"}
        if service:
            data["service_name"] = service
        return data
    return None


def parse_uri_node(line):
    line = (line or "").strip()
    if not line or "://" not in line:
        return None
    scheme = line.split("://", 1)[0].lower()
    if scheme == "vmess":
        decoded = b64_decode_text(line.split("://", 1)[1])
        cfg = json.loads(decoded or "{}")
        name = clean_node_name(cfg.get("ps") or cfg.get("name"))
        server = cfg.get("add") or cfg.get("server") or ""
        port = int(cfg.get("port") or 0)
        config = {
            "type": "vmess",
            "server": server,
            "server_port": port,
            "uuid": cfg.get("id") or cfg.get("uuid") or "",
            "security": cfg.get("scy") or cfg.get("security") or "auto",
            "alter_id": int(cfg.get("aid") or 0),
        }
        if str(cfg.get("tls") or "").lower() == "tls":
            config["tls"] = {"enabled": True, "server_name": cfg.get("sni") or cfg.get("host") or server}
            if str(cfg.get("allowInsecure") or cfg.get("allow_insecure") or cfg.get("skip-cert-verify") or "").lower() in ("1", "true"):
                config["tls"]["insecure"] = True
        transport = vmess_transport(cfg)
        if transport:
            config["transport"] = transport
        return {"name": name, "protocol": "vmess", "server": server, "port": port, "raw_uri": line, "config": config}

    parsed = urlparse(line)
    params = parse_qs(parsed.query)
    name = clean_node_name(parsed.fragment)
    server = parsed.hostname or ""
    port = int(parsed.port or 0)
    config = {"type": scheme, "server": server, "server_port": port}
    if scheme == "vless":
        config["uuid"] = unquote(parsed.username or "")
        flow = (params.get("flow") or [""])[0]
        if flow:
            config["flow"] = flow
        tls = tls_from_query(params)
        if tls:
            config["tls"] = tls
        transport = uri_transport(params)
        if transport:
            config["transport"] = transport
    elif scheme == "trojan":
        config["password"] = unquote(parsed.username or "")
        tls = tls_from_query(params, True)
        if tls:
            config["tls"] = tls
        transport = uri_transport(params)
        if transport:
            config["transport"] = transport
    elif scheme in ("socks", "socks5"):
        config["type"] = "socks"
        config["version"] = "5"
        if parsed.username:
            config["username"] = unquote(parsed.username)
        if parsed.password:
            config["password"] = unquote(parsed.password)
    elif scheme == "http":
        if parsed.username:
            config["username"] = unquote(parsed.username)
        if parsed.password:
            config["password"] = unquote(parsed.password)
    elif scheme == "ss":
        user = unquote(parsed.username or "")
        if not parsed.hostname:
            body = line.split("://", 1)[1].split("#", 1)[0]
            decoded = b64_decode_text(body)
            if decoded:
                return parse_uri_node(f"ss://{decoded}#{quote(name)}")
        if parsed.password:
            method, pwd = user, unquote(parsed.password)
        elif ":" in user:
            method, pwd = user.split(":", 1)
        else:
            decoded = b64_decode_text(user)
            method, pwd = decoded.split(":", 1) if ":" in decoded else ("", "")
        config["type"] = "shadowsocks"
        config["method"] = method
        config["password"] = pwd
    else:
        return None
    if not server or not port:
        return None
    return {"name": name or server, "protocol": config["type"], "server": server, "port": port, "raw_uri": line, "config": config}


def clash_proxy_to_node(item):
    proto = str(item.get("type") or "").lower()
    if proto not in SUPPORTED_SOURCE_PROTOCOLS:
        return None
    if proto == "shadowsocks":
        proto = "ss"
    server = str(item.get("server") or "")
    port = int(item.get("port") or item.get("server_port") or 0)
    if not server or not port:
        return None
    name = clean_node_name(item.get("name") or server)
    config = {"type": "shadowsocks" if proto == "ss" else ("socks" if proto == "socks5" else proto), "server": server, "server_port": port}
    for key in ("uuid", "password", "method", "flow", "alter_id", "security"):
        if item.get(key) not in (None, ""):
            config[key] = item.get(key)
    if proto in ("ss", "shadowsocks") and item.get("cipher") and not config.get("method"):
        config["method"] = item.get("cipher")
    if proto == "vless" and item.get("id") and not config.get("uuid"):
        config["uuid"] = item.get("id")
    if proto == "vmess":
        config.setdefault("security", "auto")
        config["alter_id"] = int(config.get("alter_id") or item.get("alterId") or 0)
    if proto in ("vless", "trojan", "vmess"):
        tls_enabled = bool(item.get("tls")) or str(item.get("network") or "") == "ws"
        if tls_enabled:
            tls = {"enabled": True}
            sni = item.get("servername") or item.get("sni") or item.get("server_name")
            if sni:
                tls["server_name"] = sni
            if item.get("skip-cert-verify") is True or str(item.get("skip-cert-verify") or item.get("allow-insecure") or "").lower() in ("1", "true"):
                tls["insecure"] = True
            fp = item.get("client-fingerprint") or item.get("fingerprint")
            if fp:
                tls["utls"] = {"enabled": True, "fingerprint": fp}
            reality = item.get("reality-opts") or item.get("reality_opts")
            if isinstance(reality, dict):
                tls["reality"] = {
                    "enabled": True,
                    "public_key": reality.get("public-key") or reality.get("public_key") or "",
                    "short_id": reality.get("short-id") or reality.get("short_id") or "",
                }
            elif item.get("pbk") or item.get("public-key"):
                tls["reality"] = {
                    "enabled": True,
                    "public_key": item.get("pbk") or item.get("public-key") or "",
                    "short_id": item.get("sid") or item.get("short-id") or "",
                }
            config["tls"] = tls
        transport = clash_transport(item)
        if transport:
            config["transport"] = transport
    raw = json_dumps(item)
    return {"name": name, "protocol": config["type"], "server": server, "port": port, "raw_uri": raw, "config": config}


def parse_subscription_nodes(text):
    text = (text or "").strip()
    if not text:
        return []
    body = text
    if "://" not in body and "proxies:" not in body:
        decoded = b64_decode_text(body)
        if decoded:
            body = decoded
    nodes = []
    if "proxies:" in body:
        for item in parse_clash_proxies(body):
            node = clash_proxy_to_node(item)
            if node:
                nodes.append(node)
    for line in body.splitlines():
        line = line.strip()
        if not line or "://" not in line:
            continue
        node = parse_uri_node(line)
        if node:
            nodes.append(node)
    seen = set()
    result = []
    for node in nodes:
        key = source_node_key(node.get("raw_uri") or json_dumps(node.get("config")))
        if key in seen:
            continue
        seen.add(key)
        node["node_key"] = key
        result.append(node)
    return result


def next_socks_port(con):
    used = {int(row["listen_port"]) for row in con.execute("SELECT listen_port FROM socks_endpoints").fetchall()}
    for port in range(SOCKS_PORT_START, SOCKS_PORT_END + 1):
        if port in used:
            continue
        return port
    raise RuntimeError(f"{SOCKS_PORT_START}-{SOCKS_PORT_END} 没有可用 SOCKS5 端口")


def socks_endpoint_uri(row, host=None):
    host = host or node_host()
    user = quote(row["username"] or "", safe="")
    pwd = quote(row["password"] or "", safe="")
    return f"socks5://{user}:{pwd}@{host}:{int(row['listen_port'])}"


def refresh_socks_source(source_id):
    init_db()
    current = now()
    with connect_manager_db() as con:
        src = con.execute("SELECT * FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
        if not src:
            raise ValueError("订阅源不存在")
        try:
            sub = fetch_subscription(src["url"])
            if not sub["text"].strip():
                raise RuntimeError("订阅接口返回空内容，请检查 token、套餐状态或源站订阅服务")
            nodes = parse_subscription_nodes(sub["text"])
            if not nodes:
                raise RuntimeError("订阅内容里没有可识别节点")
            for node in nodes:
                con.execute(
                    """
                    INSERT INTO socks_nodes(
                      source_id, node_key, name, protocol, server, port, raw_uri,
                      config_json, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '未检测', ?, ?)
                    ON CONFLICT(source_id, node_key) DO UPDATE SET
                      name = excluded.name,
                      protocol = excluded.protocol,
                      server = excluded.server,
                      port = excluded.port,
                      raw_uri = excluded.raw_uri,
                      config_json = excluded.config_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        source_id,
                        node["node_key"],
                        node["name"],
                        node["protocol"],
                        node["server"],
                        int(node["port"] or 0),
                        node["raw_uri"],
                        json_dumps(node["config"]),
                        current,
                        current,
                    ),
                )
            con.execute(
                """
                UPDATE socks_sources
                SET node_count = ?, total_gb = ?, last_refresh_at = ?, last_error = '', updated_at = ?
                WHERE id = ?
                """,
                (len(nodes), sub["total_gb"], current, current, source_id),
            )
            return len(nodes)
        except Exception as exc:
            con.execute(
                "UPDATE socks_sources SET last_error = ?, updated_at = ? WHERE id = ?",
                (str(exc), current, source_id),
            )
            con.commit()
            raise


def generate_socks_endpoints(source_id, expires_at=None):
    init_db()
    current = now()
    endpoint_expires_at = parse_upstream_expires_at(expires_at, current)
    with connect_manager_db() as con:
        src = con.execute("SELECT * FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
        if not src:
            raise ValueError("订阅源不存在")
        nodes = con.execute("SELECT * FROM socks_nodes WHERE source_id = ? ORDER BY id", (source_id,)).fetchall()
        if not nodes:
            raise ValueError("请先刷新订阅，解析出节点后再生成 SOCKS5")
        quota = round(float(src["total_gb"] or 0) / len(nodes), 3) if float(src["total_gb"] or 0) > 0 else 0
        made = 0
        for node in nodes:
            exists = con.execute("SELECT id FROM socks_endpoints WHERE node_id = ?", (node["id"],)).fetchone()
            if exists:
                continue
            port = next_socks_port(con)
            con.execute(
                """
                INSERT INTO socks_endpoints(
                  source_id, node_id, listen_port, username, password, quota_gb,
                  expires_at, remark, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    node["id"],
                    port,
                    f"px{source_id}_{node['id']}",
                    secrets.token_urlsafe(10),
                    quota,
                    endpoint_expires_at,
                    node["name"],
                    current,
                    current,
                ),
            )
            made += 1
        count = con.execute("SELECT COUNT(*) AS c FROM socks_endpoints WHERE source_id = ?", (source_id,)).fetchone()["c"]
        con.execute("UPDATE socks_sources SET endpoint_count = ?, updated_at = ? WHERE id = ?", (count, current, source_id))
    refresh_sing_box("生成 SOCKS5")
    log_event("信息", f"订阅源 {src['name']} 已生成 SOCKS5 {made} 个")
    return made


def endpoint_expired(row, at=None):
    expires_at = int(row["expires_at"] or 0)
    return bool(expires_at and expires_at <= int(at or now()))


def endpoint_used(row):
    return int(row["upload_bytes"] or 0) + int(row["download_bytes"] or 0)


def endpoint_public(row, host=None, reveal=False):
    item = dict(row)
    item["used_bytes"] = endpoint_used(item)
    item["used_gb"] = gb_from_bytes(item["used_bytes"])
    item["quota_bytes"] = bytes_from_gb(item["quota_gb"])
    item["usage_percent"] = round(item["used_bytes"] / item["quota_bytes"] * 100, 1) if item["quota_bytes"] > 0 else None
    item["expired"] = endpoint_expired(item)
    item["expires_at_text"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(item["expires_at"] or 0))) if item.get("expires_at") else ""
    if reveal:
        item["uri"] = socks_endpoint_uri(item, host)
    else:
        item["uri"] = ""
        item["username"] = mask_secret(item.get("username"))
        item["password"] = mask_secret(item.get("password"))
    return item


def node_public(row):
    item = dict(row)
    item.pop("raw_uri", None)
    item.pop("config_json", None)
    return item


def socks_factory_data(source_id=None, base_url=None):
    init_db()
    host = node_host()
    with connect_manager_db() as con:
        if source_id:
            sources = [con.execute("SELECT * FROM socks_sources WHERE id = ?", (source_id,)).fetchone()]
            sources = [row for row in sources if row]
        else:
            sources = con.execute("SELECT * FROM socks_sources ORDER BY id DESC").fetchall()
        result = []
        for src in sources:
            nodes = [node_public(row) for row in con.execute("SELECT * FROM socks_nodes WHERE source_id = ? ORDER BY id", (src["id"],)).fetchall()]
            endpoints = [
                endpoint_public(row, host)
                for row in con.execute(
                    """
                    SELECT e.*, n.name AS node_name, n.protocol, n.server, n.port AS node_port
                    FROM socks_endpoints e
                    JOIN socks_nodes n ON n.id = e.node_id
                    WHERE e.source_id = ?
                    ORDER BY e.listen_port
                    """,
                    (src["id"],),
                ).fetchall()
            ]
            used = sum(int(e["used_bytes"] or 0) for e in endpoints)
            quota = sum(int(e["quota_bytes"] or 0) for e in endpoints)
            item = dict(src)
            item["used_bytes"] = used
            item["used_gb"] = gb_from_bytes(used)
            item["endpoint_quota_bytes"] = quota
            item["endpoint_quota_gb"] = gb_from_bytes(quota)
            item["usage_percent"] = round(used / quota * 100, 1) if quota > 0 else None
            item["detail_url"] = f"{(base_url or '').rstrip('/')}/socks-sources/{src['id']}" if base_url else f"/socks-sources/{src['id']}"
            item["nodes"] = nodes
            item["endpoints"] = endpoints
            result.append(item)
    return result


def sing_box_outbound(row):
    cfg = json.loads(row["config_json"] or "{}")
    cfg["tag"] = f"source-node-{int(row['node_id'])}"
    tls = cfg.get("tls")
    if isinstance(tls, dict) and tls.get("enabled"):
        tls.setdefault("insecure", True)
    return cfg


def write_sing_box_config():
    current = now()
    with connect_manager_db() as con:
        rows = con.execute(
            """
            SELECT e.*, n.config_json, n.name AS node_name
            FROM socks_endpoints e
            JOIN socks_nodes n ON n.id = e.node_id
            JOIN socks_sources s ON s.id = e.source_id
            WHERE e.enabled = 1 AND s.enabled = 1
            ORDER BY e.listen_port
            """
        ).fetchall()
    inbounds = []
    outbounds = [{"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}]
    rules = []
    for row in rows:
        if endpoint_expired(row, current):
            continue
        used = endpoint_used(row)
        quota = bytes_from_gb(row["quota_gb"])
        if quota and used >= quota:
            continue
        in_tag = f"socks-in-{int(row['id'])}"
        out_tag = f"source-node-{int(row['node_id'])}"
        inbounds.append(
            {
                "type": "socks",
                "tag": in_tag,
                "listen": "0.0.0.0",
                "listen_port": int(row["listen_port"]),
                "users": [{"username": row["username"], "password": row["password"]}],
            }
        )
        out = sing_box_outbound(row)
        outbounds.append(out)
        rules.append({"inbound": [in_tag], "action": "route", "outbound": out_tag})
    cfg = {
        "log": {"level": "info"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": rules, "final": "block"},
    }
    if ENABLE_SING_BOX_STATS:
        cfg["experimental"] = {
            "v2ray_api": {
                "listen": SING_BOX_API_LISTEN,
                "stats": {
                    "enabled": True,
                    "inbounds": [item["tag"] for item in inbounds],
                    "outbounds": [item["tag"] for item in outbounds if item["tag"].startswith("source-node-")],
                    "users": [row["username"] for row in rows],
                },
            }
        }
    write_text(SING_BOX_CONFIG_PATH, pretty_json(cfg))
    return len(inbounds)


def reload_sing_box_best_effort(action="刷新 sing-box"):
    if os.name == "nt" or not SING_BOX_SERVICE:
        return False
    result = subprocess.run(
        ["systemctl", "restart", SING_BOX_SERVICE],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 0:
        log_event("信息", f"{action}：已重启 {SING_BOX_SERVICE}")
        return True
    detail = (result.stderr or result.stdout or "").strip()
    log_event("警告", f"{action}：sing-box 重启失败：{detail or result.returncode}")
    return False


def refresh_sing_box(action="刷新 sing-box"):
    if os.name == "nt" and "PROXY3X_CHAIN_DIR" not in os.environ:
        return 0
    try:
        count = write_sing_box_config()
    except OSError as exc:
        log_event("警告", f"{action}：写入 sing-box 配置失败：{exc}")
        return 0
    reload_sing_box_best_effort(action)
    return count


def set_socks_endpoint_enabled(endpoint_id, enabled):
    with connect_manager_db() as con:
        row = con.execute("SELECT id FROM socks_endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        if not row:
            raise ValueError("SOCKS5 不存在")
        con.execute(
            "UPDATE socks_endpoints SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now(), endpoint_id),
        )
    refresh_sing_box("切换 SOCKS5")


def update_socks_endpoint(endpoint_id, payload):
    try:
        quota_gb = float(payload.get("quota_gb") or 0)
    except (TypeError, ValueError):
        quota_gb = 0
    expires_at = parse_upstream_expires_at(payload.get("expires_at"))
    remark = payload.get("remark") or ""
    with connect_manager_db() as con:
        row = con.execute("SELECT id FROM socks_endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        if not row:
            raise ValueError("SOCKS5 不存在")
        con.execute(
            """
            UPDATE socks_endpoints
            SET quota_gb = ?, expires_at = ?, remark = ?, updated_at = ?
            WHERE id = ?
            """,
            (quota_gb, expires_at, remark, now(), endpoint_id),
        )
    refresh_sing_box("保存 SOCKS5")


def update_socks_endpoint_usage(endpoint_id, payload):
    try:
        upload = int(float(payload.get("upload_bytes") or 0))
        download = int(float(payload.get("download_bytes") or 0))
    except (TypeError, ValueError):
        raise ValueError("用量需要是数字")
    with connect_manager_db() as con:
        row = con.execute("SELECT id FROM socks_endpoints WHERE id = ?", (endpoint_id,)).fetchone()
        if not row:
            raise ValueError("SOCKS5 不存在")
        con.execute(
            """
            UPDATE socks_endpoints
            SET upload_bytes = ?, download_bytes = ?, updated_at = ?
            WHERE id = ?
            """,
            (max(0, upload), max(0, download), now(), endpoint_id),
        )
    refresh_sing_box("更新 SOCKS5 用量")


def parse_statsquery_value(text):
    total = 0
    for line in (text or "").splitlines():
        match = re.search(r"value:\s*(\d+)", line)
        if match:
            total += int(match.group(1))
            continue
        match = re.search(r"\b(\d+)\b", line.strip())
        if match:
            total += int(match.group(1))
    return total


def query_sing_box_stat(name):
    try:
        result = subprocess.run(
            [STATSQUERY_BIN, "api", "statsquery", "--server", SING_BOX_API_LISTEN, "-pattern", name],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到统计命令：{STATSQUERY_BIN}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"统计命令失败：{result.returncode}")
    return parse_statsquery_value(result.stdout)


def sync_socks_usage(source_id=None):
    with connect_manager_db() as con:
        sql = "SELECT * FROM socks_endpoints"
        args = []
        if source_id:
            sql += " WHERE source_id = ?"
            args.append(source_id)
        rows = con.execute(sql, args).fetchall()
        changed = 0
        for row in rows:
            tag = f"socks-in-{int(row['id'])}"
            up = query_sing_box_stat(f"inbound>>>{tag}>>>traffic>>>uplink")
            down = query_sing_box_stat(f"inbound>>>{tag}>>>traffic>>>downlink")
            con.execute(
                """
                UPDATE socks_endpoints
                SET upload_bytes = ?, download_bytes = ?, updated_at = ?
                WHERE id = ?
                """,
                (up, down, now(), row["id"]),
            )
            changed += 1
    return changed


def delete_socks_source(source_id):
    with connect_manager_db() as con:
        row = con.execute("SELECT name FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise ValueError("订阅源不存在")
        con.execute("DELETE FROM socks_endpoints WHERE source_id = ?", (source_id,))
        con.execute("DELETE FROM socks_nodes WHERE source_id = ?", (source_id,))
        con.execute("DELETE FROM socks_sources WHERE id = ?", (source_id,))
    refresh_sing_box("删除订阅源")
    log_event("信息", f"已删除订阅源 {row['name']}")


def parse_upstream_line(text):
    text = (text or "").strip()
    protocol = "socks"
    if "://" in text:
        parsed = urlparse(text)
        protocol = (parsed.scheme or "socks").lower()
        host = parsed.hostname or ""
        try:
            port = int(parsed.port or 0)
        except ValueError:
            port = 0
        username = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
    elif "@" in text:
        auth, target = text.rsplit("@", 1)
        if ":" not in auth or ":" not in target:
            raise ValueError("格式应为 socks5://账号:密码@IP:端口 或 IP:端口:账号:密码")
        username, password = auth.split(":", 1)
        host, port_text = target.rsplit(":", 1)
        port = int(port_text.strip())
        host = host.strip().strip("[]")
    else:
        parts = text.split(":")
        if len(parts) < 4:
            raise ValueError("格式应为 socks5://账号:密码@IP:端口 或 IP:端口:账号:密码")
        host = parts[0].strip()
        port = int(parts[1].strip())
        username = parts[2].strip()
        password = ":".join(parts[3:]).strip()
    host = (host or "").strip()
    username = (username or "").strip()
    password = (password or "").strip()
    if not host or not port or not username or not password:
        raise ValueError("SOCKS5 地址、端口、账号、密码不能为空")
    if protocol == "socks5":
        protocol = "socks"
    if protocol != "socks":
        raise ValueError("当前版本只支持 SOCKS5")
    return {"protocol": protocol, "host": host, "port": port, "username": username, "password": password}


def mask_secret(value):
    value = value or ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * max(4, len(value) - 4) + value[-2:]


def upstream_public(row):
    item = dict(row)
    try:
        internal = internal_socks_endpoint(item)
    except Exception:
        internal = None
    display_name = upstream_display_name(item)
    item["display_name"] = display_name
    item["socks5_name"] = item.get("remark") or item.get("assigned_to") or f"SOCKS5 #{item.get('id')}"
    item["source_node_name"] = internal["node_name"] if internal else ""
    item["password"] = mask_secret(item.get("password"))
    item["username"] = mask_secret(item.get("username"))
    quota_gb = float(item.get("quota_gb") or 0)
    item["quota_gb"] = quota_gb
    item["quota_bytes"] = bytes_from_gb(quota_gb)
    item["expired"] = upstream_is_expired(item)
    item["expires_at_text"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(item["expires_at"] or 0))) if item.get("expires_at") else ""
    return item


def upstream_display_name(upstream):
    try:
        internal = internal_socks_endpoint(upstream)
    except Exception:
        internal = None
    if internal:
        return internal["node_name"] or internal["remark"] or upstream.get("remark") or upstream.get("host") or "节点"
    return upstream.get("remark") or upstream.get("host") or "节点"


def tcp_connect(host, port, timeout=8):
    sock = socket.create_connection((host, int(port)), timeout=timeout)
    sock.settimeout(timeout)
    return sock


def test_http_proxy(upstream):
    auth = ""
    if upstream["username"] or upstream["password"]:
        token = base64.b64encode(f"{upstream['username']}:{upstream['password']}".encode()).decode()
        auth = f"Proxy-Authorization: Basic {token}\r\n"
    with tcp_connect(upstream["host"], upstream["port"]) as sock:
        req = (
            "CONNECT www.gstatic.com:443 HTTP/1.1\r\n"
            "Host: www.gstatic.com:443\r\n"
            f"{auth}"
            "Proxy-Connection: keep-alive\r\n\r\n"
        )
        sock.sendall(req.encode())
        data = sock.recv(256).decode("latin1", "ignore")
    if " 200 " not in data:
        raise RuntimeError("HTTP 代理连接失败")


def test_socks_proxy(upstream):
    host = b"www.gstatic.com"
    user = upstream["username"].encode()
    pwd = upstream["password"].encode()
    with tcp_connect(upstream["host"], upstream["port"]) as sock:
        sock.sendall(bytes([5, 2, 0, 2]))
        method = sock.recv(2)
        if len(method) != 2 or method[0] != 5:
            raise RuntimeError("握手失败")
        if method[1] == 2:
            sock.sendall(bytes([1, len(user)]) + user + bytes([len(pwd)]) + pwd)
            auth = sock.recv(2)
            if len(auth) != 2 or auth[1] != 0:
                raise RuntimeError("账号验证失败")
        elif method[1] != 0:
            raise RuntimeError("不支持的认证方式")
        sock.sendall(bytes([5, 1, 0, 3, len(host)]) + host + (443).to_bytes(2, "big"))
        reply = sock.recv(10)
        if len(reply) < 2 or reply[1] != 0:
            raise RuntimeError("连接目标失败")


def socks_connect_target(upstream, target_host, target_port, timeout=8):
    host = target_host.encode()
    user = (upstream.get("username") or "").encode()
    pwd = (upstream.get("password") or "").encode()
    sock = tcp_connect(upstream["host"], upstream["port"], timeout)
    try:
        sock.sendall(bytes([5, 2, 0, 2]))
        method = sock.recv(2)
        if len(method) != 2 or method[0] != 5:
            raise RuntimeError("握手失败")
        if method[1] == 2:
            sock.sendall(bytes([1, len(user)]) + user + bytes([len(pwd)]) + pwd)
            auth = sock.recv(2)
            if len(auth) != 2 or auth[1] != 0:
                raise RuntimeError("账号验证失败")
        elif method[1] != 0:
            raise RuntimeError("不支持的认证方式")
        sock.sendall(bytes([5, 1, 0, 3, len(host)]) + host + int(target_port).to_bytes(2, "big"))
        reply = sock.recv(10)
        if len(reply) < 2 or reply[1] != 0:
            raise RuntimeError("连接目标失败")
        return sock
    except Exception:
        sock.close()
        raise


def test_socks_speed(upstream, max_bytes=1024 * 1024, timeout=12):
    target_host = "speed.cloudflare.com"
    path = f"/__down?bytes={int(max_bytes)}"
    body_bytes = 0
    header_done = False
    started = time.monotonic()
    with socks_connect_target(upstream, target_host, 80, timeout) as sock:
        latency_ms = int((time.monotonic() - started) * 1000)
        download_started = time.monotonic()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {target_host}\r\n"
            "User-Agent: proxy3x-speed-test\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(req.encode("ascii"))
        while body_bytes < max_bytes:
            chunk = sock.recv(65536)
            if not chunk:
                break
            if not header_done:
                marker = chunk.find(b"\r\n\r\n")
                if marker < 0:
                    continue
                header_done = True
                chunk = chunk[marker + 4 :]
            body_bytes += len(chunk)
    elapsed = max(time.monotonic() - download_started, 0.001)
    if body_bytes <= 0:
        raise RuntimeError("测速没有下载到数据")
    return latency_ms, int(body_bytes / elapsed)


def endpoint_speed_upstream(row):
    return {
        "protocol": "socks",
        "host": "127.0.0.1",
        "port": int(row["listen_port"]),
        "username": row["username"],
        "password": row["password"],
    }


def speed_test_socks_endpoint(endpoint_id):
    current = now()
    error = ""
    with connect_manager_db() as con:
        row = con.execute(
            """
            SELECT e.*, s.enabled AS source_enabled, n.id AS node_id, n.name AS node_name
            FROM socks_endpoints e
            JOIN socks_sources s ON s.id = e.source_id
            JOIN socks_nodes n ON n.id = e.node_id
            WHERE e.id = ?
            """,
            (endpoint_id,),
        ).fetchone()
        if not row:
            raise ValueError("SOCKS5 不存在")
        if not row["enabled"] or not row["source_enabled"] or endpoint_expired(row, current):
            raise ValueError("SOCKS5 未启用或已到期")
        try:
            latency, speed = test_socks_speed(endpoint_speed_upstream(row))
            con.execute(
                """
                UPDATE socks_endpoints
                SET latency_ms = ?, speed_bps = ?, last_speed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (latency, speed, current, current, endpoint_id),
            )
            con.execute(
                """
                UPDATE socks_nodes
                SET status = '可用', latency_ms = ?, speed_bps = ?, last_speed_at = ?, last_error = '', updated_at = ?
                WHERE id = ?
                """,
                (latency, speed, current, current, row["node_id"]),
            )
            return latency, speed
        except Exception as exc:
            error = str(exc) or type(exc).__name__
            con.execute(
                """
                UPDATE socks_endpoints
                SET latency_ms = 0, speed_bps = 0, last_speed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (current, current, endpoint_id),
            )
            con.execute(
                """
                UPDATE socks_nodes
                SET status = '不可用', latency_ms = 0, speed_bps = 0, last_speed_at = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (current, error, current, row["node_id"]),
            )
    raise RuntimeError(error)


def speed_test_upstream(upstream_id):
    current = now()
    error = ""
    with connect_manager_db() as con:
        row = con.execute("SELECT * FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
        if not row:
            raise ValueError("SOCKS5 不存在")
        item = dict(row)
        if upstream_is_expired(item):
            con.execute(
                "UPDATE upstreams SET status = '不可用', last_error = 'SOCKS5: 已到期', updated_at = ? WHERE id = ?",
                (current, upstream_id),
            )
            raise ValueError("SOCKS5 已到期")
        internal = internal_socks_endpoint(item)
        target = item
        if internal:
            target = dict(item)
            target["host"] = "127.0.0.1"
        try:
            latency, speed = test_socks_speed(target)
            con.execute(
                """
                UPDATE upstreams
                SET status = '可用', last_error = '', latency_ms = ?, speed_bps = ?, last_speed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (latency, speed, current, current, upstream_id),
            )
            if internal:
                con.execute(
                    """
                    UPDATE socks_endpoints
                    SET latency_ms = ?, speed_bps = ?, last_speed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (latency, speed, current, current, internal["id"]),
                )
                con.execute(
                    """
                    UPDATE socks_nodes
                    SET status = '可用', latency_ms = ?, speed_bps = ?, last_speed_at = ?, last_error = '', updated_at = ?
                    WHERE id = ?
                    """,
                    (latency, speed, current, current, internal["node_id"]),
                )
            return latency, speed
        except Exception as exc:
            error = str(exc) or type(exc).__name__
            con.execute(
                "UPDATE upstreams SET status = '不可用', last_error = ?, latency_ms = 0, speed_bps = 0, last_speed_at = ?, updated_at = ? WHERE id = ?",
                (error, current, current, upstream_id),
            )
            if internal:
                con.execute(
                    "UPDATE socks_endpoints SET latency_ms = 0, speed_bps = 0, last_speed_at = ?, updated_at = ? WHERE id = ?",
                    (current, current, internal["id"]),
                )
                con.execute(
                    "UPDATE socks_nodes SET status = '不可用', latency_ms = 0, speed_bps = 0, last_speed_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
                    (current, error, current, internal["node_id"]),
                )
    raise RuntimeError(error)


def internal_socks_endpoint(upstream):
    try:
        port = int(upstream.get("port") or 0)
    except (TypeError, ValueError):
        return None
    with connect_manager_db() as con:
        row = con.execute(
            """
            SELECT e.*, s.enabled AS source_enabled, n.name AS node_name
            FROM socks_endpoints e
            JOIN socks_sources s ON s.id = e.source_id
            JOIN socks_nodes n ON n.id = e.node_id
            WHERE e.listen_port = ? AND e.username = ? AND e.password = ?
            """,
            (port, upstream.get("username") or "", upstream.get("password") or ""),
        ).fetchone()
    if not row or not row["enabled"] or not row["source_enabled"] or endpoint_expired(row):
        return None
    return row


def check_upstream(upstream):
    internal = internal_socks_endpoint(upstream)
    if internal:
        upstream = dict(upstream)
        upstream["host"] = "127.0.0.1"
        test_socks_proxy(upstream)
        return "socks", ""
    try:
        test_socks_proxy(upstream)
        return "socks", ""
    except Exception as exc:
        msg = str(exc) or type(exc).__name__
        raise RuntimeError(f"SOCKS5: {msg}") from exc


def xray_outbound_for_upstream(row):
    row = dict(row)
    users = []
    if row["username"] or row["password"]:
        users = [{"user": row["username"], "pass": row["password"]}]
    address = row["host"]
    if internal_socks_endpoint(row):
        address = node_host()
    return {
        "tag": f"proxy3x-upstream-{row['id']}",
        "protocol": "socks",
        "settings": {
            "servers": [
                {
                    "address": address,
                    "port": int(row["port"]),
                    "users": users,
                }
            ]
        },
    }


def block_outbound():
    return {"tag": BLOCK_OUTBOUND_TAG, "protocol": "blackhole", "settings": {}}


def inbound_tag_map():
    result = {}
    if not CHAIN_DB.exists():
        return result
    con = sqlite3.connect(f"file:{CHAIN_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        for row in con.execute("SELECT port, tag FROM inbounds WHERE port IS NOT NULL"):
            port = int(row["port"] or 0)
            if port:
                result[port] = row["tag"] or f"inbound-{port}"
    finally:
        con.close()
    return result


def fetch_xray_template():
    if not CHAIN_DB.exists():
        raise RuntimeError("没有找到 3x-ui 数据库")
    con = sqlite3.connect(f"file:{CHAIN_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT value FROM settings WHERE key = 'xrayTemplateConfig' LIMIT 1").fetchone()
    finally:
        con.close()
    if not row or not row["value"]:
        raise RuntimeError("读取 Xray 设置失败")
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError as exc:
        raise RuntimeError("Xray 设置不是有效 JSON") from exc


def write_xray_template(xray):
    if not CHAIN_DB.exists():
        raise RuntimeError("没有找到 3x-ui 数据库")
    backup_file(CHAIN_DB, "before-proxy3x-routes")
    con = sqlite3.connect(CHAIN_DB)
    try:
        cur = con.execute(
            "UPDATE settings SET value = ? WHERE key = 'xrayTemplateConfig'",
            (pretty_json(xray),),
        )
        if cur.rowcount == 0:
            con.execute(
                "INSERT INTO settings(key, value) VALUES ('xrayTemplateConfig', ?)",
                (pretty_json(xray),),
            )
        con.commit()
    finally:
        con.close()


def apply_xray_routes():
    with connect_manager_db() as con:
        packages = con.execute(
            """
            SELECT *
            FROM packages
            ORDER BY id
            """
        ).fetchall()
        upstreams = con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()
        bindings = con.execute(
            """
            SELECT b.*, u.expires_at AS upstream_expires_at
            FROM package_bindings b
            JOIN upstreams u ON u.id = b.upstream_id
            ORDER BY b.package_id, b.sort_order, b.id
            """
        ).fetchall()

    package_ports = set()
    binding_by_package = {}
    for row in bindings:
        binding_by_package.setdefault(int(row["package_id"]), []).append(row)
    for p in packages:
        for port in (p["direct_port"], p["residential_port"]):
            if port:
                package_ports.add(int(port))
    for row in bindings:
        if row["port"]:
            package_ports.add(int(row["port"]))
    tag_by_port = inbound_tag_map()
    package_tags = {tag_by_port.get(port, f"inbound-{port}") for port in package_ports}
    xray = fetch_xray_template()
    xray.setdefault("outbounds", [])
    xray.setdefault("routing", {})
    xray["routing"].setdefault("rules", [])

    xray["outbounds"] = [
        outbound
        for outbound in xray["outbounds"]
        if not str(outbound.get("tag", "")).startswith("proxy3x-upstream-")
        and str(outbound.get("tag", "")) != BLOCK_OUTBOUND_TAG
    ]
    if package_ports:
        xray["outbounds"].append(block_outbound())
    for row in upstreams:
        xray["outbounds"].append(xray_outbound_for_upstream(row))

    old_rules = xray["routing"].get("rules") or []
    kept_rules = []
    for rule in old_rules:
        inbound_tags = rule.get("inboundTag") or []
        outbound_tag = str(rule.get("outboundTag") or "")
        if outbound_tag.startswith("proxy3x-upstream-") or outbound_tag == BLOCK_OUTBOUND_TAG:
            continue
        if any(str(tag) in package_tags for tag in inbound_tags):
            continue
        kept_rules.append(rule)

    new_rules = []
    current = now()
    for p in packages:
        rows = binding_by_package.get(int(p["id"])) or []
        if rows:
            for row in rows:
                if not row["port"]:
                    continue
                blocked = (
                    not p["enabled"]
                    or not row["enabled"]
                    or package_is_expired(p, current)
                    or bool(row["upstream_expires_at"] and int(row["upstream_expires_at"]) <= current)
                )
                new_rules.append(
                    {
                        "type": "field",
                        "inboundTag": [tag_by_port.get(int(row["port"]), f"inbound-{int(row['port'])}")],
                        "outboundTag": BLOCK_OUTBOUND_TAG if blocked else f"proxy3x-upstream-{int(row['upstream_id'])}",
                    }
                )
            continue

        ports = [port for port in (p["direct_port"], p["residential_port"]) if port]
        if ports:
            blocked = not p["enabled"] or package_is_expired(p, current) or not p["upstream_id"]
            new_rules.append(
                {
                    "type": "field",
                    "inboundTag": [tag_by_port.get(int(port), f"inbound-{int(port)}") for port in ports],
                    "outboundTag": BLOCK_OUTBOUND_TAG if blocked else f"proxy3x-upstream-{int(p['upstream_id'])}",
                }
            )

    insert_at = 1 if kept_rules and kept_rules[0].get("inboundTag") == ["api"] else 0
    xray["routing"]["rules"] = kept_rules[:insert_at] + new_rules + kept_rules[insert_at:]
    write_xray_template(xray)
    restart_xui_container(f"已更新链式路由 {len(new_rules)} 条", "信息")


def traffic_map():
    result = {}
    if not CHAIN_DB.exists():
        return result
    con = sqlite3.connect(f"file:{CHAIN_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT i.id, i.port, i.enable AS inbound_enable, c.email, c.up, c.down, c.total, c.enable AS client_enable
            FROM inbounds i
            LEFT JOIN client_traffics c ON c.inbound_id = i.id
            """
        ).fetchall()
        for row in rows:
            key = (str(row["email"] or ""), int(row["port"] or 0))
            result[key] = dict(row)
    finally:
        con.close()
    return result


def restart_xray(client=None):
    try:
        client = client or get_panel_client()
        client.post_json("/panel/api/server/restartXrayService")
        return "api"
    except Exception as exc:
        if "HTTP Error 404" not in str(exc):
            raise
    return restart_xui_container("3x-ui 重启接口 404")


def restart_xui_container(reason, level="警告"):
    if not XUI_CONTAINER:
        raise RuntimeError(f"{reason}，且未配置 Docker 容器名")
    try:
        result = subprocess.run(
            ["docker", "restart", XUI_CONTAINER],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        raise RuntimeError(f"{reason}，Docker 兜底失败：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{reason}，Docker 兜底失败：{detail or result.returncode}")
    log_event(level, f"{reason}，已重启 Docker 容器 {XUI_CONTAINER} 兜底")
    return "docker"


def refresh_routes_best_effort(action):
    try:
        apply_xray_routes()
        return True
    except Exception as exc:
        log_event("警告", f"{action}：路由刷新失败：{exc}")
        if os.name == "nt":
            return False
        if "HTTP Error 404" in str(exc):
            restart_xui_container(f"{action}：3x-ui 路由接口 404")
            return False
        raise


def delete_xui_inbounds(ports, emails):
    ports = [int(port) for port in ports if port]
    emails = [email for email in emails if email]
    if not ports or not CHAIN_DB.exists():
        return 0
    backup_file(CHAIN_DB, "before-proxy3x-delete-package")
    con = sqlite3.connect(CHAIN_DB)
    con.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in ports)
        rows = con.execute(f"SELECT id FROM inbounds WHERE port IN ({placeholders})", ports).fetchall()
        inbound_ids = [int(row["id"]) for row in rows]
        if inbound_ids:
            id_placeholders = ",".join("?" for _ in inbound_ids)
            con.execute(f"DELETE FROM client_traffics WHERE inbound_id IN ({id_placeholders})", inbound_ids)
            con.execute(f"DELETE FROM inbounds WHERE id IN ({id_placeholders})", inbound_ids)
        if emails:
            email_placeholders = ",".join("?" for _ in emails)
            con.execute(f"DELETE FROM inbound_client_ips WHERE client_email IN ({email_placeholders})", emails)
        con.commit()
        return len(inbound_ids)
    finally:
        con.close()


def disable_xui_inbounds(ports, emails):
    ports = [int(port) for port in ports if port]
    emails = [email for email in emails if email]
    if not ports or not CHAIN_DB.exists():
        return 0
    backup_file(CHAIN_DB, "before-proxy3x-disable-package")
    con = sqlite3.connect(CHAIN_DB)
    con.row_factory = sqlite3.Row
    changed = 0
    try:
        placeholders = ",".join("?" for _ in ports)
        rows = con.execute(f"SELECT id, settings FROM inbounds WHERE port IN ({placeholders})", ports).fetchall()
        for row in rows:
            settings = json.loads(row["settings"] or "{}")
            for client in settings.get("clients") or []:
                if not emails or client.get("email") in emails:
                    client["enable"] = False
            con.execute("UPDATE inbounds SET enable = 0, settings = ? WHERE id = ?", (json_dumps(settings), row["id"]))
            con.execute("UPDATE client_traffics SET enable = 0 WHERE inbound_id = ?", (row["id"],))
            changed += 1
        con.commit()
        return changed
    finally:
        con.close()


def delete_package(package_id):
    init_db()
    with connect_manager_db() as con:
        row = con.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not row:
            raise ValueError("套餐不存在")
        package = dict(row)
        entries = package_runtime_entries(package)
        con.execute("DELETE FROM package_bindings WHERE package_id = ?", (package_id,))
        con.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    ports = [item["port"] for item in entries]
    emails = [item["email"] for item in entries]
    disabled = disable_xui_inbounds(ports, emails)
    removed = delete_xui_inbounds(ports, emails)
    delete_subscription_files(package["sub_id"])
    generate_subscriptions()
    refresh_routes_best_effort(f"{package['name']} 删除后刷新")
    log_event("信息", f"已删除用户套餐 {package['name']}，禁用入站 {disabled} 个，清理入站 {removed} 个")
    return "已删除套餐，旧订阅节点已失效"


def finish_package_delete(package):
    entries = package_runtime_entries(package)
    removed_inbounds = delete_xui_inbounds(
        [item["port"] for item in entries],
        [item["email"] for item in entries],
    )
    refresh_routes_best_effort(f"{package['name']} 删除后台清理")
    generate_subscriptions()
    log_event("信息", f"{package['name']} 删除后台清理完成，清理入站 {removed_inbounds} 个")


def sync_client_limit(port, email, total_bytes):
    if not port or not email or not CHAIN_DB.exists():
        return False
    con = sqlite3.connect(CHAIN_DB)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT id, total, settings FROM inbounds WHERE port = ?", (int(port),)).fetchone()
        if not row:
            return False
        try:
            settings = json.loads(row["settings"] or "{}")
        except json.JSONDecodeError:
            settings = {}
        changed = int(row["total"] or 0) != int(total_bytes)
        for client in settings.get("clients") or []:
            if client.get("email") == email and int(client.get("totalGB") or 0) != int(total_bytes):
                client["totalGB"] = int(total_bytes)
                changed = True
        traffic = con.execute(
            "SELECT total FROM client_traffics WHERE inbound_id = ? AND email = ?",
            (row["id"], email),
        ).fetchone()
        if traffic and int(traffic["total"] or 0) != int(total_bytes):
            changed = True
        if not changed:
            return False
        backup_file(CHAIN_DB, "before-proxy3x-limit")
        con.execute(
            "UPDATE inbounds SET total = ?, settings = ? WHERE id = ?",
            (int(total_bytes), json_dumps(settings), row["id"]),
        )
        con.execute(
            "UPDATE client_traffics SET total = ? WHERE inbound_id = ? AND email = ?",
            (int(total_bytes), row["id"], email),
        )
        con.commit()
        return True
    finally:
        con.close()


def package_usage(package, traffic=None):
    traffic = traffic or traffic_map()
    entries = package_runtime_entries(package)
    upload = 0
    download = 0
    direct_used = 0
    residential_used = 0
    runtime_enabled = True
    for item in entries:
        row = traffic.get((item["email"], int(item["port"] or 0)), {})
        up = int(row.get("up") or 0)
        down = int(row.get("down") or 0)
        used = up + down
        upload += up
        download += down
        if item["kind"] == "residential":
            residential_used += used
        else:
            direct_used += used
        runtime_enabled = runtime_enabled and bool(row.get("inbound_enable", item["enabled"]))
    total_used = direct_used + residential_used
    return {
        "upload": upload,
        "download": download,
        "direct_used": direct_used,
        "residential_used": residential_used,
        "total_used": total_used,
        "direct_used_gb": gb_from_bytes(direct_used),
        "residential_used_gb": gb_from_bytes(residential_used),
        "total_used_gb": gb_from_bytes(total_used),
        "direct_runtime_enabled": runtime_enabled if entries else bool(package["direct_enabled"]),
        "residential_runtime_enabled": bool(package["residential_enabled"]),
    }


def set_inbound_enabled(port, email, enabled):
    if not port or not CHAIN_DB.exists():
        return False
    backup_file(CHAIN_DB, "before-proxy3x-quota")
    con = sqlite3.connect(CHAIN_DB)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT id, settings FROM inbounds WHERE port = ?", (int(port),)).fetchone()
        if not row:
            return False
        inbound_id = int(row["id"])
        try:
            settings = json.loads(row["settings"] or "{}")
        except json.JSONDecodeError:
            settings = {}
        for client in settings.get("clients") or []:
            if client.get("email") == email:
                client["enable"] = bool(enabled)
        con.execute(
            "UPDATE inbounds SET enable = ?, settings = ? WHERE id = ?",
            (1 if enabled else 0, json_dumps(settings), inbound_id),
        )
        con.execute(
            "UPDATE client_traffics SET enable = ? WHERE inbound_id = ? AND email = ?",
            (1 if enabled else 0, inbound_id, email),
        )
        con.commit()
        restart_xray()
        return True
    finally:
        con.close()


def disable_expired_packages(con, packages):
    changed = 0
    current = now()
    for p in packages:
        if not p["enabled"] or not package_is_expired(p, current):
            continue
        entries = package_runtime_entries(p)
        for item in entries:
            set_inbound_enabled(item["port"], item["email"], False)
        binding_ids = [row["id"] for row in package_binding_all_rows(p["id"])]
        if binding_ids:
            placeholders = ",".join("?" for _ in binding_ids)
            con.execute(f"UPDATE package_bindings SET enabled = 0, updated_at = ? WHERE id IN ({placeholders})", [current, *binding_ids])
        con.execute(
            """
            UPDATE packages
            SET enabled = 0, direct_enabled = 0, residential_enabled = 0,
                disabled_reason = '已到期', updated_at = ?
            WHERE id = ?
            """,
            (current, p["id"]),
        )
        log_event("警告", f"{p['name']} 已到期，已关闭全部节点")
        changed += 1
    return changed


def disable_expired_upstreams(con):
    changed = 0
    current = now()
    rows = con.execute(
        """
        SELECT *
        FROM upstreams
        WHERE expires_at > 0 AND expires_at <= ?
          AND (status != '不可用' OR last_error != 'SOCKS5: 已到期')
        ORDER BY id
        """,
        (current,),
    ).fetchall()
    for row in rows:
        con.execute(
            "UPDATE upstreams SET status = '不可用', last_error = 'SOCKS5: 已到期', updated_at = ? WHERE id = ?",
            (current, row["id"]),
        )
        con.execute(
            "INSERT INTO events(level, message, created_at) VALUES (?, ?, ?)",
            ("警告", f"SOCKS5 {row['remark'] or row['host']} 已到期，绑定套餐已阻断", current),
        )
        changed += 1
    return changed


def disable_expired_socks_endpoints(con):
    changed = 0
    current = now()
    rows = con.execute(
        """
        SELECT e.*, n.name AS node_name
        FROM socks_endpoints e
        LEFT JOIN socks_nodes n ON n.id = e.node_id
        WHERE e.enabled = 1
        ORDER BY e.id
        """
    ).fetchall()
    for row in rows:
        used = endpoint_used(row)
        quota = bytes_from_gb(row["quota_gb"])
        reason = ""
        if endpoint_expired(row, current):
            reason = "已到期"
        elif quota and used >= quota:
            reason = "额度用完"
        if not reason:
            continue
        con.execute(
            "UPDATE socks_endpoints SET enabled = 0, updated_at = ? WHERE id = ?",
            (current, row["id"]),
        )
        con.execute(
            "INSERT INTO events(level, message, created_at) VALUES (?, ?, ?)",
            ("警告", f"订阅 SOCKS5 {row['remark'] or row['node_name']} {reason}，已停用", current),
        )
        changed += 1
    return changed


def enforce_quotas():
    init_db()
    changed = 0
    chain_changed = 0
    traffic = traffic_map()
    with connect_manager_db() as con:
        chain_changed += disable_expired_upstreams(con)
        socks_changed = disable_expired_socks_endpoints(con)
        changed += chain_changed + socks_changed
        packages = con.execute("SELECT * FROM packages ORDER BY id").fetchall()
        package_changed = disable_expired_packages(con, packages)
        changed += package_changed
        chain_changed += package_changed
        for p in packages:
            if package_is_expired(p):
                continue
            usage = package_usage(p, traffic)
            total_limit = bytes_from_gb(p["total_gb"])
            residential_limit = bytes_from_gb(p["residential_gb"])
            if residential_limit and usage["residential_used"] >= residential_limit and p["residential_enabled"]:
                if set_inbound_enabled(p["residential_port"], p["residential_email"], False):
                    con.execute("UPDATE packages SET residential_enabled = 0, updated_at = ? WHERE id = ?", (now(), p["id"]))
                    log_event("警告", f"{p['name']} 住宅流量达到 {p['residential_gb']}GB，已关闭住宅节点")
                    changed += 1
                    chain_changed += 1
            if total_limit and usage["total_used"] >= total_limit and p["enabled"]:
                for item in package_runtime_entries(p):
                    set_inbound_enabled(item["port"], item["email"], False)
                binding_ids = [row["id"] for row in package_binding_all_rows(p["id"])]
                if binding_ids:
                    placeholders = ",".join("?" for _ in binding_ids)
                    con.execute(
                        f"UPDATE package_bindings SET enabled = 0, updated_at = ? WHERE id IN ({placeholders})",
                        [now(), *binding_ids],
                    )
                con.execute(
                    "UPDATE packages SET enabled = 0, direct_enabled = 0, residential_enabled = 0, disabled_reason = '额度用完', updated_at = ? WHERE id = ?",
                    (now(), p["id"]),
                )
                log_event("警告", f"{p['name']} 总额度达到 {p['total_gb']}GB，已关闭全部节点")
                changed += 1
                chain_changed += 1
    if chain_changed:
        generate_subscriptions()
        refresh_routes_best_effort("巡检后刷新")
    if socks_changed:
            refresh_sing_box("巡检 SOCKS5")
    return changed


def ensure_residential_node(package_id):
    with connect_manager_db() as con:
        p = con.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        if not p:
            raise RuntimeError("套餐不存在")
        if not p["enabled"] or package_is_expired(p):
            raise RuntimeError("套餐已失效，不能补齐住宅节点")
        if not p["upstream_id"]:
            raise RuntimeError("请先选择家宽池")
        if p["residential_entry_json"] and p["residential_port"]:
            refresh_routes_best_effort("住宅节点刷新")
            generate_subscriptions()
            return "住宅节点已存在，已刷新路由和订阅"
        port = next_free_port()
        entry = make_inbound_best_effort(
            {
                "sub_id": p["sub_id"],
                "email": f"{p['sub_id']}-residential",
                "remark": f"{p['sub_id']}-residential",
                "node_name": "🇺🇸 住宅流量",
                "port": port,
                "total_bytes": bytes_from_gb(p["residential_gb"]),
            }
        )
        con.execute(
            """
            UPDATE packages
            SET residential_email = ?, residential_port = ?, residential_entry_json = ?,
                residential_enabled = 1, updated_at = ?
            WHERE id = ?
            """,
            (entry["email"], port, json_dumps(entry), now(), package_id),
        )
    refresh_routes_best_effort("创建住宅节点后刷新")
    generate_subscriptions()
    log_event("信息", f"已为 {p['name']} 创建住宅节点端口 {port}")
    return "已创建住宅节点"


def package_upstream_ids(payload):
    raw = payload.get("upstream_ids")
    if raw is None:
        raw = [payload.get("upstream_id")] if payload.get("upstream_id") else []
    if not isinstance(raw, list):
        raw = [raw]
    ids = []
    for item in raw:
        try:
            upstream_id = int(item)
        except (TypeError, ValueError):
            continue
        if upstream_id and upstream_id not in ids:
            ids.append(upstream_id)
    return ids


def default_upstream_ids():
    with connect_manager_db() as con:
        rows = con.execute(
            """
            SELECT id
            FROM upstreams
            WHERE protocol = 'socks'
              AND (expires_at = 0 OR expires_at > ?)
              AND status != '不可用'
            ORDER BY id
            """,
            (now(),),
        ).fetchall()
    return [int(row["id"]) for row in rows[:1]]


def load_upstream_map(ids):
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with connect_manager_db() as con:
        rows = con.execute(f"SELECT * FROM upstreams WHERE id IN ({placeholders})", ids).fetchall()
    return {int(row["id"]): dict(row) for row in rows}


def make_package_binding(package_id, package, upstream, order):
    display_name = upstream_display_name(upstream)
    port = next_free_port()
    email = f"{package['sub_id']}-u{upstream['id']}-{order + 1}"
    entry = make_inbound_best_effort(
        {
            "sub_id": package["sub_id"],
            "email": email,
            "remark": email,
            "node_name": display_name,
            "port": port,
            "total_bytes": bytes_from_gb(package["total_gb"]),
        }
    )
    current = now()
    with connect_manager_db() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO package_bindings(
              package_id, upstream_id, display_name, email, port, entry_json,
              enabled, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                package_id,
                int(upstream["id"]),
                display_name,
                email,
                port,
                json_dumps(entry),
                order,
                current,
                current,
            ),
        )
    return entry


def sync_package_bindings(package_id, upstream_ids):
    with connect_manager_db() as con:
        package = con.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        current_rows = con.execute("SELECT * FROM package_bindings WHERE package_id = ?", (package_id,)).fetchall()
    if not package:
        raise ValueError("套餐不存在")
    package = dict(package)
    upstreams = load_upstream_map(upstream_ids)
    if len(upstreams) != len(upstream_ids):
        raise ValueError("选择的 SOCKS5 不存在")

    current_by_upstream = {int(row["upstream_id"]): dict(row) for row in current_rows}
    remove_rows = [row for row in current_rows if int(row["upstream_id"]) not in upstream_ids]
    if remove_rows:
        disable_xui_inbounds([row["port"] for row in remove_rows], [row["email"] for row in remove_rows])
        delete_xui_inbounds([row["port"] for row in remove_rows], [row["email"] for row in remove_rows])

    first_entry = None
    first_upstream_id = upstream_ids[0] if upstream_ids else None
    for order, upstream_id in enumerate(upstream_ids):
        upstream = upstreams[upstream_id]
        current = current_by_upstream.get(upstream_id)
        display_name = upstream_display_name(upstream)
        if current:
            if not first_entry:
                first_entry = json.loads(current["entry_json"] or "{}")
            with connect_manager_db() as con:
                con.execute(
                    """
                    UPDATE package_bindings
                    SET display_name = ?, sort_order = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (display_name, order, now(), current["id"]),
                )
            sync_client_limit(current["port"], current["email"], bytes_from_gb(package["total_gb"]))
            continue
        entry = make_package_binding(package_id, package, upstream, order)
        if not first_entry:
            first_entry = entry

    with connect_manager_db() as con:
        if remove_rows:
            placeholders = ",".join("?" for _ in remove_rows)
            con.execute(f"DELETE FROM package_bindings WHERE id IN ({placeholders})", [row["id"] for row in remove_rows])
        first = con.execute(
            "SELECT * FROM package_bindings WHERE package_id = ? ORDER BY sort_order, id LIMIT 1",
            (package_id,),
        ).fetchone()
        con.execute(
            """
            UPDATE packages
            SET upstream_id = ?, direct_email = ?, direct_port = ?, direct_entry_json = ?,
                direct_node_enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                int(first_upstream_id) if first_upstream_id else None,
                first["email"] if first else "",
                int(first["port"]) if first and first["port"] else None,
                first["entry_json"] if first else "",
                1 if first else 0,
                now(),
                package_id,
            ),
        )


def create_package(payload):
    name = (payload.get("name") or "").strip()
    raw_sub_id = (payload.get("sub_id") or "").strip()
    if not name:
        raise ValueError("用户名不能为空")
    if not raw_sub_id:
        raise ValueError("订阅名不能为空")
    sub_id = slugify(raw_sub_id)
    if sub_id != raw_sub_id:
        raise ValueError("订阅名只能使用英文、数字、-、_")
    try:
        total_gb = float(payload.get("total_gb") or DEFAULT_PACKAGE_TOTAL_GB)
        residential_gb = float(payload.get("residential_gb") or 0)
    except (TypeError, ValueError):
        raise ValueError("额度需要填写数字")
    if total_gb <= 0:
        raise ValueError("总额度需要大于 0")
    upstream_ids = package_upstream_ids(payload) or default_upstream_ids()
    if not upstream_ids:
        raise ValueError("请先添加一个 SOCKS5 上游")
    upstreams = load_upstream_map(upstream_ids)
    if len(upstreams) != len(upstream_ids):
        raise ValueError("选择的 SOCKS5 不存在")
    notes = payload.get("notes") or ""
    expires_at = parse_expires_at(payload.get("expires_at"))
    with connect_manager_db() as con:
        if con.execute("SELECT id FROM packages WHERE sub_id = ?", (sub_id,)).fetchone():
            raise ValueError("订阅名已存在，请换一个")
    with connect_manager_db() as con:
        con.execute(
            """
            INSERT INTO packages(
              name, sub_id, total_gb, residential_gb, notes, upstream_id,
              direct_email, direct_port, direct_entry_json, expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                sub_id,
                total_gb,
                residential_gb,
                notes,
                int(upstream_ids[0]) if upstream_ids else None,
                "",
                None,
                "",
                expires_at,
                now(),
                now(),
            ),
        )
        package_id = con.execute("SELECT id FROM packages WHERE sub_id = ?", (sub_id,)).fetchone()["id"]
    sync_package_bindings(package_id, upstream_ids)
    log_event("信息", f"已新增用户 {name}")
    run_background("创建后刷新", finish_package_create, package_id)
    message = "用户已创建，链式路由和订阅正在后台刷新"
    return package_id, message


def finish_package_create(package_id):
    route_ok = refresh_routes_best_effort("创建后刷新")
    generate_subscriptions()
    msg = "链式路由和订阅已刷新" if route_ok else "订阅已刷新，路由接口 404 已重启容器兜底"
    with connect_manager_db() as con:
        row = con.execute("SELECT name FROM packages WHERE id = ?", (package_id,)).fetchone()
    if row:
        log_event("信息", f"{row['name']} 创建后刷新完成：{msg}")


def dashboard_data(base_url=None):
    init_db()
    import_existing_packages()
    traffic = traffic_map()
    with connect_manager_db() as con:
        packages = [dict(row) for row in con.execute("SELECT * FROM packages ORDER BY id").fetchall()]
        upstreams = [upstream_public(row) for row in con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()]
        events = [dict(row) for row in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()]
    package_items = []
    sub_base = (base_url or "https://vpn.sjiaa.cc.cd").rstrip("/")
    total_used = 0
    total_limit = 0
    residential_used = 0
    upstream_usage = {int(u["id"]): 0 for u in upstreams}
    for p in packages:
        bindings = package_binding_public_rows(p["id"])
        usage = package_usage(p, traffic)
        total_used += usage["total_used"]
        total_limit += bytes_from_gb(p["total_gb"])
        residential_used += usage["residential_used"]
        if bindings:
            used_each = int(usage["total_used"] / len(bindings)) if bindings else 0
            for binding in bindings:
                upstream_id = int(binding["upstream_id"])
                upstream_usage[upstream_id] = upstream_usage.get(upstream_id, 0) + used_each
        elif p.get("upstream_id"):
            upstream_usage[int(p["upstream_id"])] = upstream_usage.get(int(p["upstream_id"]), 0) + usage["total_used"]
        p.update(usage)
        p["bindings"] = bindings
        p["upstream_ids"] = [int(row["upstream_id"]) for row in bindings] or ([int(p["upstream_id"])] if p.get("upstream_id") else [])
        p["total_bytes"] = bytes_from_gb(p["total_gb"])
        p["residential_bytes"] = bytes_from_gb(p["residential_gb"])
        p["expired"] = package_is_expired(p)
        p["expires_at_text"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(p["expires_at"] or 0))) if p.get("expires_at") else ""
        p["clash_url"] = f"{sub_base}/api/v1/client/subscribe?token={quote(p['sub_id'])}&type=clash"
        p["shadowrocket_url"] = f"{sub_base}/api/v1/client/subscribe?token={quote(p['sub_id'])}&type=shadowrocket"
        p["shadowrocket_alt_url"] = f"https://{ALT_SUBSCRIPTION_DOMAIN}/{p['sub_id']}.list"
        p.pop("direct_entry_json", None)
        p.pop("residential_entry_json", None)
        package_items.append(p)
    for u in upstreams:
        used = upstream_usage.get(int(u["id"]), 0)
        u["used_bytes"] = used
        u["used_gb"] = gb_from_bytes(used)
        # 进度分母 = SOCKS5 额度（quota_bytes）；未设额度（0）时 usage_percent 为 None，前端不画进度条。
        quota_bytes = int(u.get("quota_bytes") or 0)
        u["usage_percent"] = round(used / quota_bytes * 100, 1) if quota_bytes > 0 else None
    return {
        "summary": {
            "package_count": len(packages),
            "upstream_count": len(upstreams),
            "total_used_gb": gb_from_bytes(total_used),
            "total_limit_gb": gb_from_bytes(total_limit),
            "residential_used_gb": gb_from_bytes(residential_used),
        },
        "packages": package_items,
        "upstreams": upstreams,
        "events": events,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "proxy3x-manager/1.0"

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route()

    def do_PUT(self):
        self.route()

    def do_DELETE(self):
        self.route()

    def route(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/v1/client/subscribe":
                self.serve_client_subscription(parsed)
                return
            if path.startswith("/api/"):
                self.handle_api(path)
                return
            self.serve_static(path)
        except Exception as exc:
            self.send_json({"ok": False, "message": str(exc)}, 500)

    def current_user(self):
        header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        jar.load(header)
        token = jar.get("proxy3x_session")
        return read_session(token.value if token else "")

    def require_auth(self):
        user = self.current_user()
        if not user:
            self.send_json({"ok": False, "message": "请先登录"}, 401)
            return None
        return user

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        data = self.rfile.read(length).decode("utf-8")
        return json.loads(data or "{}")

    def send_json(self, data, status=200, headers=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200, content_type="text/plain; charset=utf-8", headers=None):
        body = str(text or "").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def public_base_url(self):
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").strip()
        if not host:
            return "https://vpn.sjiaa.cc.cd"
        proto = (self.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip() or "https"
        return f"{proto}://{host}"

    def serve_client_subscription(self, parsed):
        params = parse_qs(parsed.query)
        token = (params.get("token") or params.get("sub_id") or [""])[0].strip()
        if not token:
            self.send_text("缺少订阅 token", 404)
            return
        with connect_manager_db() as con:
            package = con.execute("SELECT * FROM packages WHERE sub_id = ?", (token,)).fetchone()
        if not package or not package["enabled"] or package_is_expired(package):
            self.send_text("订阅不存在或已失效", 403)
            return
        kind = subscription_kind(self.headers, params)
        text, content_type = package_subscription_response(package, kind)
        if not text:
            self.send_text("订阅内容为空", 404)
            return
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Profile-Update-Interval", "3600")
        self.send_header("Subscription-Userinfo", package_userinfo(package))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def handle_api(self, path):
        if path == "/api/login" and self.command == "POST":
            payload = self.read_json()
            if verify_password(payload.get("username", ""), payload.get("password", "")):
                token = sign_session(payload.get("username", "admin"))
                self.send_json(
                    {"ok": True},
                    headers={"Set-Cookie": f"proxy3x_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_MAX_AGE}"},
                )
            else:
                self.send_json({"ok": False, "message": "用户名或密码不正确"}, 403)
            return
        if path == "/api/logout":
            self.send_json({"ok": True}, headers={"Set-Cookie": "proxy3x_session=; Path=/; Max-Age=0"})
            return
        if path == "/api/me":
            user = self.current_user()
            self.send_json({"ok": bool(user), "username": user})
            return
        if not self.require_auth():
            return

        if path == "/api/dashboard":
            self.send_json({"ok": True, "data": dashboard_data(self.public_base_url())})
            return
        if path == "/api/enforce" and self.command == "POST":
            changed = enforce_quotas()
            self.send_json({"ok": True, "message": f"额度巡检完成，变更 {changed} 项"})
            return
        if path == "/api/regenerate" and self.command == "POST":
            generate_subscriptions()
            route_ok = refresh_routes_best_effort("手动刷新订阅")
            self.send_json({"ok": True, "message": "订阅和路由已刷新" if route_ok else "订阅已刷新，路由刷新失败已写入日志"})
            return
        if path == "/api/socks-sources":
            if self.command == "GET":
                self.send_json({"ok": True, "data": socks_factory_data(base_url=self.public_base_url())})
                return
            if self.command == "POST":
                payload = self.read_json()
                name = (payload.get("name") or "").strip()
                url = (payload.get("url") or "").strip()
                if not name or not url:
                    self.send_json({"ok": False, "message": "名称和订阅链接不能为空"}, 400)
                    return
                try:
                    total_gb = float(payload.get("total_gb") or 0)
                except (TypeError, ValueError):
                    total_gb = 0
                with connect_manager_db() as con:
                    cur = con.execute(
                        """
                        INSERT INTO socks_sources(name, url, total_gb, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?)
                        """,
                        (name, url, total_gb, now(), now()),
                    )
                    source_id = cur.lastrowid
                try:
                    count = refresh_socks_source(source_id)
                except Exception as exc:
                    self.send_json({"ok": False, "message": f"订阅已保存，但刷新失败：{exc}", "data": {"id": source_id}}, 200)
                    return
                made = generate_socks_endpoints(source_id, payload.get("expires_at"))
                self.send_json({"ok": True, "message": f"已添加订阅源，解析节点 {count} 个，生成 SOCKS5 {made} 个", "data": {"id": source_id}})
                return
        match = re.match(r"^/api/socks-sources/(\d+)$", path)
        if match and self.command == "GET":
            rows = socks_factory_data(int(match.group(1)), self.public_base_url())
            if not rows:
                self.send_json({"ok": False, "message": "订阅源不存在"}, 404)
                return
            self.send_json({"ok": True, "data": rows[0]})
            return
        if match and self.command == "PUT":
            source_id = int(match.group(1))
            payload = self.read_json()
            with connect_manager_db() as con:
                row = con.execute("SELECT id FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
                if not row:
                    self.send_json({"ok": False, "message": "订阅源不存在"}, 404)
                    return
                old = con.execute("SELECT total_gb FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
                try:
                    total_gb = float(payload.get("total_gb")) if "total_gb" in payload else float(old["total_gb"] or 0)
                except (TypeError, ValueError):
                    total_gb = float(old["total_gb"] or 0)
                con.execute(
                    """
                    UPDATE socks_sources
                    SET name = ?, url = ?, total_gb = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ((payload.get("name") or "").strip(), (payload.get("url") or "").strip(), total_gb, now(), source_id),
                )
            self.send_json({"ok": True, "message": "已保存订阅源"})
            return
        if match and self.command == "DELETE":
            try:
                delete_socks_source(int(match.group(1)))
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
                return
            self.send_json({"ok": True, "message": "已删除订阅源"})
            return
        match = re.match(r"^/api/socks-sources/(\d+)/(refresh|generate|toggle|copy)$", path)
        if match and self.command == "POST":
            source_id = int(match.group(1))
            action = match.group(2)
            try:
                if action == "refresh":
                    count = refresh_socks_source(source_id)
                    refresh_sing_box("刷新订阅源")
                    self.send_json({"ok": True, "message": f"刷新完成，解析节点 {count} 个"})
                    return
                if action == "generate":
                    payload = self.read_json()
                    count = generate_socks_endpoints(source_id, payload.get("expires_at"))
                    self.send_json({"ok": True, "message": f"生成完成，新增 {count} 个 SOCKS5"})
                    return
                if action == "toggle":
                    payload = self.read_json()
                    enabled = bool(payload.get("enabled"))
                    with connect_manager_db() as con:
                        row = con.execute("SELECT id FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
                        if not row:
                            raise ValueError("订阅源不存在")
                        con.execute("UPDATE socks_sources SET enabled = ?, updated_at = ? WHERE id = ?", (1 if enabled else 0, now(), source_id))
                    refresh_sing_box("切换订阅源")
                    self.send_json({"ok": True, "message": "已启用订阅源" if enabled else "已停用订阅源"})
                    return
                if action == "copy":
                    with connect_manager_db() as con:
                        src = con.execute("SELECT id FROM socks_sources WHERE id = ?", (source_id,)).fetchone()
                        if not src:
                            raise ValueError("订阅源不存在")
                        items = con.execute(
                            """
                            SELECT e.*, n.name AS node_name, n.protocol, n.server, n.port AS node_port
                            FROM socks_endpoints e
                            JOIN socks_nodes n ON n.id = e.node_id
                            WHERE e.source_id = ?
                            ORDER BY e.listen_port
                            """,
                            (source_id,),
                        ).fetchall()
                    if not items:
                        raise ValueError("还没有生成 SOCKS5")
                    lines = [endpoint_public(e, node_host(), True)["uri"] for e in items]
                    self.send_json({"ok": True, "data": {"text": "\n".join(lines)}, "message": f"已生成 {len(lines)} 条"})
                    return
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
                return
        match = re.match(r"^/api/socks-sources/(\d+)/sync-usage$", path)
        if match and self.command == "POST":
            try:
                changed = sync_socks_usage(int(match.group(1)))
            except Exception as exc:
                self.send_json({"ok": False, "message": f"同步统计失败：{exc}"}, 500)
                return
            self.send_json({"ok": True, "message": f"已同步 {changed} 个 SOCKS5 用量"})
            return
        match = re.match(r"^/api/socks-endpoints/(\d+)/(toggle|reveal|speed-test)$", path)
        if match and self.command == "POST":
            endpoint_id = int(match.group(1))
            action = match.group(2)
            try:
                if action == "toggle":
                    payload = self.read_json()
                    set_socks_endpoint_enabled(endpoint_id, bool(payload.get("enabled")))
                    self.send_json({"ok": True, "message": "已启用 SOCKS5" if payload.get("enabled") else "已停用 SOCKS5"})
                    return
                if action == "reveal":
                    with connect_manager_db() as con:
                        row = con.execute(
                            """
                            SELECT e.*, n.name AS node_name, n.protocol, n.server, n.port AS node_port
                            FROM socks_endpoints e
                            JOIN socks_nodes n ON n.id = e.node_id
                            WHERE e.id = ?
                            """,
                            (endpoint_id,),
                        ).fetchone()
                    if not row:
                        raise ValueError("SOCKS5 不存在")
                    self.send_json({"ok": True, "data": endpoint_public(row, node_host(), True)})
                    return
                if action == "speed-test":
                    latency, speed = speed_test_socks_endpoint(endpoint_id)
                    self.send_json(
                        {
                            "ok": True,
                            "message": f"测速完成：{latency} ms / {format_speed(speed)}",
                            "data": {"latency_ms": latency, "speed_bps": speed},
                        }
                    )
                    return
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
                return
            except Exception as exc:
                self.send_json({"ok": False, "message": f"测速失败：{exc}"}, 200)
                return
        match = re.match(r"^/api/socks-endpoints/(\d+)$", path)
        if match and self.command == "PUT":
            try:
                update_socks_endpoint(int(match.group(1)), self.read_json())
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
                return
            self.send_json({"ok": True, "message": "已保存 SOCKS5"})
            return
        match = re.match(r"^/api/socks-endpoints/(\d+)/usage$", path)
        if match and self.command == "POST":
            try:
                update_socks_endpoint_usage(int(match.group(1)), self.read_json())
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 400)
                return
            self.send_json({"ok": True, "message": "已更新用量"})
            return
        if path == "/api/upstreams":
            if self.command == "GET":
                with connect_manager_db() as con:
                    rows = [upstream_public(row) for row in con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()]
                self.send_json({"ok": True, "data": rows})
                return
            if self.command == "POST":
                payload = self.read_json()
                item = parse_upstream_line(payload.get("line") or "")
                remark = payload.get("remark") or ""
                if not remark:
                    internal = internal_socks_endpoint(item)
                    if internal:
                        remark = internal["node_name"] or internal["remark"] or ""
                assigned_to = payload.get("assigned_to") or ""
                try:
                    quota_gb = float(payload.get("quota_gb") or 0)
                except (TypeError, ValueError):
                    quota_gb = 0
                expires_at = parse_upstream_expires_at(payload.get("expires_at"))
                with connect_manager_db() as con:
                    con.execute(
                        """
                        INSERT INTO upstreams(protocol, host, port, username, password, remark, assigned_to, quota_gb, expires_at, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["protocol"],
                            item["host"],
                            item["port"],
                            item["username"],
                            item["password"],
                            remark,
                            assigned_to,
                            quota_gb,
                            expires_at,
                            now(),
                            now(),
                        ),
                    )
                log_event("信息", f"已新增 SOCKS5：{remark or item['host']}")
                self.send_json({"ok": True, "message": "SOCKS5 已保存"})
                return
        match = re.match(r"^/api/upstreams/(\d+)/reveal$", path)
        if match and self.command == "GET":
            upstream_id = int(match.group(1))
            with connect_manager_db() as con:
                row = con.execute("SELECT * FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
            if not row:
                self.send_json({"ok": False, "message": "SOCKS5 不存在"}, 404)
                return
            item = dict(row)
            scheme = "socks5" if str(item.get("protocol") or "").startswith("socks") else (item.get("protocol") or "http")
            user = quote(item.get("username") or "", safe="")
            pwd = quote(item.get("password") or "", safe="")
            host = item.get("host") or ""
            port = item.get("port") or ""
            uri = f"{scheme}://{user}:{pwd}@{host}:{port}" if (user or pwd) else f"{scheme}://{host}:{port}"
            data = {
                "id": item.get("id"),
                "protocol": item.get("protocol") or "",
                "host": host,
                "port": port,
                "username": item.get("username") or "",
                "password": item.get("password") or "",
                "remark": item.get("remark") or "",
                "assigned_to": item.get("assigned_to") or "",
                "status": item.get("status") or "",
                "expires_at": int(item.get("expires_at") or 0),
                "expires_at_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(item.get("expires_at") or 0))) if item.get("expires_at") else "",
                "uri": uri,
                "line": f"{host}:{port}:{item.get('username') or ''}:{item.get('password') or ''}",
            }
            self.send_json({"ok": True, "data": data})
            return
        match = re.match(r"^/api/upstreams/(\d+)$", path)
        if match and self.command == "PUT":
            upstream_id = int(match.group(1))
            payload = self.read_json()
            try:
                quota_gb = float(payload.get("quota_gb") or 0)
            except (TypeError, ValueError):
                quota_gb = 0
            expires_at = parse_upstream_expires_at(payload.get("expires_at"))
            with connect_manager_db() as con:
                row = con.execute("SELECT id, status, last_error FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
                if not row:
                    self.send_json({"ok": False, "message": "SOCKS5 不存在"}, 404)
                    return
                status = row["status"]
                last_error = row["last_error"]
                if expires_at and expires_at <= now():
                    status = "不可用"
                    last_error = "SOCKS5: 已到期"
                elif row["last_error"] == "SOCKS5: 已到期":
                    status = "未检测"
                    last_error = ""
                con.execute(
                    """
                    UPDATE upstreams
                    SET remark = ?, assigned_to = ?, quota_gb = ?, expires_at = ?,
                        status = ?, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.get("remark") or "",
                        payload.get("assigned_to") or "",
                        quota_gb,
                        expires_at,
                        status,
                        last_error,
                        now(),
                        upstream_id,
                    ),
                )
                bound = con.execute("SELECT id FROM packages WHERE upstream_id = ? LIMIT 1", (upstream_id,)).fetchone()
            if bound:
                refresh_routes_best_effort("保存 SOCKS5 后刷新")
            self.send_json({"ok": True, "message": "已保存 SOCKS5"})
            return
        match = re.match(r"^/api/upstreams/(\d+)/check$", path)
        if match and self.command == "POST":
            upstream_id = int(match.group(1))
            expired = False
            with connect_manager_db() as con:
                row = con.execute("SELECT * FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
                if not row:
                    self.send_json({"ok": False, "message": "SOCKS5 不存在"}, 404)
                    return
                item = dict(row)
                if upstream_is_expired(item):
                    con.execute(
                        "UPDATE upstreams SET status = '不可用', last_error = 'SOCKS5: 已到期', last_check_at = ?, updated_at = ? WHERE id = ?",
                        (now(), now(), upstream_id),
                    )
                    expired = True
                try:
                    if expired:
                        raise RuntimeError("SOCKS5: 已到期")
                    protocol, error = check_upstream(item)
                    con.execute(
                        "UPDATE upstreams SET protocol = ?, status = '可用', last_error = '', last_check_at = ?, updated_at = ? WHERE id = ?",
                        (protocol, now(), now(), upstream_id),
                    )
                    self.send_json({"ok": True, "message": f"检测可用，协议：{protocol}"})
                except Exception as exc:
                    if not expired:
                        con.execute(
                            "UPDATE upstreams SET status = '不可用', last_error = ?, last_check_at = ?, updated_at = ? WHERE id = ?",
                            (str(exc), now(), now(), upstream_id),
                        )
                    msg = "SOCKS5 已到期" if expired else (str(exc) or type(exc).__name__)
                    self.send_json({"ok": False, "message": f"检测失败：{msg}"}, 200)
            if expired:
                refresh_routes_best_effort("SOCKS5 到期检测")
            return
        match = re.match(r"^/api/upstreams/(\d+)/speed-test$", path)
        if match and self.command == "POST":
            upstream_id = int(match.group(1))
            try:
                latency, speed = speed_test_upstream(upstream_id)
                self.send_json(
                    {
                        "ok": True,
                        "message": f"测速完成：{latency} ms / {format_speed(speed)}",
                        "data": {"latency_ms": latency, "speed_bps": speed},
                    }
                )
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
            except Exception as exc:
                self.send_json({"ok": False, "message": f"测速失败：{exc}"}, 200)
            return
        match = re.match(r"^/api/upstreams/(\d+)$", path)
        if match and self.command == "DELETE":
            upstream_id = int(match.group(1))
            with connect_manager_db() as con:
                con.execute("DELETE FROM upstreams WHERE id = ?", (upstream_id,))
                con.execute("UPDATE packages SET upstream_id = NULL WHERE upstream_id = ?", (upstream_id,))
            try:
                generate_subscriptions()
            except OSError as exc:
                log_event("警告", f"删除 SOCKS5 后刷新订阅失败：{exc}")
            refresh_routes_best_effort("删除 SOCKS5 后刷新")
            self.send_json({"ok": True, "message": "已删除 SOCKS5"})
            return

        if path == "/api/packages":
            if self.command == "GET":
                self.send_json({"ok": True, "data": dashboard_data()["packages"]})
                return
            if self.command == "POST":
                try:
                    package_id, message = create_package(self.read_json())
                except ValueError as exc:
                    self.send_json({"ok": False, "message": str(exc)}, 400)
                    return
                except sqlite3.IntegrityError:
                    self.send_json({"ok": False, "message": "订阅名已存在，请换一个"}, 400)
                    return
                self.send_json({"ok": True, "id": package_id, "message": message})
                return
        match = re.match(r"^/api/packages/(\d+)$", path)
        if match and self.command == "DELETE":
            package_id = int(match.group(1))
            try:
                msg = delete_package(package_id)
            except ValueError as exc:
                self.send_json({"ok": False, "message": str(exc)}, 404)
                return
            except Exception as exc:
                log_event("警告", f"删除套餐失败：{exc}")
                self.send_json({"ok": False, "message": f"删除失败：{exc}"}, 500)
                return
            self.send_json({"ok": True, "message": msg})
            return
        if match and self.command == "PUT":
            package_id = int(match.group(1))
            payload = self.read_json()
            upstream_ids = package_upstream_ids(payload)
            if not upstream_ids and payload.get("upstream_id"):
                upstream_ids = package_upstream_ids({"upstream_id": payload.get("upstream_id")})
            if "upstream_ids" in payload and not upstream_ids:
                self.send_json({"ok": False, "message": "请选择至少一个 SOCKS5 节点"}, 400)
                return
            with connect_manager_db() as con:
                con.execute(
                    """
                    UPDATE packages
                    SET name = ?, total_gb = ?, residential_gb = ?, notes = ?, upstream_id = ?, expires_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.get("name") or "",
                        float(payload.get("total_gb") or DEFAULT_PACKAGE_TOTAL_GB),
                        float(payload.get("residential_gb") or 0),
                        payload.get("notes") or "",
                        int(payload["upstream_id"]) if payload.get("upstream_id") else None,
                        parse_expires_at(payload.get("expires_at")),
                        now(),
                        package_id,
                    ),
                )
                row = con.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
            if not row:
                self.send_json({"ok": False, "message": "套餐不存在"}, 404)
                return
            if upstream_ids:
                try:
                    sync_package_bindings(package_id, upstream_ids)
                except ValueError as exc:
                    self.send_json({"ok": False, "message": str(exc)}, 400)
                    return
                with connect_manager_db() as con:
                    row = con.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
            changed_limit = False
            for item in package_runtime_entries(row):
                changed_limit = sync_client_limit(item["port"], item["email"], bytes_from_gb(row["total_gb"])) or changed_limit
            if changed_limit:
                restart_xray()
            generate_subscriptions()
            refresh_routes_best_effort("保存套餐后刷新")
            self.send_json({"ok": True, "message": "已保存"})
            return
        match = re.match(r"^/api/packages/(\d+)/residential$", path)
        if match and self.command == "POST":
            msg = ensure_residential_node(int(match.group(1)))
            self.send_json({"ok": True, "message": msg})
            return
        match = re.match(r"^/api/packages/(\d+)/sync$", path)
        if match and self.command == "POST":
            enforce_quotas()
            generate_subscriptions()
            refresh_routes_best_effort("套餐手动同步")
            self.send_json({"ok": True, "message": "已巡检并刷新"})
            return
        self.send_json({"ok": False, "message": "接口不存在"}, 404)

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        safe = unquote(path).lstrip("/")
        if ".." in safe or safe.startswith("/"):
            self.send_error(404)
            return
        target = FRONTEND_DIR / safe
        if not target.is_file():
            target = FRONTEND_DIR / "index.html"
        content_type = "text/plain; charset=utf-8"
        if target.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=32180)
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--regenerate", action="store_true")
    args = parser.parse_args()

    init_db()
    load_credentials()
    if args.init:
        imported = import_existing_packages()
        generate_subscriptions()
        print(json.dumps({"ok": True, "imported": imported}, ensure_ascii=False))
        return
    if args.enforce:
        changed = enforce_quotas()
        print(json.dumps({"ok": True, "changed": changed}, ensure_ascii=False))
        return
    if args.regenerate:
        generate_subscriptions()
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"proxy3x-manager listening on {args.host}:{args.port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
