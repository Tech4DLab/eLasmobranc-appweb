from django.urls import path

from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "mainpage"
urlpatterns = [
    path("", views.main_page, name="main_page"),
    path("ver-zip/", views.ver_imagenes, name="ver_imagenes"),
    path("borrar-temp/", views.borrar_temp, name="borrar_temp"),
    
    path("pdf/generar/", views.generar_pdf, name="generar_pdf"),
    path("pdf/descargar/<str:token>/", views.descargar_pdf_token, name="descargar_pdf_token"),
    path("borrar-temp/", views.borrar_temp, name="borrar_temp"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

