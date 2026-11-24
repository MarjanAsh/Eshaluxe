# Eshaluxe — Shopify store: Eshaa Official

- Store: `eshaa-official.myshopify.com` (primary domain eshaaofficial.com, currency PKR)
- Credentials come from environment variables `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`.
  Never print, log, or commit their values or the access token.

## Talking to the store

Always use `scripts/shopify.py` for Admin API calls:

```bash
python3 scripts/shopify.py --check
python3 scripts/shopify.py '{ products(first: 5) { nodes { id title } } }'
python3 scripts/shopify.py --scopes                    # granted scopes
python3 scripts/shopify.py -f query.graphql '{"n":5}'  # query from file + variables
python3 scripts/shopify.py --rest GET orders/count.json
python3 scripts/shopify.py --write 'mutation { ... }'  # only after owner approval
```

Mutations and non-GET REST calls are refused unless `--write` is passed.
In Python: `sys.path.insert(0, "scripts"); from shopify import graphql, rest`.

Scopes the app does NOT have (24 Nov 2026): read_inventory, read_locations,
read_customers (admin), read_fulfillments, read_all_orders (orders older than
60 days are hidden). Add them in the Dev Dashboard if needed.

The script gets an access token via the client-credentials grant, caches it in
`~/.cache/shopify_token.json` (mode 600), renews it 10 minutes before expiry
and retries once on 401. Token expiry is never a reason to stop or to ask the
user to reconnect — just call the script again.

## Rules

- Read freely; ask the owner before any write (products, prices, discounts,
  orders, theme changes, publishing a theme).
- The live theme is "minimog - Festive Sale v2"; test theme edits on a
  duplicate, not on the live theme.
