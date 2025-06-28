from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class FalabellaCron(models.Model):
    _name = 'falabella.cron'
    _description = 'Falabella Synchronization Cron'

    def run_price_name_sync(self):
        products = self.env['product.template'].search([('write_date','>', (fields.Datetime.now() - relativedelta(minutes=5)))])
        for product in products:
            product.sync_to_falabella()

    @api.model
    def sync_all_products(self):
        products = self.env['product.template'].search([])
        for product in products:
            product.sync_to_falabella()