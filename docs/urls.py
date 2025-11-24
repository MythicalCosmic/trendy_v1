from django.urls import path
from .views import return_home
app_name = 'docs'

urlpatterns = [
    path('', return_home, name='home')
]