# Prompt: Eshaa Official Shopify app connect karna

Neeche line ke baad wala poora text copy karke doosre Claude session / agent ko de dein.
Us session ke environment mein `SHOPIFY_CLIENT_ID` aur `SHOPIFY_CLIENT_SECRET` hone chahiye.

---

Is session ko mere Shopify store **Eshaa Official** (`eshaa-official.myshopify.com`) se connect karo.

**Credentials:** environment variables `SHOPIFY_CLIENT_ID` aur `SHOPIFY_CLIENT_SECRET` mein hain.
Inki values ya access token kabhi print, log ya commit mat karna. Pehle sirf check karo ke dono set
hain (`[ -n "$SHOPIFY_CLIENT_SECRET" ] && echo set`). Agar set nahi hain to mujhe batao ke environment
settings mein add karne hain. Chat mein value mat maangna.

**Steps:**
1. Agar GitHub repo `marjanash/eshaluxe` (branch `claude/brave-wozniak-h55f0o`) is session mein hai,
   to `scripts/shopify.py` aur `CLAUDE.md` wahan se le lo. Warna neeche diya gaya script
   `scripts/shopify.py` mein save karo.
2. `python3 scripts/shopify.py --check` chalao. Jawab `Connected: Eshaa Official ...` aana chahiye.
3. Access token takreeban 24 ghante chalta hai. Script use cache karta hai, expire hone se 10 minute
   pehle ya 401 aane par **khud naya token le leta hai**. Mujhe kabhi mat kehna ke token expire ho
   gaya ya reconnect karo. Har Admin API call isi script se karo aur masla khud handle karo.
4. Read-only queries kabhi bhi chala sakte ho. Store mein koi bhi badlaav (products, prices, orders,
   discounts, themes, pages) karne se pehle mujh se poocho.
5. Live theme "minimog - Festive Sale v2" hai. Theme edit karna ho to pehle duplicate par karo.
6. Connect hone ke baad mujhe store ka naam, products aur orders ki ginti bata do.

Usage:
```bash
python3 scripts/shopify.py --check
python3 scripts/shopify.py '{ products(first: 5) { nodes { id title } } }'
python3 scripts/shopify.py 'query($n:Int!){ orders(first:$n){ nodes { name } } }' '{"n":5}'
```

`scripts/shopify.py`:
```python
#!/usr/bin/env python3
"""Shopify Admin API helper with automatic token refresh.

Uses the client-credentials grant, so no manual reconnect is ever needed:
the access token is cached and silently renewed before it expires
(tokens last ~24h) or whenever Shopify answers 401.

Environment:
  SHOPIFY_CLIENT_ID      app client ID (required)
  SHOPIFY_CLIENT_SECRET  app client secret (required)
  SHOPIFY_STORE          store domain (default: eshaa-official.myshopify.com)
  SHOPIFY_API_VERSION    Admin API version (default: 2025-10)
  SHOPIFY_TOKEN_CACHE    token cache file (default: ~/.cache/shopify_token.json)

CLI usage:
  python3 scripts/shopify.py '{ shop { name } }'
  python3 scripts/shopify.py 'query($n:Int!){ products(first:$n){ nodes { title } } }' '{"n":5}'
  python3 scripts/shopify.py --check      # verify connection

Library usage:
  from shopify import graphql
  data = graphql("{ shop { name } }")
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

STORE = os.environ.get("SHOPIFY_STORE", "eshaa-official.myshopify.com")
API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2025-10")
CACHE = os.path.expanduser(
    os.environ.get("SHOPIFY_TOKEN_CACHE", "~/.cache/shopify_token.json")
)
REFRESH_MARGIN = 10 * 60  # renew 10 minutes before expiry


def _credentials():
    cid = os.environ.get("SHOPIFY_CLIENT_ID")
    secret = os.environ.get("SHOPIFY_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET not set in environment")
    return cid, secret


def _fetch_token():
    cid, secret = _credentials()
    body = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": cid, "client_secret": secret}
    ).encode()
    req = urllib.request.Request(
        f"https://{STORE}/admin/oauth/access_token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    d["expires_at"] = time.time() + int(d.get("expires_in", 86399))
    d["store"] = STORE
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    fd = os.open(CACHE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f)
    return d["access_token"]


def get_token(force=False):
    if not force:
        try:
            with open(CACHE) as f:
                d = json.load(f)
            if d.get("store") == STORE and d["expires_at"] - REFRESH_MARGIN > time.time():
                return d["access_token"]
        except (OSError, ValueError, KeyError):
            pass
    return _fetch_token()


def graphql(query, variables=None, _retry=True):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"https://{STORE}/admin/api/{API_VERSION}/graphql.json",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": get_token(force=not _retry),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry:  # token expired/revoked -> renew once
            return graphql(query, variables, _retry=False)
        if e.code == 429 and _retry:  # throttled -> wait and retry once
            time.sleep(2)
            return graphql(query, variables, _retry=False)
        raise SystemExit(f"Shopify API error {e.code}: {e.read().decode()[:500]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--check":
        res = graphql("{ shop { name myshopifyDomain } productsCount { count } }")
        shop = res["data"]["shop"]
        print(f"Connected: {shop['name']} ({shop['myshopifyDomain']}), "
              f"{res['data']['productsCount']['count']} products")
    else:
        variables = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
        print(json.dumps(graphql(sys.argv[1], variables), indent=2, ensure_ascii=False))
```
