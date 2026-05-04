import json
import math
from pathlib import Path

RULES_PATH = Path(__file__).with_name('pricing_rules.json')


def load_rules():
    return json.loads(RULES_PATH.read_text())


def clamp_minimum(low, high, rules=None):
    rules = rules or load_rules()
    minimum = rules['business']['minimum_service_call']
    return max(minimum, round(low)), max(minimum, round(high))


def wall_sqft(width_ft=None, height_ft=None):
    if not width_ft or not height_ft:
        return None
    return round(float(width_ft) * float(height_ft), 1)


def drywall_estimate(area_sqft, include_paint=True):
    rules = load_rules()
    s = rules['services']['drywall_patch']
    if area_sqft <= 2:
        low, high = s['small_patch_under_2sqft']
    elif area_sqft <= 8:
        low, high = s['medium_patch_2_8sqft']
    elif area_sqft <= 32:
        low, high = s['large_patch_8_32sqft']
    else:
        # large patch/section: base + sqft multiplier
        low = 650 + area_sqft * 8
        high = 1100 + area_sqft * 16
    if include_paint:
        p_low, p_high = s['finish_paint_extra']
        low += p_low
        high += p_high
    return clamp_minimum(low, high, rules)


def painting_wall_estimate(area_sqft):
    rules = load_rules()
    s = rules['services']['painting_touchup']
    low = area_sqft * s['per_wall_labor_low_per_sqft']
    high = area_sqft * s['per_wall_labor_high_per_sqft']
    return clamp_minimum(low, high, rules)


def fixed_range(service, key):
    rules = load_rules()
    low, high = rules['services'][service][key]
    return clamp_minimum(low, high, rules)


def estimate_from_structured(job_type, width_ft=None, height_ft=None, quantity=1, surface=None, complexity='standard'):
    rules = load_rules()
    qty = max(1, int(quantity or 1))
    jt = (job_type or '').lower()
    sqft = wall_sqft(width_ft, height_ft)
    notes = []

    if jt in ['drywall', 'drywall_patch', 'wall_repair']:
        if sqft is None:
            return {'needs_more_info': True, 'question': 'Need damaged area width and height in feet, or a photo with tape measure/known object for scale.'}
        low, high = drywall_estimate(sqft)
        return {'job_type': 'drywall_patch', 'sqft': sqft, 'price_low': low, 'price_high': high, 'notes': ['Includes rough patch/finish range. Paint match may add cost.']}

    if jt in ['paint', 'painting', 'wall_paint']:
        if sqft is None:
            return {'needs_more_info': True, 'question': 'Need wall width and height in feet to calculate square feet.'}
        low, high = painting_wall_estimate(sqft)
        return {'job_type': 'painting_touchup', 'sqft': sqft, 'price_low': low, 'price_high': high, 'notes': ['Paint/material not included unless specified.']}

    if jt in ['hose_reel', 'hose reel', 'hose_reel_mounting']:
        key = 'brick_tapcon' if surface in ['brick', 'masonry', 'concrete'] else 'vinyl_or_wood'
        low, high = fixed_range('hose_reel_mounting', key)
        if qty > 1:
            add_low, add_high = rules['services']['hose_reel_mounting']['multiple_units_each_after_first']
            low += add_low * (qty - 1)
            high += add_high * (qty - 1)
        return {'job_type': 'hose_reel_mounting', 'quantity': qty, 'surface': surface, 'price_low': low, 'price_high': high, 'notes': ['Brick uses Tapcon/concrete screws. Final depends on wall and bracket holes.']}

    if jt in ['tv', 'tv_mounting']:
        key = 'brick_or_masonry' if surface in ['brick', 'masonry', 'concrete'] else 'standard_wall'
        if complexity == 'fireplace': key = 'above_fireplace'
        low, high = fixed_range('tv_mounting', key)
        return {'job_type': 'tv_mounting', 'surface': surface, 'price_low': low, 'price_high': high, 'notes': ['Concealed wiring or special mount can add cost.']}

    return {'needs_more_info': True, 'question': 'Send job type, quantity, surface, and dimensions if wall/paint/drywall.'}


def format_estimate(result):
    if result.get('needs_more_info'):
        return 'Need more info: ' + result.get('question', '')
    lines = []
    lines.append('📋 FixCraft VP rough estimate')
    lines.append(f"Job: {result.get('job_type','unknown')}")
    if result.get('sqft'):
        lines.append(f"Area: ~{result['sqft']} sq ft")
    if result.get('quantity'):
        lines.append(f"Quantity: {result['quantity']}")
    if result.get('surface'):
        lines.append(f"Surface: {result['surface']}")
    lines.append(f"Ballpark: ${result['price_low']}–${result['price_high']}")
    if result.get('notes'):
        lines.append('Notes: ' + ' '.join(result['notes']))
    lines.append('Final price after Vlad confirms scope/photos/on-site conditions.')
    return '\n'.join(lines)
