# diagnostic2.py
from orangebox import Parser

parser = Parser.load("btfl_001.bbl")

print("Атрибуты parser:")
for attr in dir(parser):
    if not attr.startswith('_'):
        print(" ", attr)

print("\nПробуем найти имена полей:")
for name in ['field_names', 'fields', 'headers', 'field_names_list', 'columns']:
    val = getattr(parser, name, None)
    if val is not None:
        print(f"  {name} = {val}")