
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from .models import District, City

def get_districts(request):
    state_id = request.GET.get('state_id')
    districts = District.objects.filter(state_id=state_id).values('id', 'name')
    return JsonResponse(list(districts), safe=False)

def get_cities(request):
    district_id = request.GET.get('district_id')
    cities = City.objects.filter(district_id=district_id).values('id', 'name')
    return JsonResponse(list(cities), safe=False)