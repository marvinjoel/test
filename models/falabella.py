from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
import requests
import time
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fb_last_sync = fields.Datetime(string="Last Sync with Falabella", readonly=True)

    @api.model
    def _falabella_signature(self, params):
        _logger.info("Generating signature for params: %s", params)
        secret = self.env['ir.config_parameter'].sudo().get_param('falabella.token')
        if not secret:
            _logger.error("No token found for Falabella")
            return False
        try:
            payload = ''.join(f"{k}{params[k]}" for k in sorted(params))
            signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            _logger.info("Signature generated: %s", signature)
            return signature
        except Exception as e:
            _logger.error("Error generating signature: %s", str(e))
            return False

    def sync_to_falabella(self):
        _logger.info("Starting sync with Falabella for %s products", len(self))
        base = self.env['ir.config_parameter'].sudo()
        user = base.get_param('falabella.user')
        token = base.get_param('falabella.token')

        if not user or not token:
            _logger.error("Missing Falabella credentials - User: %s, Token: %s", user, token)
            return

        url = "https://sellercenter-api.falabella.com/"
        for prod in self:
            _logger.info("Syncing product: %s (ID: %s, SKU: %s)", prod.name, prod.id, prod.default_code or str(prod.id))
            try:
                stock_qty = prod.qty_available
                timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                params = {
                    'Action': 'UpdateProducts',
                    'UserID': user,
                    'SKU': prod.default_code or str(prod.id),
                    'Name': prod.name,
                    'Price': str(prod.list_price),
                    'Quantity': str(int(stock_qty)),
                    'Timestamp': timestamp,
                    'Format': 'JSON',
                    'Version': '1.0'
                }

                params['Signature'] = self._falabella_signature(params)

                if not params['Signature']:
                    _logger.error("Failed to generate signature for product %s", prod.name)
                    continue

                headers = {'Content-Type': 'application/x-www-form-urlencoded'}

                _logger.info("Sending request to Falabella for product %s", prod.name)
                resp = requests.post(url, data=params, headers=headers)

                _logger.debug("Falabella response - Code: %s, Body: %s", resp.status_code, resp.text)

                if resp.ok:
                    prod.write({'fb_last_sync': fields.Datetime.now()})
                    _logger.info("Product %s synced successfully with Falabella", prod.name)
                else:
                    _logger.error("Error syncing %s: Code %s, Response: %s", prod.name, resp.status_code, resp.text)
            except Exception as e:
                _logger.error("Exception syncing %s: %s", prod.name, str(e))
        _logger.info("Finished sync with Falabella for %s products", len(self))

    def action_sync_with_falabella(self):
        _logger.info("Manual sync triggered for product %s", self.name)
        self.sync_to_falabella()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }