def _ensure_products(env):
    products = ['Consumables', 'Sundries', 'Excess', 'Betterment']
    for p in products:
        if not env['product.product'].search([('name', '=', p)], limit=1):
            env['product.product'].create({'name': p, 'type': 'service'})
