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
from http import cookies
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


APP_DIR = Path(os.environ.get("PROXY3X_APP_DIR", Path(__file__).resolve().parent))
CHAIN_DIR = Path(os.environ.get("PROXY3X_CHAIN_DIR", "/opt/3x-ui-chain"))
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "manager.db"
FRONTEND_DIR = APP_DIR / "frontend"
RULES_PATH = APP_DIR / "rules.yaml"
CREDENTIALS_PATH = APP_DIR / "manager-credentials.json"
INITIAL_CREDENTIALS_PATH = APP_DIR / "manager-credentials.txt"
CHAIN_DB = CHAIN_DIR / "db" / "x-ui.db"
DEPLOYMENT_PATH = CHAIN_DIR / "chain-deployment.json"
SUBSCRIPTIONS_DIR = CHAIN_DIR / "subscriptions"
PANEL_BASE_URL = os.environ.get("PROXY3X_PANEL_URL", "http://127.0.0.1:32080")
XUI_CONTAINER = os.environ.get("PROXY3X_XUI_CONTAINER", "3x-ui-chain")
DEFAULT_SERVER = os.environ.get("PROXY3X_SERVER", "vpn.sjiaa.cc.cd")
ALT_SUBSCRIPTION_DOMAIN = os.environ.get("PROXY3X_ALT_SUBSCRIPTION_DOMAIN", "vpn-us.songjiaaa.ccwu.cc")
SHADOWROCKET_NODE_SERVER = os.environ.get("PROXY3X_SHADOWROCKET_NODE_SERVER", "154.44.9.60")
REALITY_SNI = os.environ.get("PROXY3X_REALITY_SNI", "www.amazon.com")
OUTBOUND_TEST_URL = "https://www.google.com/generate_204"
GB = 1024 * 1024 * 1024
SESSION_MAX_AGE = 86400
DEFAULT_PACKAGE_EXPIRE_SECONDS = 30 * 86400
DEFAULT_PACKAGE_TOTAL_GB = 500
DEFAULT_NODE_NAME = "🇺🇸 住宅家宽"
LEGACY_NODE_NAMES = {"高速节点", "高速流量"}
LEGACY_SINGLE_NODE_NAMES = LEGACY_NODE_NAMES | {"🇺🇸 娱乐流量"}
BLOCK_OUTBOUND_TAG = "proxy3x-block"


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


def default_expires_at(base=None):
    return int(base or now()) + DEFAULT_PACKAGE_EXPIRE_SECONDS


def parse_expires_at(value, base=None):
    try:
        ts = int(float(value or 0))
    except (TypeError, ValueError):
        ts = 0
    if ts > 100000000000:
        ts = ts // 1000
    return ts if ts > 0 else default_expires_at(base)


def package_is_expired(package, at=None):
    expires_at = int(package["expires_at"] or 0)
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


def connect_manager_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


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
            """
        )
        columns = {row["name"] for row in con.execute("PRAGMA table_info(packages)").fetchall()}
        if "expires_at" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN expires_at INTEGER NOT NULL DEFAULT 0")
        if "disabled_reason" not in columns:
            con.execute("ALTER TABLE packages ADD COLUMN disabled_reason TEXT NOT NULL DEFAULT ''")
        con.execute(
            """
            UPDATE packages
            SET expires_at = created_at + ?
            WHERE expires_at IS NULL OR expires_at = 0
            """,
            (DEFAULT_PACKAGE_EXPIRE_SECONDS,),
        )
        # SOCKS5 额度字段：用于上游用量进度条的分母（GB）。0 = 未设额度，前端不画进度条。
        upstream_columns = {row["name"] for row in con.execute("PRAGMA table_info(upstreams)").fetchall()}
        if "quota_gb" not in upstream_columns:
            con.execute("ALTER TABLE upstreams ADD COLUMN quota_gb REAL NOT NULL DEFAULT 0")


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
    return f"vless://{entry['uuid']}@{SHADOWROCKET_NODE_SERVER}:{entry['port']}?{query}#{quote(node_name)}"


def clash_node(entry, node_name):
    return f"""  - name: \"{node_name}\"
    type: vless
    server: \"{server_host()}\"
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
    entries = []
    for key in ("direct_entry_json", "residential_entry_json"):
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
    with connect_manager_db() as con:
        packages = con.execute("SELECT * FROM packages ORDER BY id").fetchall()
        upstreams = con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()

    manager_packages = []
    for p in packages:
        sources = []
        if p["direct_email"] and p["direct_port"]:
            sources.append({"email": p["direct_email"], "port": int(p["direct_port"])})
        if p["residential_email"] and p["residential_port"]:
            sources.append({"email": p["residential_email"], "port": int(p["residential_port"])})
        manager_packages.append(
            {
                "sub_id": p["sub_id"],
                "name": p["name"],
                "total_gb": p["total_gb"],
                "residential_gb": p["residential_gb"],
                "expire": int(p["expires_at"] or 0),
                "usage_sources": sources,
            }
        )

    data["manager_packages"] = manager_packages
    data["proxy3x_manager"] = {
        "updated_at": now(),
        "panel": "https://proxy3x.sjiaa.cc.cd/",
        "packages": [
            {
                "sub_id": p["sub_id"],
                "name": p["name"],
                "direct_port": p["direct_port"],
                "residential_port": p["residential_port"],
                "upstream_id": p["upstream_id"],
            }
            for p in packages
        ],
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
    item["password"] = mask_secret(item.get("password"))
    item["username"] = mask_secret(item.get("username"))
    quota_gb = float(item.get("quota_gb") or 0)
    item["quota_gb"] = quota_gb
    item["quota_bytes"] = bytes_from_gb(quota_gb)
    return item


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
            raise RuntimeError("SOCKS5 握手失败")
        if method[1] == 2:
            sock.sendall(bytes([1, len(user)]) + user + bytes([len(pwd)]) + pwd)
            auth = sock.recv(2)
            if len(auth) != 2 or auth[1] != 0:
                raise RuntimeError("SOCKS5 账号验证失败")
        elif method[1] != 0:
            raise RuntimeError("SOCKS5 不支持的认证方式")
        sock.sendall(bytes([5, 1, 0, 3, len(host)]) + host + (443).to_bytes(2, "big"))
        reply = sock.recv(10)
        if len(reply) < 2 or reply[1] != 0:
            raise RuntimeError("SOCKS5 连接目标失败")


def check_upstream(upstream):
    try:
        test_socks_proxy(upstream)
        return "socks", ""
    except Exception as exc:
        raise RuntimeError(f"SOCKS5: {type(exc).__name__}") from exc


def xray_outbound_for_upstream(row):
    users = []
    if row["username"] or row["password"]:
        users = [{"user": row["username"], "pass": row["password"]}]
    return {
        "tag": f"proxy3x-upstream-{row['id']}",
        "protocol": "socks",
        "settings": {
            "servers": [
                {
                    "address": row["host"],
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
            SELECT p.*, u.protocol, u.host, u.port AS upstream_port, u.username, u.password
            FROM packages p
            LEFT JOIN upstreams u ON u.id = p.upstream_id
            ORDER BY p.id
            """
        ).fetchall()
        upstreams = con.execute("SELECT * FROM upstreams ORDER BY id").fetchall()

    package_ports = set()
    managed_ports = set()
    for p in packages:
        for port in (p["direct_port"], p["residential_port"]):
            if port:
                package_ports.add(int(port))
        if not p["upstream_id"]:
            continue
        if p["direct_port"]:
            managed_ports.add(int(p["direct_port"]))
        if p["residential_port"]:
            managed_ports.add(int(p["residential_port"]))
    tag_by_port = inbound_tag_map()
    package_tags = {tag_by_port.get(port, f"inbound-{port}") for port in package_ports}
    used_upstream_ids = {
        int(p["upstream_id"])
        for p in packages
        if p["upstream_id"] and (p["direct_port"] or p["residential_port"])
    }
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
        if int(row["id"]) in used_upstream_ids:
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
    for p in packages:
        ports = [port for port in (p["direct_port"], p["residential_port"]) if port]
        if not ports:
            continue
        if not p["upstream_id"]:
            new_rules.append(
                {
                    "type": "field",
                    "inboundTag": [tag_by_port.get(int(port), f"inbound-{int(port)}") for port in ports],
                    "outboundTag": BLOCK_OUTBOUND_TAG,
                }
            )
            continue
        new_rules.append(
            {
                "type": "field",
                "inboundTag": [tag_by_port.get(int(port), f"inbound-{int(port)}") for port in ports],
                "outboundTag": f"proxy3x-upstream-{int(p['upstream_id'])}",
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
        con.execute("DELETE FROM packages WHERE id = ?", (package_id,))
    ports = [package.get("direct_port"), package.get("residential_port")]
    emails = [package.get("direct_email"), package.get("residential_email")]
    disabled = disable_xui_inbounds(ports, emails)
    removed = delete_xui_inbounds(ports, emails)
    delete_subscription_files(package["sub_id"])
    generate_subscriptions()
    refresh_routes_best_effort(f"{package['name']} 删除后刷新")
    log_event("信息", f"已删除用户套餐 {package['name']}，禁用入站 {disabled} 个，清理入站 {removed} 个")
    return "已删除套餐，旧订阅节点已失效"


def finish_package_delete(package):
    removed_inbounds = delete_xui_inbounds(
        [package.get("direct_port"), package.get("residential_port")],
        [package.get("direct_email"), package.get("residential_email")],
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
    direct = traffic.get((package["direct_email"], int(package["direct_port"] or 0)), {})
    residential = traffic.get((package["residential_email"], int(package["residential_port"] or 0)), {})
    upload = int(direct.get("up") or 0) + int(residential.get("up") or 0)
    download = int(direct.get("down") or 0) + int(residential.get("down") or 0)
    direct_used = int(direct.get("up") or 0) + int(direct.get("down") or 0)
    residential_used = int(residential.get("up") or 0) + int(residential.get("down") or 0)
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
        "direct_runtime_enabled": bool(direct.get("inbound_enable", package["direct_enabled"])),
        "residential_runtime_enabled": bool(residential.get("inbound_enable", package["residential_enabled"])),
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
        set_inbound_enabled(p["direct_port"], p["direct_email"], False)
        set_inbound_enabled(p["residential_port"], p["residential_email"], False)
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


def enforce_quotas():
    init_db()
    changed = 0
    traffic = traffic_map()
    with connect_manager_db() as con:
        packages = con.execute("SELECT * FROM packages ORDER BY id").fetchall()
        changed += disable_expired_packages(con, packages)
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
            if total_limit and usage["total_used"] >= total_limit and p["enabled"]:
                set_inbound_enabled(p["direct_port"], p["direct_email"], False)
                set_inbound_enabled(p["residential_port"], p["residential_email"], False)
                con.execute(
                    "UPDATE packages SET enabled = 0, direct_enabled = 0, residential_enabled = 0, disabled_reason = '额度用完', updated_at = ? WHERE id = ?",
                    (now(), p["id"]),
                )
                log_event("警告", f"{p['name']} 总额度达到 {p['total_gb']}GB，已关闭全部节点")
                changed += 1
    if changed:
        generate_subscriptions()
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
            apply_xray_routes()
            generate_subscriptions()
            return "住宅节点已存在，已刷新路由和订阅"
        port = next_free_port()
        entry = make_inbound(
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
    apply_xray_routes()
    generate_subscriptions()
    log_event("信息", f"已为 {p['name']} 创建住宅节点端口 {port}")
    return "已创建住宅节点"


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
    upstream_id = payload.get("upstream_id") or None
    if not upstream_id:
        with connect_manager_db() as con:
            row = con.execute("SELECT id FROM upstreams WHERE protocol = 'socks' ORDER BY id LIMIT 1").fetchone()
            upstream_id = row["id"] if row else None
    if not upstream_id:
        raise ValueError("请先添加一个 SOCKS5 上游")
    notes = payload.get("notes") or ""
    expires_at = parse_expires_at(payload.get("expires_at"))
    with connect_manager_db() as con:
        if con.execute("SELECT id FROM packages WHERE sub_id = ?", (sub_id,)).fetchone():
            raise ValueError("订阅名已存在，请换一个")
    direct_port = next_free_port()
    direct_entry = make_inbound(
        {
            "sub_id": sub_id,
            "email": f"{sub_id}-node",
            "remark": f"{sub_id}-node",
            "node_name": DEFAULT_NODE_NAME,
            "port": direct_port,
            "total_bytes": bytes_from_gb(total_gb),
        }
    )
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
                int(upstream_id) if upstream_id else None,
                direct_entry["email"],
                direct_port,
                json_dumps(direct_entry),
                expires_at,
                now(),
                now(),
            ),
        )
        package_id = con.execute("SELECT id FROM packages WHERE sub_id = ?", (sub_id,)).fetchone()["id"]
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
        usage = package_usage(p, traffic)
        total_used += usage["total_used"]
        total_limit += bytes_from_gb(p["total_gb"])
        residential_used += usage["residential_used"]
        if p.get("upstream_id"):
            upstream_usage[int(p["upstream_id"])] = upstream_usage.get(int(p["upstream_id"]), 0) + usage["residential_used"]
        p.update(usage)
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
            self.send_json({"ok": True, "message": "订阅已刷新"})
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
                assigned_to = payload.get("assigned_to") or ""
                try:
                    quota_gb = float(payload.get("quota_gb") or 0)
                except (TypeError, ValueError):
                    quota_gb = 0
                with connect_manager_db() as con:
                    con.execute(
                        """
                        INSERT INTO upstreams(protocol, host, port, username, password, remark, assigned_to, quota_gb, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            with connect_manager_db() as con:
                row = con.execute("SELECT id FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
                if not row:
                    self.send_json({"ok": False, "message": "SOCKS5 不存在"}, 404)
                    return
                con.execute(
                    "UPDATE upstreams SET remark = ?, assigned_to = ?, quota_gb = ?, updated_at = ? WHERE id = ?",
                    (
                        payload.get("remark") or "",
                        payload.get("assigned_to") or "",
                        quota_gb,
                        now(),
                        upstream_id,
                    ),
                )
            self.send_json({"ok": True, "message": "已保存 SOCKS5"})
            return
        match = re.match(r"^/api/upstreams/(\d+)/check$", path)
        if match and self.command == "POST":
            upstream_id = int(match.group(1))
            with connect_manager_db() as con:
                row = con.execute("SELECT * FROM upstreams WHERE id = ?", (upstream_id,)).fetchone()
                if not row:
                    self.send_json({"ok": False, "message": "SOCKS5 不存在"}, 404)
                    return
                item = dict(row)
                try:
                    protocol, error = check_upstream(item)
                    con.execute(
                        "UPDATE upstreams SET protocol = ?, status = '可用', last_error = '', last_check_at = ?, updated_at = ? WHERE id = ?",
                        (protocol, now(), now(), upstream_id),
                    )
                    self.send_json({"ok": True, "message": f"检测可用，协议：{protocol}"})
                except Exception as exc:
                    con.execute(
                        "UPDATE upstreams SET status = '不可用', last_error = ?, last_check_at = ?, updated_at = ? WHERE id = ?",
                        (str(exc), now(), now(), upstream_id),
                    )
                    self.send_json({"ok": False, "message": f"检测失败：{type(exc).__name__}"}, 200)
            return
        match = re.match(r"^/api/upstreams/(\d+)$", path)
        if match and self.command == "DELETE":
            upstream_id = int(match.group(1))
            with connect_manager_db() as con:
                con.execute("DELETE FROM upstreams WHERE id = ?", (upstream_id,))
                con.execute("UPDATE packages SET upstream_id = NULL WHERE upstream_id = ?", (upstream_id,))
            generate_subscriptions()
            apply_xray_routes()
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
            changed_limit = False
            if row:
                changed_limit = sync_client_limit(row["direct_port"], row["direct_email"], bytes_from_gb(row["total_gb"])) or changed_limit
                changed_limit = sync_client_limit(row["residential_port"], row["residential_email"], bytes_from_gb(row["residential_gb"])) or changed_limit
            if changed_limit:
                restart_xray()
            generate_subscriptions()
            apply_xray_routes()
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
            apply_xray_routes()
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
