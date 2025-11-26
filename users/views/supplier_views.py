from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from admins.services.supplier_service import SupplierService
from users.helpers.response import APIResponse
from users.helpers.api_key_require import api_key_required

@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def list_suppliers(request):
    result = SupplierService.get_active_suppliers()
    return APIResponse.success(data=result['suppliers'])


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def get_supplier(request, supplier_id):
    result = SupplierService.get_supplier_by_id(supplier_id)
    
    if result['success']:
        supplier = result['supplier']
        public_data = {
            'id': supplier['id'],
            'first_name': supplier['first_name'],
            'last_name': supplier['last_name'],
            'api_type': supplier['api_type'],
            'currency': supplier['currency'],
            'min_order_amount': supplier['min_order_amount'],
            'max_order_amount': supplier['max_order_amount'],
            'description': supplier['description']
        }
        return APIResponse.success(data=public_data)
    
    return APIResponse.not_found(message=result['message'])