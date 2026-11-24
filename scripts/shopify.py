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
  python3 scripts/shopify.py --scopes     # list the app's granted access scopes
  python3 scripts/shopify.py -f query.graphql ['{"vars":1}']   # query from a file
  echo '{ shop { name } }' | python3 scripts/shopify.py -       # query from stdin
  python3 scripts/shopify.py --rest GET products/count.json     # REST Admin API
  python3 scripts/shopify.py --write 'mutation { ... }'         # writes need --write

Mutations and non-GET REST calls are refused unless --write is passed, so
nothing changes in the store by accident (owner approval comes first).

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


def rest(method, path, body=None, _retry=True):
    """Call the REST Admin API, e.g. rest("GET", "products/count.json")."""
    url = f"https://{STORE}/admin/api/{API_VERSION}/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method.upper(),
        headers={"Content-Type": "application/json",
                 "X-Shopify-Access-Token": get_token(force=not _retry)},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 429) and _retry:
            if e.code == 429:
                time.sleep(2)
            return rest(method, path, body, _retry=False)
        raise SystemExit(f"Shopify API error {e.code}: {e.read().decode()[:500]}")


def _is_mutation(query):
    q = query.lstrip()
    while q.startswith("#"):
        q = q.split("\n", 1)[1].lstrip() if "\n" in q else ""
    return q.startswith("mutation")


def _main(argv):
    write = "--write" in argv
    argv = [a for a in argv if a != "--write"]
    if not argv:
        sys.exit(__doc__)
    if argv[0] == "--check":
        res = graphql("{ shop { name myshopifyDomain } productsCount { count } }")
        shop = res["data"]["shop"]
        print(f"Connected: {shop['name']} ({shop['myshopifyDomain']}), "
              f"{res['data']['productsCount']['count']} products")
        return
    if argv[0] == "--scopes":
        res = graphql("{ currentAppInstallation { accessScopes { handle } } }")
        for s in res["data"]["currentAppInstallation"]["accessScopes"]:
            print(s["handle"])
        return
    if argv[0] == "--rest":
        if len(argv) < 3:
            sys.exit("usage: --rest METHOD path [json-body]")
        method, path = argv[1].upper(), argv[2]
        if method != "GET" and not write:
            sys.exit("Refusing REST write without --write (ask the owner first)")
        body = json.loads(argv[3]) if len(argv) > 3 else None
        print(json.dumps(rest(method, path, body), indent=2, ensure_ascii=False))
        return
    if argv[0] in ("-f", "--file"):
        with open(argv[1]) as f:
            query = f.read()
        rest_args = argv[2:]
    elif argv[0] == "-":
        query = sys.stdin.read()
        rest_args = argv[1:]
    else:
        query = argv[0]
        rest_args = argv[1:]
    if _is_mutation(query) and not write:
        sys.exit("Refusing mutation without --write (ask the owner first)")
    variables = json.loads(rest_args[0]) if rest_args else None
    print(json.dumps(graphql(query, variables), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main(sys.argv[1:])

