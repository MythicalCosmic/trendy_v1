from django.shortcuts import render

# Create your views here.

def return_home(request):
    return render(request, 'index.html')