# Eshaluxe — Shopify store: Eshaa Official

- Store: `eshaa-official.myshopify.com` (primary domain eshaaofficial.com, currency PKR)
- Credentials come from environment variables `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`.
  Never print, log, or commit their values or the access token.

## Talking to the store

Always use `scripts/shopify.py` for Admin API calls:

```bash
python3 scripts/shopify.py --check
python3 scripts/shopify.py '{ products(first: 5) { nodes { id title } } }'
```

The script gets an access token via the client-credentials grant, caches it in
`~/.cache/shopify_token.json` (mode 600), renews it 10 minutes before expiry
and retries once on 401. Token expiry is never a reason to stop or to ask the
user to reconnect — just call the script again.

## Rules

- Read freely; ask the owner before any write (products, prices, discounts,
  orders, theme changes, publishing a theme).
- The live theme is "minimog - Festive Sale v2"; test theme edits on a
  duplicate, not on the live theme.
