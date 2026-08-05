from django.http import JsonResponse
from .models import SubCategory

def get_subcategories_api(request):
    category_id = request.GET.get('category_id') or request.GET.get('category')
    
    if not category_id:
        return JsonResponse([], safe=False)
        
    try:
        subcategories = SubCategory.objects.filter(category_id=category_id).values('id', 'name')
        return JsonResponse(list(subcategories), safe=False)
    except Exception as e:
        return JsonResponse([], safe=False)