from odoo import models, fields, api
import requests
import time
import hashlib
import hmac

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fb_last_sync = fields.Datetime('Última sincronización Falabella')

    @api.model
    def _falabella_signature(self, params):
        secret = self.env['ir.config_parameter'].sudo().get_param('falabella.token')
        payload = ''.join(f"{k}{params[k]}" for k in sorted(params))
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def sync_to_falabella(self):
        base = self.env['ir.config_parameter'].sudo()
        user = base.get_param('falabella.user')
        token = base.get_param('falabella.token')
        url = "https://sellercenter-api.falabella.com/"
        for prod in self:
            params = {
                'Action': 'UpdateProducts',
                'UserID': user,
                'SKU': prod.default_code or str(prod.id),
                'Name': prod.name,
                'Price': str(prod.list_price),
                'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%S"),
                'Format': 'JSON',
                'Version': '1.0'
            }
            params['Signature'] = self._falabella_signature(params)
            resp = requests.post(url, params=params)
            if resp.ok:
                prod.fb_last_sync = fields.Datetime.now()