from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.index, name='index'),
    path('export/', views.export_sale, name='export_sale'),
    path('upload/', views.upload_file, name='upload_file'),
    # Files source
    path('files/', views.list_files, name='list_files'),
    path('files/<str:filename>/', views.view_file, name='view_file'),
    # DB source
    path('db/', views.db_list, name='db_list'),
    path('db/search/', views.db_search, name='db_search'),
    path('db/<int:pk>/delete/', views.db_delete, name='db_delete'),
    path('db/<int:pk>/update/', views.db_update, name='db_update'),
]
