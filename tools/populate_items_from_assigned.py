#!/usr/bin/env python3
"""
Populate items in the web_app SQLite database from assigned_items.json.

Usage:
    python3 tools/populate_items_from_assigned.py
"""
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

try:
    from web_app import create_app_with_db, load_assigned_items, load_config, Machine, Item, db
except Exception as e:
    print(f"Failed to import web_app models: {e}")
    raise


def main():
    app = create_app_with_db()
    with app.app_context():
        config = load_config()
        assigned = load_assigned_items()

        machine_id = config.get('machine_id', 'RAON-001')
        esp32_host = config.get('esp32_host', '192.168.4.1')

        machine = Machine.query.filter_by(machine_id=machine_id).first()
        if not machine:
            machine = Machine(machine_id=machine_id, name=config.get('machine_name', 'RAON Vending Machine'), esp32_host=esp32_host, is_active=True)
            db.session.add(machine)
            db.session.commit()
            print(f"Created machine: {machine_id}")

        slots = assigned.get('slots', []) if isinstance(assigned, dict) else []
        created = 0
        updated = 0

        for slot_idx, slot_data in enumerate(slots, 1):
            if not isinstance(slot_data, dict):
                continue

            # 'terms' holds pricing/quantity per terminal
            terms = slot_data.get('terms', {})
            term1 = terms.get('1', {}) if isinstance(terms, dict) else {}
            if not term1:
                continue

            item_name = slot_data.get('name') or f'Item {slot_idx}'
            try:
                price = float(term1.get('price', 1.0))
            except Exception:
                price = 1.0
            try:
                qty = int(term1.get('quantity', 0))
            except Exception:
                qty = 0

            item = Item.query.filter_by(machine_id=machine.id, name=item_name).first()
            if not item:
                item = Item(
                    machine_id=machine.id,
                    name=item_name,
                    price=price,
                    quantity=qty,
                    slots=str(slot_idx),
                    category=term1.get('category', ''),
                    image_url=term1.get('image', '')
                )
                db.session.add(item)
                created += 1
            else:
                item.price = price
                item.quantity = qty
                item.slots = str(slot_idx)
                updated += 1

        db.session.commit()
        print(f"Populate complete. Created: {created}, Updated: {updated}")


if __name__ == '__main__':
    main()
