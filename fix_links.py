import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "suthar_backend.settings")
django.setup()

from members.models import Member, MemberRole

def fix_orphaned_members():
    # Find all families
    families_fixed = 0
    members_fixed = 0
    
    heads = Member.objects.filter(role=MemberRole.FAMILY_HEAD)
    for head in heads:
        family = head.family
        if not family:
            continue
            
        # Get all members in this family except the head
        family_members = Member.objects.filter(family=family).exclude(id=head.id)
        
        for member in family_members:
            relation = (member.relation or "").lower()
            updated = False
            
            if relation == "father" and not head.father:
                head.father = member
                head.save(update_fields=["father"])
                updated = True
            elif relation == "mother" and not head.mother:
                head.mother = member
                head.save(update_fields=["mother"])
                updated = True
            elif relation == "spouse" and not head.spouse:
                head.spouse = member
                head.save(update_fields=["spouse"])
                updated = True
            elif relation in ["son", "daughter"]:
                if not member.father and not member.mother:
                    if head.gender == "female":
                        member.mother = head
                        member.save(update_fields=["mother"])
                    else:
                        member.father = head
                        member.save(update_fields=["father"])
                    updated = True
            elif relation in ["brother", "sister"]:
                if not member.father and head.father:
                    member.father = head.father
                    updated = True
                if not member.mother and head.mother:
                    member.mother = head.mother
                    updated = True
                if updated:
                    member.save(update_fields=["father", "mother"])
                    
            if updated:
                members_fixed += 1
                
        families_fixed += 1
        
    print(f"Fixed {members_fixed} orphaned members across {families_fixed} families.")

if __name__ == "__main__":
    fix_orphaned_members()
