from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from datetime import date

FORMAT_CHOICES = (
    ('json', 'JSON'),
    ('xml', 'XML'),
)

class SaleForm(forms.Form):
    order_id = forms.CharField(label='ID заказа', max_length=50)
    customer_name = forms.CharField(label='Имя клиента', max_length=100)
    product = forms.CharField(label='Товар', max_length=100)
    quantity = forms.IntegerField(label='Количество', validators=[MinValueValidator(1)])
    price = forms.DecimalField(label='Цена за единицу', max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    date = forms.DateField(label='Дата покупки', widget=forms.DateInput(attrs={'type': 'date'}))
    export_format = forms.ChoiceField(label='Формат сохранения', choices=FORMAT_CHOICES)

    def clean_date(self):
        d = self.cleaned_data['date']
        if d > date.today():
            raise ValidationError('Дата покупки не может быть в будущем')
        return d

class UploadForm(forms.Form):
    file = forms.FileField(label='Файл (JSON или XML)')

    def clean_file(self):
        f = self.cleaned_data['file']
        allowed = ['application/json', 'text/json', 'application/xml', 'text/xml']
        if hasattr(f, 'content_type') and f.content_type not in allowed:
            raise ValidationError('Недопустимый тип файла. Разрешены JSON или XML.')
        if not (f.name.lower().endswith('.json') or f.name.lower().endswith('.xml')):
            raise ValidationError('Расширение файла должно быть .json или .xml')
        return f
