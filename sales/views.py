import json
import uuid
from pathlib import Path
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.conf import settings
from django.contrib import messages
from django.utils.html import escape
from .forms import SaleForm, UploadForm
from .models import Sale
import xml.etree.ElementTree as ET
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db import IntegrityError

# ПАПКИ ХРАНЕНИЯ ДАННЫХ (ТРЕБОВАНИЕ: хранить загруженные/сгенерированные файлы)
# media/data/json и media/data/xml создаются автоматически при первом обращении
DATA_DIR_JSON = Path(settings.MEDIA_ROOT) / 'data' / 'json'
DATA_DIR_XML = Path(settings.MEDIA_ROOT) / 'data' / 'xml'
DATA_DIR_JSON.mkdir(parents=True, exist_ok=True)
DATA_DIR_XML.mkdir(parents=True, exist_ok=True)


def index(request):
    return render(request, 'sales/index.html', {
        'sale_form': SaleForm(),
        'upload_form': UploadForm(),
    })


def export_sale(request):
    if request.method != 'POST':
        return redirect('sales:index')

    form = SaleForm(request.POST)
    if not form.is_valid():
        # Валидация формы: при ошибках возвращаем пользователя с сообщением
        messages.error(request, 'Исправьте ошибки формы')
        return render(request, 'sales/index.html', {'sale_form': form, 'upload_form': UploadForm()})

    data = form.cleaned_data.copy()
    storage = data.pop('storage')
    export_format = data.pop('export_format')

    # Приводим данные к единой структуре и добавляем вычисляемое поле total
    record = {
        'order_id': data['order_id'],
        'customer_name': data['customer_name'],
        'product': data['product'],
        'quantity': int(data['quantity']),
        'price': float(data['price']),
        'date': data['date'].isoformat(),
        'total': round(float(data['price']) * int(data['quantity']), 2),
    }

    # Генерация безопасного имени файла (не доверяем имени пользователя)
    if storage == 'db':
        try:
            obj, created = Sale.objects.get_or_create(
                order_id=record['order_id'],
                customer_name=record['customer_name'],
                product=record['product'],
                date=record['date'],
                defaults={
                    'quantity': record['quantity'],
                    'price': record['price'],
                }
            )
            if created:
                messages.success(request, 'Запись сохранена в БД')
            else:
                messages.info(request, 'Такая запись уже существует и не была добавлена (дубликат)')
        except IntegrityError:
            messages.info(request, 'Дубликат записи — не добавлено')
        return redirect('sales:index')

    # save to files
    filename = f"sale_{uuid.uuid4().hex}"

    if export_format == 'json':
        filepath = DATA_DIR_JSON / f"{filename}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        messages.success(request, f'Данные сохранены в {filepath.name}')
    else:
        filepath = DATA_DIR_XML / f"{filename}.xml"
        sale = ET.Element('sale')
        for k, v in record.items():
            child = ET.SubElement(sale, k)
            child.text = str(v)
        tree = ET.ElementTree(sale)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        messages.success(request, f'Данные сохранены в {filepath.name}')

    return redirect('sales:index')


def _is_valid_sale_dict(d: dict) -> bool:
    required = {'order_id', 'customer_name', 'product', 'quantity', 'price', 'date'}
    if not isinstance(d, dict) or not required.issubset(d.keys()):
        return False
    try:
        int(d['quantity'])
        float(d['price'])
        # Простая проверка формата даты ISO
        if 'T' in d['date']:
            d['date'] = d['date'].split('T')[0]
        parts = d['date'].split('-')
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            return False
    except Exception:
        return False
    return True


def upload_file(request):
    """
    Загрузка файла JSON/XML с сервера в папку media/data/... с валидацией.
    Соответствует требованиям:
    - Принимаем только JSON/XML (первичная проверка в форме UploadForm)
    - Генерируем собственное имя файла (UUID), не доверяем пользовательскому
    - Перед сохранением выполняем глубокую проверку структуры
    - При невалидности выводим сообщение и не сохраняем файл (или удаляем, если бы сохранили)
    """
    if request.method != 'POST':
        return redirect('sales:index')

    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, 'sales/index.html', {'sale_form': SaleForm(), 'upload_form': form})

    uploaded = request.FILES['file']
    content = uploaded.read()

    # Генерация нового безопасного имени файла
    new_name = f"upload_{uuid.uuid4().hex}"
    try:
        if uploaded.name.lower().endswith('.json'):
            # Парсинг JSON и структурная проверка
            data = json.loads(content.decode('utf-8'))
            if not _is_valid_sale_dict(data):
                raise ValueError('Некорректная структура JSON')
            dest = DATA_DIR_JSON / f"{new_name}.json"
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            # Парсинг XML и структурная проверка
            root = ET.fromstring(content)
            data = {child.tag: (child.text or '') for child in root}
            if not _is_valid_sale_dict(data):
                raise ValueError('Некорректная структура XML')
            # Нормализованный XML перед сохранением
            sale = ET.Element('sale')
            for k, v in data.items():
                child = ET.SubElement(sale, k)
                child.text = str(v)
            dest = DATA_DIR_XML / f"{new_name}.xml"
            ET.ElementTree(sale).write(dest, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        # При любой ошибке сообщаем пользователю и не сохраняем файл
        messages.error(request, f'Файл отклонен: {escape(str(e))}')
        # Удалять ничего не нужно: мы сохраняем файл только после успешной валидации
        return redirect('sales:index')

    messages.success(request, f'Файл сохранен как {dest.name}')
    return redirect('sales:index')


@require_http_methods(["GET"])
def db_list(request):
    return render(request, 'sales/db_list.html', {
        'sales': Sale.objects.all()
    })

@require_http_methods(["GET"]) 
def db_search(request):
    q = request.GET.get('q', '').strip()
    qs = Sale.objects.all()
    if q:
        # Поиск по текстовым полям
        from django.db.models import Q
        qs = qs.filter(Q(order_id__icontains=q) | Q(customer_name__icontains=q) | Q(product__icontains=q))
    data = [
        {
            'id': s.id,
            'order_id': s.order_id,
            'customer_name': s.customer_name,
            'product': s.product,
            'quantity': s.quantity,
            'price': float(s.price),
            'date': s.date.isoformat(),
            'total': s.total,
        } for s in qs[:100]
    ]
    return JsonResponse({'results': data})

@require_http_methods(["POST"]) 
def db_delete(request, pk: int):
    try:
        Sale.objects.get(pk=pk).delete()
        return JsonResponse({'ok': True})
    except Sale.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not_found'}, status=404)

@require_http_methods(["POST"]) 
def db_update(request, pk: int):
    # Обновление отдельных полей с валидацией
    try:
        s = Sale.objects.get(pk=pk)
    except Sale.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not_found'}, status=404)

    payload = json.loads(request.body.decode('utf-8') or '{}')
    errors = {}
    def add_err(field, msg):
        errors.setdefault(field, []).append(msg)

    from datetime import date
    if 'order_id' in payload:
        if not payload['order_id']:
            add_err('order_id', 'Обязательное поле')
        else:
            s.order_id = payload['order_id']
    if 'customer_name' in payload:
        if not payload['customer_name']:
            add_err('customer_name', 'Обязательное поле')
        else:
            s.customer_name = payload['customer_name']
    if 'product' in payload:
        if not payload['product']:
            add_err('product', 'Обязательное поле')
        else:
            s.product = payload['product']
    if 'quantity' in payload:
        try:
            q = int(payload['quantity'])
            if q < 1:
                add_err('quantity', '>= 1')
            else:
                s.quantity = q
        except Exception:
            add_err('quantity', 'Целое число')
    if 'price' in payload:
        try:
            p = float(payload['price'])
            if p < 0:
                add_err('price', '>= 0')
            else:
                s.price = p
        except Exception:
            add_err('price', 'Число')
    if 'date' in payload:
        try:
            y, m, d = map(int, payload['date'].split('-'))
            from datetime import date as ddate
            dt = ddate(y, m, d)
            if dt > ddate.today():
                add_err('date', 'Не в будущем')
            else:
                s.date = dt
        except Exception:
            add_err('date', 'Формат YYYY-MM-DD')

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    # Проверка уникальности
    try:
        s.save()
    except IntegrityError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Дубликат записи']}}, status=400)

    return JsonResponse({'ok': True})


def list_files(request):
    """
    Страница со списком всех файлов JSON/XML из соответствующих папок.
    Требование: проверка на существование файла/ов и информирование при отсутствии.
    """
    json_files = sorted([p.name for p in DATA_DIR_JSON.glob('*.json')])
    xml_files = sorted([p.name for p in DATA_DIR_XML.glob('*.xml')])
    if not json_files and not xml_files:
        messages.info(request, 'На сервере нет файлов данных')
    return render(request, 'sales/files.html', {'json_files': json_files, 'xml_files': xml_files})


def view_file(request, filename: str):
    """
    Просмотр содержимого конкретного файла JSON/XML.
    Требования:
    - Санитизация имени файла (Path(...).name == filename)
    - Повторная проверка валидности перед выводом для безопасности
    """
    # Санитизация: запрещаем пути/слэши в имени
    safe_name = Path(filename).name
    if safe_name != filename:
        raise Http404

    if safe_name.endswith('.json'):
        path = DATA_DIR_JSON / safe_name
        if not path.exists():
            raise Http404
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            # Если файл поврежден/невалиден — 404
            raise Http404
        return render(request, 'sales/view_file.html', {
            'filename': safe_name,
            'content': json.dumps(data, ensure_ascii=False, indent=2),
            'type': 'json'
        })
    elif safe_name.endswith('.xml'):
        path = DATA_DIR_XML / safe_name
        if not path.exists():
            raise Http404
        try:
            txt = path.read_text(encoding='utf-8')
            # Базовая проверка валидности XML
            ET.fromstring(txt)
        except Exception:
            raise Http404
        return render(request, 'sales/view_file.html', {'filename': safe_name, 'content': txt, 'type': 'xml'})
    else:
        # Неизвестное расширение
        raise Http404
