from django.db import models

class Sale(models.Model):
    order_id = models.CharField(max_length=50)
    customer_name = models.CharField(max_length=100)
    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order_id', 'customer_name', 'product', 'date'], name='uniq_sale')
        ]
        ordering = ['-date', 'order_id']

    @property
    def total(self):
        return round(float(self.price) * int(self.quantity), 2)

    def __str__(self):
        return f"{self.order_id} — {self.customer_name} — {self.product}"
