from django.shortcuts import render

# Create your views here.

def home(request):
    """Main landing page for Speakle."""
    return render(request, 'main/home.html')
