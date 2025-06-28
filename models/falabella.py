from odoo import models, fields, api
import requests
import time
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

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
        if not user or not token:
            _logger.error("Faltan credenciales de Falabella (usuario o token).")
            return False

        url = "https://sellercenter-api.falabella.com/"
        for prod in self:
            try:
                stock_qty = sum(prod.quant_ids.mapped('quantity'))

                params = {
                    'Action': 'UpdateProducts',
                    'UserID': user,
                    'SKU': prod.default_code or str(prod.id),
                    'Name': prod.name,
                    'Price': str(prod.list_price),
                    'Quantity': str(int(stock_qty)),
                    'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    'Format': 'JSON',
                    'Version': '1.0'
                }
                params['Signature'] = self._falabella_signature(params)
                if not params['Signature']:
                    _logger.error(f"No se pudo generar la firma para el producto {prod.name}")
                    continue

                resp = requests.post(url, json=params)
                if resp.ok:
                    prod.fb_last_sync = fields.Datetime.now()
                    _logger.info(f"Producto {prod.name} sincronizado con Falabella exitosamente.")
                else:
                    _logger.error(f"Error al sincronizar {prod.name}: {resp.status_code} - {resp.text}")
            except Exception as e:
                _logger.error(f"Excepción al sincronizar {prod.name}: {str(e)}")