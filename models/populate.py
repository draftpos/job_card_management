def _ensure_products(env):
    products = ['Consumables', 'Sundries', 'Excess', 'Betterment']
    for p in products:
        prod = env['product.product'].search([('name', '=ilike', p)], limit=1)
        if not prod:
            prod = env['product.product'].with_context(active_test=False).search([('name', '=ilike', p)], limit=1)
            if prod and not prod.active:
                prod.active = True
        if not prod:
            env['product.product'].create({'name': p, 'type': 'service'})
