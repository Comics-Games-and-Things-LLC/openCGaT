from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from discount_codes.models import DiscountCode, CodeUsage


# Create your views here.

@csrf_exempt
def apply_code(request, code, cart=None):
    potential_codes = DiscountCode.objects.filter(code=code.lower())
    print(potential_codes)
    if cart is None:
        cart = request.cart
    if potential_codes.exists():
        next_page = request.GET.get("next")

        code = potential_codes.first()
        user = None
        if request.user.is_authenticated:
            user = request.user
        CodeUsage.objects.create(code=code, cart_id=cart.id, user=user)
        if code.validate_code_for_cart(cart):
            pass  # Validating the code saves it to the cart.
        else:
            next_page = reverse('view_cart')  # redirect user to page where they can see error message

        if request.method == "POST":
            return HttpResponse(status=200)
        if next_page is None:
            next_page = reverse('shop')
        return HttpResponseRedirect(next_page)
    else:
        cart.discount_code_message = "The code {} does not exist".format(code)
    cart.discount_code = None
    cart.save()  # Clear code if we can't find the discount.
    return HttpResponse(status=200)
