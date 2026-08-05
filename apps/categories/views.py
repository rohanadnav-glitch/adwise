from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import SubCategory

@require_GET
def get_subcategories_api(request):
    category_id = request.GET.get('category_id')
    if not category_id or not category_id.isdigit():
        return JsonResponse({'subcategories': [], 'error': 'Valid Category ID required'}, status=400)

    subcategories = list(SubCategory.objects.filter(category_id=category_id).values('id', 'name'))
    return JsonResponse({'subcategories': subcategories}, status=200)