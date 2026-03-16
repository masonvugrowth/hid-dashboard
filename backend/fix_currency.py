import sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models.branch import Branch

db = SessionLocal()

currency_map = {
    "11111111-1111-1111-1111-111111111101": "TWD",   # Taipei
    "11111111-1111-1111-1111-111111111102": "VND",   # Saigon
    "11111111-1111-1111-1111-111111111103": "VND",   # 1948 Hanoi
    "11111111-1111-1111-1111-111111111104": "VND",   # Oani Da Nang
    "11111111-1111-1111-1111-111111111105": "JPY",   # Osaka
}

for bid, cur in currency_map.items():
    b = db.query(Branch).filter_by(id=bid).first()
    if b:
        b.currency = cur
        print(f"  {b.name} -> {cur}")

db.commit()
db.close()
print("Done.")
