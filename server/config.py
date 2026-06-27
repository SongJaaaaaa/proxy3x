import os
from pathlib import Path


APP_DIR = Path(os.environ.get("PROXY3X_APP_DIR", Path(__file__).resolve().parent))
DATA_DIR = APP_DIR / "data"
DEFAULT_CHAIN_DIR = DATA_DIR / "chain" if os.name == "nt" else Path("/opt/3x-ui-chain")
CHAIN_DIR = Path(os.environ.get("PROXY3X_CHAIN_DIR", str(DEFAULT_CHAIN_DIR)))
DB_PATH = DATA_DIR / "manager.db"
FRONTEND_DIR = APP_DIR / "frontend"
RULES_PATH = APP_DIR / "rules.yaml"
CREDENTIALS_PATH = APP_DIR / "manager-credentials.json"
INITIAL_CREDENTIALS_PATH = APP_DIR / "manager-credentials.txt"
CHAIN_DB = CHAIN_DIR / "db" / "x-ui.db"
DEPLOYMENT_PATH = CHAIN_DIR / "chain-deployment.json"
SUBSCRIPTIONS_DIR = CHAIN_DIR / "subscriptions"
SOCKS_FACTORY_DIR = CHAIN_DIR / "socks-factory"
SING_BOX_CONFIG_PATH = SOCKS_FACTORY_DIR / "sing-box.json"
PANEL_BASE_URL = os.environ.get("PROXY3X_PANEL_URL", "http://127.0.0.1:32080")
XUI_CONTAINER = os.environ.get("PROXY3X_XUI_CONTAINER", "3x-ui-chain")
DEFAULT_SERVER = os.environ.get("PROXY3X_SERVER", "vpn.sjiaa.cc.cd")
ALT_SUBSCRIPTION_DOMAIN = os.environ.get("PROXY3X_ALT_SUBSCRIPTION_DOMAIN", "vpn-us.songjiaaa.ccwu.cc")
SHADOWROCKET_NODE_SERVER = os.environ.get("PROXY3X_SHADOWROCKET_NODE_SERVER", DEFAULT_SERVER)
REALITY_SNI = os.environ.get("PROXY3X_REALITY_SNI", "www.amazon.com")
SOCKS_PORT_START = int(os.environ.get("PROXY3X_SOCKS_PORT_START", "33001"))
SOCKS_PORT_END = int(os.environ.get("PROXY3X_SOCKS_PORT_END", "33999"))
SING_BOX_API_LISTEN = os.environ.get("PROXY3X_SING_BOX_API_LISTEN", "127.0.0.1:33000")
SING_BOX_SERVICE = os.environ.get("PROXY3X_SING_BOX_SERVICE", "proxy3x-socks-factory")
STATSQUERY_BIN = os.environ.get("PROXY3X_STATSQUERY_BIN", "xray")
ENABLE_SING_BOX_STATS = os.environ.get("PROXY3X_ENABLE_SING_BOX_STATS", "").lower() in ("1", "true", "yes", "on")
OUTBOUND_TEST_URL = "https://www.google.com/generate_204"
GB = 1024 * 1024 * 1024
SESSION_MAX_AGE = 86400
DEFAULT_PACKAGE_EXPIRE_SECONDS = 30 * 86400
DEFAULT_UPSTREAM_EXPIRE_SECONDS = 30 * 86400
DEFAULT_PACKAGE_TOTAL_GB = 500
DEFAULT_NODE_NAME = "🇺🇸 住宅家宽"
LEGACY_NODE_NAMES = {"高速节点", "高速流量"}
LEGACY_SINGLE_NODE_NAMES = LEGACY_NODE_NAMES | {"🇺🇸 娱乐流量"}
BLOCK_OUTBOUND_TAG = "proxy3x-block"
PACKAGE_TYPE_CHAIN = "chain"
PACKAGE_TYPE_MIXED = "mixed"
DIRECT_OUTBOUND_TAG = "direct"
ENTERTAINMENT_NODE_NAME = "🇺🇸 娱乐流量"
RESIDENTIAL_NODE_NAME = "🇺🇸 住宅流量"
SUPPORTED_SOURCE_PROTOCOLS = {"vless", "vmess", "trojan", "ss", "shadowsocks", "socks", "socks5", "http"}
