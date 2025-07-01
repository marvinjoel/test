{
    'name': 'Falabella Integration',
    'version': '15.0.1.0.0',
    'depends': ['product', 'base', 'sale', 'stock'],
    'data': [
        # 'security/falabella_security_models.xml',
        # 'security/ir.model.access.csv',
        'data/falabella_data.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}