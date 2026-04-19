"""Fixtures for PatchWriter tests: Python source snippets used as input/expected output."""

# --- EDS: function missing docstring ---

EDS_MISSING_DOCSTRING_SOURCE = '''\
def compute_total(items, tax_rate):
    result = sum(item.price for item in items)
    return result * (1 + tax_rate)
'''

EDS_EXPECTED_WITH_DOCSTRING = '''\
def compute_total(items, tax_rate):
    """TODO: document compute_total."""
    result = sum(item.price for item in items)
    return result * (1 + tax_rate)
'''

# --- EDS: function that already has a docstring (no-op) ---

EDS_ALREADY_HAS_DOCSTRING = '''\
def compute_total(items, tax_rate):
    """Compute the total price including tax."""
    result = sum(item.price for item in items)
    return result * (1 + tax_rate)
'''

# --- EDS: async function missing docstring ---

EDS_ASYNC_MISSING_DOCSTRING = '''\
async def fetch_user(user_id):
    response = await http.get(f"/users/{user_id}")
    return response.json()
'''

EDS_ASYNC_EXPECTED_WITH_DOCSTRING = '''\
async def fetch_user(user_id):
    """TODO: document fetch_user."""
    response = await http.get(f"/users/{user_id}")
    return response.json()
'''

# --- GCD: function missing guard clause ---

GCD_MISSING_GUARD_SOURCE = '''\
def process_order(order, user):
    total = sum(item.price for item in order.items)
    return user.apply_discount(total)
'''

GCD_EXPECTED_WITH_GUARD_ORDER = '''\
def process_order(order, user):
    if order is None:
        raise TypeError("order must not be None")
    total = sum(item.price for item in order.items)
    return user.apply_discount(total)
'''

# Both params guarded
GCD_EXPECTED_WITH_GUARD_BOTH = '''\
def process_order(order, user):
    if order is None:
        raise TypeError("order must not be None")
    if user is None:
        raise TypeError("user must not be None")
    total = sum(item.price for item in order.items)
    return user.apply_discount(total)
'''

# --- GCD: function that already has a guard for one param (partial) ---

GCD_PARTIAL_GUARD = '''\
def process_order(order, user):
    if order is None:
        raise TypeError("order must not be None")
    total = sum(item.price for item in order.items)
    return user.apply_discount(total)
'''

GCD_PARTIAL_EXPECTED_SECOND_GUARD = '''\
def process_order(order, user):
    if order is None:
        raise TypeError("order must not be None")
    if user is None:
        raise TypeError("user must not be None")
    total = sum(item.price for item in order.items)
    return user.apply_discount(total)
'''
