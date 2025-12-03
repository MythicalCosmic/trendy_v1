from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from admins.services.service_service import ServiceService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from admins.helpers.require_admin import require_admin

@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def list_services(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search')
    category_id = request.GET.get('category_id')
    supplier_id = request.GET.get('supplier_id')
    status = request.GET.get('status', 'ACTIVE')
    is_featured = request.GET.get('is_featured')
    order_by = request.GET.get('order_by', 'sort_order')
    
    if is_featured:
        is_featured = is_featured.lower() == 'true'
    
    result = ServiceService.get_all_services(
        page=page,
        per_page=per_page,
        search=search,
        category_id=category_id,
        supplier_id=supplier_id,
        status=status,
        is_featured=is_featured,
        order_by=order_by
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_service(request, service_id):
    result = ServiceService.get_service_by_id(service_id)
    
    if result['success']:
        return APIResponse.success(data=result['service'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def create_service(request):
    data = request.POST.dict()
    photo = request.FILES.get("photo")

    # Convert string booleans to actual booleans
    boolean_fields = ['is_featured', 'refill_enabled', 'cancel_enabled']
    for key in boolean_fields:
        if key in data:
            if isinstance(data[key], str):
                data[key] = data[key].lower() in ['true', '1', 'yes']
    
    # Convert numeric strings to numbers
    numeric_fields = ['price_per_100', 'supplier_price_per_100', 'min_quantity', 'max_quantity', 'category_id', 'supplier_id']
    for key in numeric_fields:
        if key in data and data[key]:
            try:
                if key in ['price_per_100', 'supplier_price_per_100']:
                    data[key] = float(data[key])
                else:
                    data[key] = int(data[key])
            except (ValueError, TypeError):
                pass

    required = [
        'name', 'category_id', 'supplier_id', 'price_per_100',
        'supplier_price_per_100', 'min_quantity', 'max_quantity',
        'supplier_service_id'
    ]

    missing = [field for field in required if field not in data]
    if missing:
        return APIResponse.validation_error(
            errors={f: f"{f} is required" for f in missing},
            message=f'Missing required fields: {", ".join(missing)}'
        )

    result = ServiceService.create_service(photo=photo, **data)

    if result['success']:
        return APIResponse.created(
            data={'service_id': result['service'].id},
            message=result['message']
        )

    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST", "PUT", "PATCH"])
@require_admin
def update_service(request, service_id):
    print("Content-Type:", request.content_type)
    print("FILES:", request.FILES)
    print("POST:", request.POST)
    
    # Handle both multipart/form-data and JSON
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.POST.dict()
        files = request.FILES
        
        # Convert string booleans to actual booleans
        boolean_fields = ['is_featured', 'refill_enabled', 'cancel_enabled']
        for key in boolean_fields:
            if key in data:
                # Handle various string representations
                if isinstance(data[key], str):
                    data[key] = data[key].lower() in ['true', '1', 'yes']
                    
        # Convert numeric strings to numbers
        numeric_fields = ['price_per_100', 'supplier_price_per_100', 'min_quantity', 'max_quantity', 'category_id', 'supplier_id']
        for key in numeric_fields:
            if key in data and data[key]:
                try:
                    if key in ['price_per_100', 'supplier_price_per_100']:
                        data[key] = float(data[key])
                    else:
                        data[key] = int(data[key])
                except (ValueError, TypeError):
                    pass
    else:
        data, error = parse_json_body(request)
        if error:
            return error
        files = None

    result = ServiceService.update_service(
        service_id=service_id,
        data=data,
        files=files
    )

    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@require_admin
def delete_service(request, service_id):
    result = ServiceService.delete_service(service_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["PATCH"])
@require_admin
def update_service_status(request, service_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    status = data.get('status')
    if not status:
        return APIResponse.validation_error(
            errors={'status': 'status is required'},
            message='Missing status field'
        )
    
    result = ServiceService.update_service_status(service_id, status)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def toggle_featured(request, service_id):
    result = ServiceService.toggle_featured(service_id)
    
    if result['success']:
        return APIResponse.success(
            data={'is_featured': result['is_featured']},
            message='Featured status toggled'
        )
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_stats(request):
    result = ServiceService.get_service_stats()
    return APIResponse.success(data=result['stats'])