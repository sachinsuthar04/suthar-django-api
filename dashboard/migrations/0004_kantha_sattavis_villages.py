"""Seed the 35 villages of Kantha Sattavis (from the KSSPL 2.0 poster).

Existing villages with the same English name are updated, not duplicated.
Villages that are not in the list are kept but switched off, so members
who already picked them keep their native place.
"""
from django.db import migrations

KANTHA_SATTAVIS_VILLAGES = [
    (1, "Aglod", "આગલોડ"),
    (2, "Bhavsor", "ભાવસોર"),
    (3, "Bhimpura", "ભીમપુરા"),
    (4, "Chitrodi", "ચિત્રોડી"),
    (5, "Davad", "દાવડ"),
    (6, "Dedhrota", "દેધરોટા"),
    (7, "Derol", "દેરોલ"),
    (8, "Devpura", "દેવપુરા"),
    (9, "Dhanpura", "ધનપુરા"),
    (10, "Eklara", "એકલારા"),
    (11, "Falu", "ફલુ"),
    (12, "Fadeda", "ફદેડા"),
    (13, "Gadha", "ગઢા"),
    (14, "Hansalpur", "હાંસલપુર"),
    (15, "Hirpura", "હીરપુરા"),
    (16, "Himmatpur", "હિંમતપુર"),
    (17, "Hapa", "હાપા"),
    (18, "Ilol", "ઈલોલ"),
    (19, "Jadar", "જાદર"),
    (20, "Jamla", "જામળા"),
    (21, "Kadoli", "કડોલી"),
    (22, "Khedavada", "ખેડાવાડા"),
    (23, "Mahadevpura", "મહાદેવપુરા"),
    (24, "Panpur", "પાણપુર"),
    (25, "Parbada", "પરબડા"),
    (26, "Pedhamali", "પેઢામલી"),
    (27, "Pethapur", "પેથાપુર"),
    (28, "Purushottamnagar", "પુરુષોતમનગર"),
    (29, "Rampura", "રામપુરા"),
    (30, "Rangpur", "રંગપુર"),
    (31, "Ranasipur", "રણાસીપુર"),
    (32, "Rajpur", "રાજપુર"),
    (33, "Sayodar", "સાયોદર"),
    (34, "Sanghpur", "સંઘપુર"),
    (35, "Vaktapur", "વકતાપુર"),
]


def seed(apps, schema_editor):
    Village = apps.get_model("dashboard", "Village")
    names = []
    for number, name, name_gu in KANTHA_SATTAVIS_VILLAGES:
        names.append(name)
        v = Village.objects.filter(name__iexact=name).first() or Village(name=name)
        v.name, v.name_gu, v.number, v.is_active = name, name_gu, number, True
        v.save()
    Village.objects.exclude(name__in=names).update(is_active=False, number=1000)


def unseed(apps, schema_editor):
    pass  # keep data; the schema migration before this one drops the columns


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0003_village_details")]
    operations = [migrations.RunPython(seed, unseed)]
