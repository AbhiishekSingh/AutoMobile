"""Run every seed script in the correct order with one command:

    python -m app.seeds.all

Order matters: users/branches must exist before leads (a lead is assigned
to a PBA and a branch), so users runs first, then leads.
"""
from app.seeds import users, leads


def run():
    print("== Seeding users + branches ==")
    users.run()
    print("\n== Seeding lookups + sample leads ==")
    leads.run()
    print("\nAll seeds complete.")


if __name__ == "__main__":
    run()