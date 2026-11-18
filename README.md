# Eshaluxe: Eshaa Official Shopify app

This file tells any agent or platform (Claude, muse.ai or anything else that can make HTTPS requests)
how to connect to the **Eshaa Official** Shopify store **without a connector**, using the store's
own custom app credentials.

## 1. Store

| | |
|---|---|
| Store name | Eshaa Official |
| Admin domain | `eshaa-official.myshopify.com` |
| Public domain | `eshaaofficial.com` |
| Currency | PKR |
| Plan | Basic |
| Live theme | `minimog - Festive Sale v2` |
| Admin API version | `2025-10` (GraphQL) |

## 2. Credentials (secrets)

Store these as **secrets / environment variables** on the platform. Never put them in chat, code,
logs or commits.

| Variable | What it is |
|---|---|
| `SHOPIFY_CLIENT_ID` | The app's Client ID (Shopify Dev Dashboard → app → Settings) |
| `SHOPIFY_CLIENT_SECRET` | The app's Client secret (same page) |
| `SHOPIFY_STORE` | Optional, defaults to `eshaa-official.myshopify.com` |

The values are not in this repository. Copy them from the Shopify Dev Dashboard, or from the
environment settings of the Claude session where they are already saved.

## 3. How the connection works

The app is already installed on the store. Agents connect with the **client-credentials grant**:
no browser login, no OAuth redirect, no connector.

### Step A: get an access token

```
POST https://eshaa-official.myshopify.com/admin/oauth/access_token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=<SHOPIFY_CLIENT_ID>&client_secret=<SHOPIFY_CLIENT_SECRET>
```

```bash
curl -sS -X POST "https://eshaa-official.myshopify.com/admin/oauth/access_token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=$SHOPIFY_CLIENT_ID" \
  --data-urlencode "client_secret=$SHOPIFY_CLIENT_SECRET"
```

Response (HTTP 200):

```json
{ "access_token": "shpat_…", "scope": "read_analytics,write_products,…", "expires_in": 86399 }
```

### Step B: call the Admin GraphQL API

```
POST https://eshaa-official.myshopify.com/admin/api/2025-10/graphql.json
Content-Type: application/json
X-Shopify-Access-Token: <access_token>

{ "query": "{ shop { name } productsCount { count } }" }
```

```bash
curl -sS -X POST "https://eshaa-official.myshopify.com/admin/api/2025-10/graphql.json" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Access-Token: $TOKEN" \
  -d '{"query":"{ shop { name myshopifyDomain } productsCount { count } }"}'
```

A working connection answers with `"name": "Eshaa Official"`.

### Step C: keep the token alive (required)

- The token lasts **about 24 hours** (`expires_in` ≈ 86399 seconds).
- Save it along with `expires_at = now + expires_in`.
- **Request a new token 10 minutes before `expires_at`**, or whenever an API call returns **HTTP 401**,
  then retry the call. A new token is just Step A again, with the same client ID and secret.
- On **HTTP 429** or a GraphQL error with code `THROTTLED`, wait 2 seconds and retry.
- Token expiry is never a reason to stop or ask the owner to reconnect. Renew it and continue.

## 4. Permissions (scopes) the app has

| Area | Scopes |
|---|---|
| Products & catalog | `write_products`, `write_product_listings`, `write_product_feeds`, `write_publications`, `write_channels`, `write_discovery` |
| Orders | `write_orders` |
| Discounts | `write_discounts`, `write_price_rules` |
| Theme & content | `write_themes`, `write_theme_code`, `write_content`, `write_online_store_pages`, `write_online_store_navigation`, `write_files` |
| Metaobjects | `write_metaobjects`, `write_metaobject_definitions` |
| Marketing & tracking | `write_marketing_events`, `write_marketing_integrated_campaigns`, `write_pixels`, `read_customer_events` |
| Analytics | `read_analytics`, `write_reports` |
| Customer account / Storefront | `customer_write_customers`, `customer_read_orders`, `unauthenticated_write_customers`, `unauthenticated_read_product_listings`, `unauthenticated_read_product_tags` |

There is **no** Admin `read_customers` / `write_customers` scope, so Admin API customer lists are not
available. To get them, add the scope in the Dev Dashboard and release a new app version.

## 5. Ready-made helper (Python, no dependencies)

`scripts/shopify.py` does Steps A to C automatically. It caches the token in
`~/.cache/shopify_token.json` (mode 600) and renews it on its own.

```bash
python3 scripts/shopify.py --check
python3 scripts/shopify.py '{ products(first: 5) { nodes { id title } } }'
python3 scripts/shopify.py 'query($n:Int!){ orders(first:$n){ nodes { name } } }' '{"n":5}'
```

```python
from shopify import graphql          # with scripts/ on the import path
data = graphql("{ shop { name } }")
```

## 6. Rules for any agent using this app

1. Never print, log or commit the client secret or the access token.
2. Read-only queries are allowed any time.
3. **Ask the owner before any change** to products, prices, inventory, orders, discounts, pages,
   navigation, files or themes.
4. Do not edit or publish the live theme (`minimog - Festive Sale v2`) directly. Duplicate it,
   edit the copy, and publish only after the owner approves.
5. Each connection should first report the store name, product count and order count to the owner.

## 7. Prompt for a new agent (muse.ai, Claude or any other)

Paste this into the agent, after saving `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET` as its secrets:

> Connect to my Shopify store `eshaa-official.myshopify.com` without a connector, following the
> README in GitHub repo `marjanash/eshaluxe` (branch `claude/brave-wozniak-h55f0o`). Credentials are in
> the secrets `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`. Get an access token with the
> client-credentials grant (README section 3), use the Admin GraphQL API version 2025-10, and renew
> the token yourself before it expires or on any 401. Never ask me to reconnect. Never show the
> secret or the token. Ask me before changing anything in the store. Once connected, tell me the
> store name, product count and order count.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Token request returns 400 / `invalid_client` | Client ID or secret is wrong, or has extra spaces. Copy it again from the Dev Dashboard. |
| Token request returns 4xx `app not installed` | The app is not installed on this store. Install it from the Dev Dashboard. |
| API returns 401 | Token expired or revoked. Get a new one (Step A) and retry. |
| API returns 403 / `ACCESS_DENIED` | That scope is missing (see section 4). Add it in the Dev Dashboard and release a new app version. |
| API returns 429 / `THROTTLED` | Rate limit. Wait a moment and retry. |
| Network / proxy errors | The platform must allow outbound HTTPS to `eshaa-official.myshopify.com`. |
| Token request returns 502 `token refresh not allowed through egress proxy` (store homepage still loads) | The platform's sandbox blocks the token endpoint on purpose, so Step A cannot run there. Do not try to get around it. Use the platform's own credential / OAuth page and enter this app's client ID and secret there (if it asks for a redirect URL, add that URL under the app's allowed redirection URLs in the Shopify Dev Dashboard). Or ask the platform's admin to allow `/admin/oauth/access_token` for this store. |

## 9. Platforms with a locked-down network (e.g. muse.ai)

Some agent sandboxes do not let the agent request tokens itself. On those:

1. Save the app's client ID and secret in the platform's **secure credential / OAuth page**, not in chat.
2. The platform then gets and renews the token for the agent. Section 3 Step A is skipped,
   and Steps B and C (API calls, retry on 401) still apply.
3. If the platform asks for a **redirect URL**, add it to the app in the Shopify Dev Dashboard
   (app → Configuration → Allowed redirection URLs) and release a new app version.
4. The rules in section 6 still apply.
