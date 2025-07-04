from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import requests
import urllib.parse
from hmac import HMAC
from hashlib import sha256
import logging
import xml.etree.ElementTree as ET

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
            sorted_params = sorted((k, v) for k, v in params.items() if k != 'Signature')
            encoded_params = [f"{urllib.parse.quote(k, safe='')}"
                             f"={urllib.parse.quote(v, safe='')}" for k, v in sorted_params]
            concatenated = '&'.join(encoded_params)
            _logger.debug("Signature Payload (concatenated and URL-encoded): %s", concatenated)
            signature = HMAC(secret.encode('utf-8'), concatenated.encode('utf-8'), sha256).hexdigest()
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
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Missing Falabella credentials. Please check system parameters.',
                    'type': 'danger',
                    'sticky': True,
                }
            }

        url_base = "https://sellercenter-api.falabella.com/"
        seller_id_ua = 'SC4ACDC'
        python_version_ua = '3.9.2'
        integration_type_ua = 'PROPIA'
        country_code_ua = 'FAPE'

        headers = {
            'Content-Type': 'application/xml',
            'User-Agent': f'{seller_id_ua}/Python/{python_version_ua}/{integration_type_ua}/{country_code_ua}',
            'Accept': 'application/xml',
        }

        for prod in self[:5]:
            _logger.info("Syncing product: %s (ID: %s, SKU: %s)", prod.name, prod.id, prod.default_code or str(prod.id))
            try:
                product_variants = self.env['product.product'].search([('product_tmpl_id', '=', prod.id)], limit=1)
                if not product_variants:
                    _logger.error("No variants found for product %s", prod.name)
                    continue

                variant = product_variants[0]
                warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                if not warehouse:
                    warehouse = self.env['stock.warehouse'].search([], limit=1)
                    if not warehouse:
                        _logger.error(
                            "No warehouse found to calculate stock for product %s. Please ensure you have at least one warehouse configured in Odoo.",
                            prod.name)
                        continue

                stock_qty = variant.with_context(warehouse=warehouse.id).qty_available
                sku = variant.default_code or str(variant.id)

                timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                params = {
                    'Action': 'ProductUpdate',
                    'UserID': user,
                    'Timestamp': timestamp,
                    'Version': '1.0',
                    'Format': 'XML'
                }

                params['Signature'] = self._falabella_signature(params)

                request_root = ET.Element('Request')
                product_node = ET.SubElement(request_root, 'Product')
                ET.SubElement(product_node, 'SellerSku').text = sku
                ET.SubElement(product_node, 'Price').text = str(prod.list_price)
                business_units = ET.SubElement(product_node, 'BusinessUnits')
                business_unit = ET.SubElement(business_units, 'BusinessUnit')
                ET.SubElement(business_unit, 'OperatorCode').text = country_code_ua
                ET.SubElement(business_unit, 'Stock').text = str(int(stock_qty))

                xml_body = ET.tostring(request_root, encoding='UTF-8', xml_declaration=True).decode('utf-8')

                query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
                full_url = f"{url_base}?{query_string}"

                _logger.info("Sending request to Falabella for product %s. Full URL: %s", prod.name, full_url)
                _logger.debug("Request Headers: %s", headers)
                _logger.debug("Request XML Body: %s", xml_body)

                import time
                time.sleep(5)

                resp = requests.post(full_url, data=xml_body.encode('utf-8'), headers=headers)

                _logger.debug("Falabella response - Code: %s, Body: %s", resp.status_code, resp.text)

                if resp.ok:
                    prod.write({'fb_last_sync': fields.Datetime.now()})
                    _logger.info("Product %s synced successfully with Falabella", prod.name)
                else:
                    _logger.error("Error syncing %s: Code %s, Response: %s", prod.name, resp.status_code, resp.text)
            except Exception as e:
                _logger.error("Synchronization exception for %s: %s", prod.name, str(e))
                continue
        _logger.info("Finished sync with Falabella for %s products", len(self))

    def action_sync_with_falabella(self):
        _logger.info("Manual sync triggered for product %s", self.name)
        self.sync_to_falabella()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }