from django.urls import path
from . import views

urlpatterns = [
	path('', views.search, name='search'), # main page
    path('<t>', views.main, name='main'),
    path('convert/<s>', views.convert),
    path('not/found', views.not_found, name='not-found')
]