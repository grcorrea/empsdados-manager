"""Restaurant and menu item catalogs for realistic invoice generation."""

RESTAURANT_NAMES: dict[str, list[str]] = {
    "American": [
        "The Classic Diner",
        "Main Street Grill",
        "Liberty Burgers",
        "All-American Eats",
        "Uncle Sam's Kitchen",
        "Stars & Stripes Cafe",
        "Hometown Diner",
        "Route 66 Restaurant",
    ],
    "Italian": [
        "Bella Italia",
        "Luigi's Trattoria",
        "Pasta Paradise",
        "Nonna's Kitchen",
        "Olive Garden Express",
        "Roma Pizzeria",
        "Tuscany Table",
        "Little Italy Cafe",
    ],
    "Mexican": [
        "Taco Fiesta",
        "El Camino Real",
        "Casa Mexicana",
        "Los Amigos Cantina",
        "Salsa Verde",
        "El Toro Loco",
        "Burrito Brothers",
        "Guadalajara Grill",
    ],
    "Asian": [
        "Golden Dragon",
        "Sakura Sushi",
        "Panda Express Plus",
        "Thai Orchid",
        "Wok This Way",
        "Tokyo Kitchen",
        "Beijing Garden",
        "Spice Route",
    ],
    "Fast Food": [
        "Quick Bites",
        "Speedy Eats",
        "Fast Lane Burgers",
        "Grab & Go Grill",
        "Express Kitchen",
        "Rapid Wraps",
        "Drive-Thru Delights",
        "Instant Eats",
    ],
}

MENU_ITEMS: dict[str, list[dict[str, str | float]]] = {
    "American": [
        {"name": "Classic Cheeseburger", "price": 12.99},
        {"name": "BBQ Bacon Burger", "price": 14.99},
        {"name": "Grilled Chicken Sandwich", "price": 11.99},
        {"name": "Caesar Salad", "price": 9.99},
        {"name": "Buffalo Wings (12pc)", "price": 13.99},
        {"name": "Fish & Chips", "price": 15.99},
        {"name": "Club Sandwich", "price": 12.49},
        {"name": "Loaded Nachos", "price": 10.99},
        {"name": "Mac & Cheese", "price": 8.99},
        {"name": "Philly Cheesesteak", "price": 13.99},
    ],
    "Italian": [
        {"name": "Margherita Pizza", "price": 14.99},
        {"name": "Spaghetti Carbonara", "price": 16.99},
        {"name": "Chicken Parmesan", "price": 18.99},
        {"name": "Fettuccine Alfredo", "price": 15.99},
        {"name": "Lasagna", "price": 17.99},
        {"name": "Bruschetta", "price": 8.99},
        {"name": "Tiramisu", "price": 7.99},
        {"name": "Caprese Salad", "price": 11.99},
        {"name": "Garlic Bread", "price": 5.99},
        {"name": "Pepperoni Pizza", "price": 16.99},
    ],
    "Mexican": [
        {"name": "Burrito Supreme", "price": 12.99},
        {"name": "Chicken Tacos (3)", "price": 10.99},
        {"name": "Steak Fajitas", "price": 17.99},
        {"name": "Cheese Quesadilla", "price": 9.99},
        {"name": "Enchiladas Verdes", "price": 14.99},
        {"name": "Nachos Grande", "price": 11.99},
        {"name": "Churros", "price": 5.99},
        {"name": "Guacamole & Chips", "price": 7.99},
        {"name": "Carnitas Bowl", "price": 13.99},
        {"name": "Mexican Street Corn", "price": 4.99},
    ],
    "Asian": [
        {"name": "Kung Pao Chicken", "price": 14.99},
        {"name": "Pad Thai", "price": 13.99},
        {"name": "California Roll (8pc)", "price": 12.99},
        {"name": "General Tso's Chicken", "price": 15.99},
        {"name": "Fried Rice", "price": 10.99},
        {"name": "Spring Rolls (4)", "price": 6.99},
        {"name": "Tom Yum Soup", "price": 8.99},
        {"name": "Teriyaki Salmon", "price": 18.99},
        {"name": "Dumplings (6)", "price": 9.99},
        {"name": "Beef Pho", "price": 14.99},
    ],
    "Fast Food": [
        {"name": "Double Burger Combo", "price": 9.99},
        {"name": "Chicken Nuggets (10pc)", "price": 7.99},
        {"name": "Large Fries", "price": 3.99},
        {"name": "Onion Rings", "price": 4.49},
        {"name": "Hot Dog", "price": 5.99},
        {"name": "Milkshake", "price": 4.99},
        {"name": "Chicken Sandwich", "price": 8.99},
        {"name": "Veggie Burger", "price": 9.49},
        {"name": "Mozzarella Sticks", "price": 5.99},
        {"name": "Apple Pie", "price": 2.99},
    ],
}

MODIFIERS: list[str] = [
    "Extra cheese",
    "No onions",
    "Add bacon",
    "Gluten-free",
    "Spicy",
    "Well done",
    "Sauce on the side",
    "Add avocado",
    "No tomato",
    "Extra sauce",
]


def get_restaurant_names(cuisine_type: str) -> list[str]:
    return RESTAURANT_NAMES.get(cuisine_type, RESTAURANT_NAMES["American"])


def get_menu_items(cuisine_type: str) -> list[dict[str, str | float]]:
    return MENU_ITEMS.get(cuisine_type, MENU_ITEMS["American"])


def get_random_modifiers() -> list[str]:
    return MODIFIERS
