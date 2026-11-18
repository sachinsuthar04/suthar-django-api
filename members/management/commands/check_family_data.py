from collections import Counter

from django.core.management.base import BaseCommand

from members.models import Member, MemberGender


class Command(BaseCommand):
    help = "Read-only report of family-tree data problems (nothing is modified)."

    def handle(self, *args, **options):
        members = {m.id: m for m in Member.objects.all()}
        problems = []

        def add(m, text):
            problems.append(f"#{m.id} {m.name}: {text}")

        for m in members.values():
            if m.father_id == m.id or m.mother_id == m.id:
                add(m, "is his own parent")
            if m.spouse_id == m.id:
                add(m, "is his own spouse")
            if m.father_id and m.father_id == m.mother_id:
                add(m, f"father and mother are the same person (#{m.father_id})")
            f, mo = members.get(m.father_id), members.get(m.mother_id)
            if f and f.gender == MemberGender.FEMALE:
                add(m, f"father #{f.id} {f.name} is marked female")
            if mo and mo.gender == MemberGender.MALE:
                add(m, f"mother #{mo.id} {mo.name} is marked male")
            sp = members.get(m.spouse_id)
            if sp:
                if sp.spouse_id != m.id:
                    add(m, f"spouse #{sp.id} {sp.name} does not point back")
                if sp.gender == m.gender and m.gender in (MemberGender.MALE, MemberGender.FEMALE):
                    add(m, f"spouse #{sp.id} {sp.name} has the same gender ({m.gender})")
            if not m.gender:
                add(m, "gender missing (relation names need it)")
            for parent in (f, mo):
                if parent and parent.date_of_birth and m.date_of_birth and parent.date_of_birth >= m.date_of_birth:
                    add(m, f"is not younger than parent #{parent.id} {parent.name}")

        heads = Counter(m.family_id for m in members.values() if m.role == "familyHead" and m.family_id)
        for family_id, n in heads.items():
            if n > 1:
                problems.append(f"family #{family_id} has {n} family heads")

        for line in problems:
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS("No problems found.") if not problems
                          else self.style.WARNING(f"{len(problems)} problem(s) found - fix them in the admin."))
