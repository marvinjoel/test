from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class FalabellaCron(models.Model):
    _name = 'x_falabella.cron'
    _description = 'Falabella Synchronization Cron'

    @api.model
    def run_price_name_sync(self):
        products = self.env['product.template'].search([('write_date', '>', (fields.Datetime.now() - relativedelta(minutes=5)))])
        for product in products:
            product.sync_to_falabella()
