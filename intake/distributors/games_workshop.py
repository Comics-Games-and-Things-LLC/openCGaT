import os
import traceback
from decimal import ROUND_UP

import pandas
import pypdf_table_extraction
from django.utils.text import slugify

from game_info.models import Game
from intake.distributors.common import create_valhalla_item
from intake.distributors.utility import create_subfactions, create_factions, log
from intake.models import *
from openCGaT.management_util import email_report
from shop.models import Product, Publisher, InventoryItem

HORUS_HERESY = "Warhammer: The Horus Heresy"

AERONAUTICA_IMPERIALIS = "Aeronautica Imperialis"

BLOOD_BOWL = "Blood Bowl"

CITIES_OF_SIGMAR = "Cities of Sigmar"

BEASTS_OF_CHAOS = "Beasts of Chaos"

AGE_OF_SIGMAR = "Warhammer: Age of Sigmar"

GREY_KNIGHTS = 'Grey Knights'

OGOR_MAWTRIBES = "Ogor Mawtribes"

ALLIANCE_DESTRUCTION = "Grand Alliance Destruction"

GRAND_ALLIANCE_CHAOS = "Grand Alliance Chaos"

GRAND_ALLIANCE_DEATH = "Grand Alliance Death"

SKAVEN = "Skaven"

SYLVANETH = "Sylvaneth"

STORMCAST_ETERNALS = "Stormcast Eternals"

SERAPHON = "Seraphon"

LUMINETH_REALM_LORDS = "Lumineth Realm-Lords"

DAUGHTERS_OF_KHAINE = "Daughters of Khaine"

IDONETH_DEEPKIN = "Idoneth Deepkin"

NECRONS = "Necrons"

IMPERIUM_OF_MAN = "Imperium of Man"

CHAOS_DAEMONS = "Chaos Daemons"

DEATH_GUARD = "Death Guard"

DRUKHARI = "Drukhari"

CRAFTWORLDS = "Craftworlds"

T_AU_EMPIRE = "T'au Empire"

ORKS = "Orks"

TYRANIDS = "Tyranids"

GENESTEALER_CULTS = "Genestealer Cults"

ASTRA_MILITARUM = "Astra Militarum"

ADEPTUS_MECHANICUS = 'Adeptus Mechanicus'

WARHAMMER_40K = "Warhammer 40k"

SPACE_MARINES = 'Space Marines'
CHAOS_SPACE_MARINES = 'Chaos Space Marines'
DEATHWATCH = 'Deathwatch'

dist_name = "Games Workshop"


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]

    publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
    wh40k, _ = Game.objects.get_or_create(name=("%s" % WARHAMMER_40K))

    imperium40k, _ = wh40k.factions.get_or_create(name=("%s" % IMPERIUM_OF_MAN))
    spacemarines, _ = imperium40k.subfactions.get_or_create(name=SPACE_MARINES, game=wh40k)
    create_subfactions(spacemarines, ['Space Wolves',
                                      'Blood Angels',
                                      'Dark Angels',
                                      'Ultramarines',
                                      'Iron Hands',
                                      ('%s' % GREY_KNIGHTS),
                                      DEATHWATCH,
                                      'Imperial Fists',
                                      'White Scars'])
    create_subfactions(imperium40k, [
        'Adeptus Soroitas',
        'Adeptus Custodes',
        ('%s' % ADEPTUS_MECHANICUS),
        ("%s" % ASTRA_MILITARUM),
        "Imperial Knights",
        "Inquisition",
        "Officio Assassinorum",
        "Sisters of Silence",
    ])
    chaos40k, _ = wh40k.factions.get_or_create(name="Armies of Chaos")

    create_subfactions(chaos40k, [
        ("%s" % CHAOS_DAEMONS),
        "Chaos Knights",
        CHAOS_SPACE_MARINES,
        ("%s" % DEATH_GUARD),
        "Thousand Sons",
        "World Eaters",
    ])

    eldar40k, _ = wh40k.factions.get_or_create(name='Eldar')
    create_subfactions(eldar40k, [
        ("%s" % CRAFTWORLDS),
        ("%s" % DRUKHARI),
        "Harlequins",
        "Ynnari",
    ])
    tyranids40k, _ = wh40k.factions.get_or_create(name='Tyranid Broods')
    create_subfactions(tyranids40k, [
        ("%s" % GENESTEALER_CULTS),
        ("%s" % TYRANIDS),
        "Brood Brothers"
    ])

    create_factions(wh40k, [
        ("%s" % NECRONS),
        ("%s" % ORKS),
        ("%s" % T_AU_EMPIRE)
    ])

    aos, _ = Game.objects.get_or_create(name=("%s" % AGE_OF_SIGMAR))
    order, _ = aos.factions.get_or_create(name="Grand Alliance Order")
    create_subfactions(order, [("%s" % CITIES_OF_SIGMAR),
                               ("%s" % DAUGHTERS_OF_KHAINE),
                               "Fyreslayers",
                               ("%s" % IDONETH_DEEPKIN),
                               "Kharadron Overlords",
                               ("%s" % LUMINETH_REALM_LORDS),
                               ("%s" % SERAPHON),
                               ("%s" % STORMCAST_ETERNALS),
                               ("%s" % SYLVANETH)
                               ])
    aoschaos, _ = aos.factions.get_or_create(name=("%s" % GRAND_ALLIANCE_CHAOS))
    create_subfactions(aoschaos, [
        ("%s" % BEASTS_OF_CHAOS),
        "Blades of Khorne",
        "Disciples of Tzeentch",
        "Hedonites of Slaanesh",
        "Maggotkin of Nurgle",
        ("%s" % SKAVEN),
        "Slaves to Darkness",

    ])
    aosdeath, _ = aos.factions.get_or_create(name=("%s" % GRAND_ALLIANCE_DEATH))
    create_subfactions(aosdeath, [
        "Flesh-eater Courts",
        "Nighthaunt",
        "Ossiarch Bonereapers",
        "Soulblight Gravelords"
    ])

    aosdestruction, _ = aos.factions.get_or_create(name=("%s" % ALLIANCE_DESTRUCTION))
    create_subfactions(aosdestruction, [
        "Gloomspite Gitz",
        ("%s" % OGOR_MAWTRIBES),
        "Orruk Warclans",
        "Sons of Behemat",
    ])

    # reset existing trade ranges:
    TradeRange.objects.filter(distributor=distributor).delete()

    trade_range_name = None
    # trade_range_name = "US Price Adjustment File - 09.08.xlsx"
    inventories_path = './intake/inventories/'
    if trade_range_name is None:
        for file in os.listdir(inventories_path):
            if "Trade Range" in file or "USA PRICE RISE" in file:
                trade_range_name = file
    if trade_range_name is None:
        print("Please have a file with 'Trade Range' or 'USA Price Rise' in the inventories folder")
        exit()
    file = pandas.ExcelFile(os.path.join(inventories_path, trade_range_name))
    dataframe = pandas.read_excel(file, header=0, sheet_name='USA', converters={'Product': str, 'Barcode': str})
    # dataframe = pandas.read_excel(file, header=3, sheet_name='USD Pricelist',
    #                               converters={'Product': str, 'Barcode': str, 'Product Code': str})

    records = dataframe.to_dict(orient='records')
    created_products_list = open(f"reports/created_products_{datetime.now()}.txt", "w")

    checked_short_codes = []

    price_adjustment_csv = open(f"reports/valhalla_inventory_price_adjustments_gw_{datetime.now()}.csv", "w")

    f = open(f"reports/gw_price_adjustments_{datetime.now()}.txt", "a")
    log(f, "Creating products and adjusting prices for games workshop")
    for row in records:
        # print(row)
        try:
            product_code = row.get('Product', row.get("Product Code"))
            short_code = row.get('Short Code', row.get("SS Code"))
            checked_short_codes.append(short_code)
            name = row.get('Description')
            barcode = row.get('Barcode')
            msrp = Money(row.get('US/$ Retail', row.get("New US Retail Price")), currency='USD', decimal_places=2)
            maprice = Money(Decimal(msrp.amount * Decimal(.85)).quantize(Decimal('.01'), rounding=ROUND_UP),
                            currency='USD', decimal_places=2)
            dist_price = Money(row.get('US/$ Trade', row.get("New US Trade Price")), currency='USD')
            games, factions, categories = get_product_information_from_product_code(product_code)
            range_code = row.get("Module")
            trade_range = None
            if range_code:
                trade_range, _ = TradeRange.objects.get_or_create(code=range_code, distributor=distributor,
                                                                  defaults={'name': range_code})

            if name and name.strip() != '' and (
                    (barcode and barcode.strip() != '') or (short_code and short_code.strip() != '')
            ):
                DistItem.objects.filter(distributor=distributor, dist_barcode=barcode).delete()
                item, created = DistItem.objects.get_or_create(
                    distributor=distributor,
                    dist_barcode=barcode,
                    dist_number=short_code,
                )
                item.dist_name = name
                item.dist_barcode = barcode
                item.dist_price = dist_price
                item.msrp = msrp
                item.map = maprice
                item.trade_range.clear()
                if range_code:
                    item.trade_range.add(trade_range)
                item.quantity_per_pack = row.get("Pack Qty")
                item.save()

                created = False
                products = []
                if barcode and Product.objects.filter(barcode=barcode).exists():
                    products = [Product.objects.get(barcode=barcode)]
                elif Product.objects.filter(publisher_short_sku=short_code).exists():
                    products = Product.objects.filter(publisher_short_sku=short_code)
                else:
                    continue  # Don't create products right now
                    # Create the new product
                    created = True

                    # Append year to name if there's any existing.
                    if Product.objects.filter(slug=slugify(name)).exists():
                        name += f" ({datetime.today().year})"

                    created_products_list.write(barcode + "\n")
                    log(f, f"Creating product for {name}")
                    product = Product.objects.create(
                        barcode=barcode,
                        release_date=datetime.today(),
                        name=name.title(),
                    )

                    product.games.set(games)
                    product.factions.set(factions)

                    if product.publisher_short_sku is None:
                        product.publisher_short_sku = short_code
                        print(f"Set short code on {product.name} to {short_code}")

                    # Get products this product could be replacing, that aren't already replaced.
                    old_short_code_products = Product.objects.filter(publisher_short_sku=short_code) \
                        .exclude(barcode=barcode, replaced_by__isnull=False)

                    if old_short_code_products.count() == 1:
                        old_product = old_short_code_products.get()
                        if old_product:
                            old_product.replaced_by = product
                            old_product.save()
                    products = [product]

                for product in products:
                    if product.publisher_short_sku is None:
                        product.publisher_short_sku = short_code
                        if not created:
                            print(f"Set short code on {product.name} to {short_code}")

                    # GW products in the trade range should always be all retail, reset it if we forgot.
                    product.all_retail = True
                    product.publisher = publisher
                    product.msrp = msrp
                    product.map = maprice
                    product.page_is_draft = False

                    # Set these if they are blank but don't override any existing ones.
                    if not product.games.exists():
                        product.games.set(games)
                    if not product.factions.exists():
                        product.factions.set(factions)

                    product.save()

                    create_valhalla_item(product, f=f, only_adjust_default_price=True,
                                         price_adjustment_csv=price_adjustment_csv)

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values or other error")
            exit(1)

    hidden_products_log = hide_products(checked_short_codes, publisher)
    f.flush()
    price_adjustment_csv.flush()
    hidden_products_log.flush()

    email_report("GW Price Adjustments", [f.name, price_adjustment_csv.name, hidden_products_log.name], )


def hide_products(checked_short_codes, publisher):
    hobby_products, _ = Category.objects.get_or_create(name="Hobby Products")
    hidden_products_log = open(f"reports/hidden_products_{datetime.now()}.txt", "w")
    for product in Product.objects.filter(publisher=publisher) \
            .exclude(publisher_short_sku__in=checked_short_codes).exclude(page_is_draft=True) \
            .exclude(categories=hobby_products):
        count = InventoryItem.objects.filter(product=product).aggregate(sum=Sum("current_inventory"))['sum'] or 0
        if count > 0:
            log(hidden_products_log, f"Hid {product.name}, which we had {count}")
            product.page_is_draft = True
            product.save()
    return hidden_products_log


def get_product_information_from_product_code(product_code):
    game_code = product_code[4:6]  # game system

    games = []
    if game_code == "01":
        games.append(Game.objects.get_or_create(name=WARHAMMER_40K)[0])
    elif game_code == "02":
        games.append(Game.objects.get_or_create(name=AGE_OF_SIGMAR)[0])
    elif game_code == "26":
        games.append(Game.objects.get_or_create(name="Legions Imperialis")[0])
    elif game_code == "05":
        games.append(Game.objects.get_or_create(name="Necromunda")[0])
    elif game_code == "06":
        games.append(Game.objects.get_or_create(name="Warhammer Quest")[0])
    elif game_code == "07":
        games.append(Game.objects.get_or_create(name="Warhammer Underworlds")[0])
    elif game_code == "09":
        games.append(Game.objects.get_or_create(name=("%s" % BLOOD_BOWL))[0])
    elif game_code == "14":
        games.append(Game.objects.get_or_create(name="Middle-earth™ Strategy Battle Game")[0])
    elif game_code == "14":
        games.append(Game.objects.get_or_create(name=("%s" % AERONAUTICA_IMPERIALIS))[0])
    elif game_code == "30":
        games.append(Game.objects.get_or_create(name=("%s" % HORUS_HERESY))[0])
    factions = []

    faction_code = product_code[6:8]  # faction

    for game in games:
        faction = None
        if game.name == WARHAMMER_40K:
            if faction_code == "01":
                faction, _ = game.factions.get_or_create(name=SPACE_MARINES)
            elif faction_code == "02":
                faction, _ = game.factions.get_or_create(name=CHAOS_SPACE_MARINES)
            elif faction_code == "03":
                faction, _ = game.factions.get_or_create(name=ORKS)
            elif faction_code == "04":
                faction, _ = game.factions.get_or_create(name=CRAFTWORLDS)
            elif faction_code == "05":
                faction, _ = game.factions.get_or_create(name=ASTRA_MILITARUM)
            elif faction_code == "06":
                faction, _ = game.factions.get_or_create(name=TYRANIDS)
            elif faction_code == "07":
                faction, _ = game.factions.get_or_create(name=GREY_KNIGHTS)
            elif faction_code == "08":
                faction, _ = game.factions.get_or_create(name=IMPERIUM_OF_MAN)
            elif faction_code == "09":
                faction, _ = game.factions.get_or_create(name=DEATHWATCH)
            elif faction_code == "10":
                faction, _ = game.factions.get_or_create(name=NECRONS)
            elif faction_code == "12":
                faction, _ = game.factions.get_or_create(name=DRUKHARI)
            elif faction_code == "13":
                faction, _ = game.factions.get_or_create(name=T_AU_EMPIRE)
            elif faction_code == "16":
                faction, _ = game.factions.get_or_create(name=ADEPTUS_MECHANICUS)
            elif faction_code == "17":
                faction, _ = game.factions.get_or_create(name=GENESTEALER_CULTS)
        elif game.name == AGE_OF_SIGMAR:
            if faction_code == "01":  # Chaos, probably old Warriors of Chaos?
                faction, _ = game.factions.get_or_create(name=GRAND_ALLIANCE_CHAOS)
            elif faction_code == "02":  # Empire/Humans
                faction, _ = game.factions.get_or_create(name=CITIES_OF_SIGMAR)
            elif faction_code == "04":  # Wood elves
                faction, _ = game.factions.get_or_create(name=SYLVANETH)
            # 5 is dwarves, but could be either variety so leaving uncategorized
            elif faction_code == "06":
                faction, _ = game.factions.get_or_create(name=SKAVEN)
            elif faction_code == "07":  # Vampire counts
                faction, _ = game.factions.get_or_create(name=GRAND_ALLIANCE_DEATH)
            elif faction_code == "08":
                faction, _ = game.factions.get_or_create(name=SERAPHON)
            # 9 is orks and goblins, which is difficult because they are currently two separate factions
            elif faction_code == "09":
                faction, _ = game.factions.get_or_create(name=ALLIANCE_DESTRUCTION)
            elif faction_code == "10":
                faction, _ = game.factions.get_or_create(name=LUMINETH_REALM_LORDS)
            elif faction_code == "12":
                faction, _ = game.factions.get_or_create(name=DAUGHTERS_OF_KHAINE)
            elif faction_code == "13":
                faction, _ = game.factions.get_or_create(name=OGOR_MAWTRIBES)
            elif faction_code == "16":
                faction, _ = game.factions.get_or_create(name=BEASTS_OF_CHAOS)
            elif faction_code == "18":
                faction, _ = game.factions.get_or_create(name=STORMCAST_ETERNALS)
            elif faction_code == "19":
                faction, _ = game.factions.get_or_create(name=IDONETH_DEEPKIN)
        elif game.name == BLOOD_BOWL:
            if faction_code == "01":  # Chaos
                faction, _ = game.factions.get_or_create(name="Chaos")
            elif faction_code == "02":  # Humans
                faction, _ = game.factions.get_or_create(name="Humans")
            elif faction_code == "04":  # Wood elves
                faction, _ = game.factions.get_or_create(name="Wood Elves")
            elif faction_code == "05":
                faction, _ = game.factions.get_or_create(name="Dwarves")
            elif faction_code == "06":
                faction, _ = game.factions.get_or_create(name=SKAVEN)
            elif faction_code == "08":
                faction, _ = game.factions.get_or_create(name="Lizardmen")
            elif faction_code == "09":
                faction, _ = game.factions.get_or_create(name="Orcs & Goblins")
            elif faction_code == "12":
                faction, _ = game.factions.get_or_create(name="Dark Elves")
            elif faction_code == "13":
                faction, _ = game.factions.get_or_create(name="Ogres")
        # TODO: LOTR # Orcs, Humans, Monsters, Generic. Not useful enough to make distinctions, will come back to it later.
        elif game.name == AERONAUTICA_IMPERIALIS:
            if faction_code == "01":
                faction, _ = game.factions.get_or_create(name=SPACE_MARINES)
            elif faction_code == "03":
                faction, _ = game.factions.get_or_create(name=ORKS)
            elif faction_code == "04":
                faction, _ = game.factions.get_or_create(name=CRAFTWORLDS)
            elif faction_code == "08":
                faction, _ = game.factions.get_or_create(name="Imperial Navy")
            elif faction_code == "13":
                faction, _ = game.factions.get_or_create(name=T_AU_EMPIRE)
        elif game.name == HORUS_HERESY:
            if faction_code == "01":
                faction, _ = game.factions.get_or_create(name="Adeptus Astartes")
            elif faction_code == "02":
                faction, _ = game.factions.get_or_create(name="Traitor Astartes")
            elif faction_code == "05":
                faction, _ = game.factions.get_or_create(name="Solar Auxilia")
            elif faction_code == "08":
                faction, _ = game.factions.get_or_create(name="Imperial Knights")
            elif faction_code == "16":
                faction, _ = game.factions.get_or_create(name="Mechanicum")
        elif game.name == "Legions Imperialis":
            if faction_code == "01":
                faction, _ = game.factions.get_or_create(name="Adeptus Astartes")
            elif faction_code == "05":
                faction, _ = game.factions.get_or_create(name="Solar Auxilia")

        if faction is not None:
            factions.append(faction)

    if product_code.startswith("99129915"):  # Chaos Daemons
        games.append(Game.objects.get_or_create(name=WARHAMMER_40K)[0])
        games.append(Game.objects.get_or_create(name=AGE_OF_SIGMAR)[0])
        for game in games:
            faction, _ = game.factions.get_or_create(name=CHAOS_DAEMONS)
            factions.append(faction)
    categories = []
    # hobby_products, _ = Category.objects.get_or_create(name="Hobby Products")
    # paints, _ = Category.get_or_create(name="Paints")
    # citadel_paints, _ = paints.get_children().get_or_create(name="Citadel Paints")
    # if product_code.startswith("991899"):  # Paint
    #     if product_code.startswith("99189950"):  # Base Paint
    #         categories.append(citadel_paints.get_children().get_or_create(name='Base Paints')[0])
    #     elif product_code.startswith("99189951"):  # Layer
    #         categories.append(citadel_paints.get_children().get_or_create(name='Layer Paints')[0])
    #     elif product_code.startswith("99189952"):  # Dry
    #         categories.append(citadel_paints.get_children().get_or_create(name='Drybrush Paints')[0])
    #     elif product_code.startswith("99189953"):  # Shade
    #         categories.append(citadel_paints.get_children().get_or_create(name='Shade Paints')[0])
    #     elif product_code.startswith("99189956"):  # Technical
    #         categories.append(citadel_paints.get_children().get_or_create(name='Technical Paints')[0])
    #     elif product_code.startswith("99189958"):  # Airbrush
    #         categories.append(citadel_paints.get_children().get_or_create(name='Airbrush Paints')[0])
    #     elif product_code.startswith("99189960"):  # Contrast
    #         categories.append(citadel_paints.get_children().get_or_create(name='Contrast Paints')[0])

    return games, factions, categories


def get_dist_object():
    return Distributor.objects.get(dist_name="Games Workshop")


def read_pdf_invoice(pdf_path):
    po = PurchaseOrder.objects.get(po_number=pdf_path.split("/")[-1].split(".")[0], distributor=get_dist_object())
    if not po:
        print("Could not find purchase order for this PDF, skipping.")

    tables = pypdf_table_extraction.read_pdf(pdf_path,
                                             flavor='stream',
                                             pages="1-end",
                                             row_tol=10,
                                             )
    lines = []
    lines_that_could_not_be_parsed = []
    for i, table in enumerate(tables):
        print(f"Table {i}")
        if table.df.to_numpy()[0].tolist()[1] != 'Pack':
            continue
        for line in table.df.to_numpy():
            line = line.tolist()  # Numpy array to list
            dict_line = {}
            dict_line["Quantity"] = line[0]
            if "." not in dict_line["Quantity"]:
                continue
            print(line)
            dict_line["Short Code"] = line[3]
            dict_line["Description"] = line[4]
            dict_line["MSRP"] = line[2]
            dict_line["Cost"] = line[5]
            lines.append(dict_line)

    for i, line in enumerate(lines):
        print(line)
        barcode = find_barcode_from_product(line["Short Code"])
        if barcode is None:
            lines_that_could_not_be_parsed.append(lines)
            print("Could not find product for this short code.")

            continue

        po_lines = POLine.objects.filter(po=po, barcode=barcode)
        if not po_lines.exists():
            lines_that_could_not_be_parsed.append(lines)
            print("Could not find line for this product.")
            continue

        po_line = po_lines.first()
        if not po_line.expected_quantity:
            po_line.expected_quantity = round(float(line["Quantity"]))

        if not po_line.cost_per_item:
            po_line.cost_per_item = Money(line["Cost"], "USD")
        if not po_line.line_number:
            po_line.line_number = i + 1

        if not po_line.msrp_on_line:
            po_line.msrp_on_line = Money(line["MSRP"], "USD")

        po_line.save()

    return po, []


def find_barcode_from_product(short_code):
    products = Product.objects.filter(publisher_short_sku=short_code)
    if products.count() == 1:
        product = products.first()
        return product.barcode
    if not products.exists():
        return None
    return products.order_by("-release_date").first().barcode
