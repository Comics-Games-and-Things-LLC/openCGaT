from game_info.models import Game
from shop.models import Publisher


def navbar_links(request):
    try:
        return {'top_publishers': get_top_publishers(),
                "top_games": get_top_games(), }
    except Exception as e:
        print(e)
        return {}


def get_top_games():
    return Game.objects.filter(navbar_order__isnull=False).order_by("navbar_order")


def get_top_publishers():
    return Publisher.objects.filter(navbar_order__isnull=False).order_by("navbar_order")
