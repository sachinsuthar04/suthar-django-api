from django.db import transaction
from members.models import Member, MemberGender, MemberRole, Family


def heal_family_relations(family: Family | int | None):
    """
    Analyzes all members in a family and automatically infers & heals missing
    father, mother, spouse, and child relationships in the database based on
    their roles and relations.
    """
    if not family:
        return

    family_id = family.id if isinstance(family, Family) else family
    members = list(Member.objects.filter(family_id=family_id))
    if not members:
        return

    # 1. Identify Family Head
    head = next((m for m in members if m.role == MemberRole.FAMILY_HEAD), None)
    if not head:
        head_user_id = None
        if isinstance(family, Family) and family.head_id:
            head_user_id = family.head_id
        else:
            fam_obj = Family.objects.filter(id=family_id).first()
            if fam_obj:
                head_user_id = fam_obj.head_id

        if head_user_id:
            head = next((m for m in members if m.user_id == head_user_id), None)

    if not head and members:
        head = members[0]

    # Map members by ID for quick access
    member_map = {m.id: m for m in members}
    dirty_members = set()

    # 2. Categorize relations relative to Head
    spouse = None
    father = None
    mother = None
    grandfather = None
    grandmother = None
    sons = []
    daughters = []
    brothers = []
    sisters = []
    uncles = []
    buas = []

    for m in members:
        if m.id == head.id:
            continue
        rel = (m.relation or "").lower()

        # Check existing links or relation string
        if rel == "spouse" or head.spouse_id == m.id or m.spouse_id == head.id:
            spouse = m
        elif rel == "father" or head.father_id == m.id:
            father = m
        elif rel == "mother" or head.mother_id == m.id:
            mother = m
        elif rel == "grandfather":
            grandfather = m
        elif rel == "grandmother":
            grandmother = m
        elif rel == "son" or (m.father_id == head.id and m.gender == MemberGender.MALE):
            sons.append(m)
        elif rel == "daughter" or (m.father_id == head.id and m.gender == MemberGender.FEMALE):
            daughters.append(m)
        elif rel == "brother":
            brothers.append(m)
        elif rel == "sister":
            sisters.append(m)
        elif rel == "uncle":
            uncles.append(m)
        elif rel == "bua":
            buas.append(m)

    # 3. Heal Head & Spouse
    if spouse:
        if head.spouse_id != spouse.id:
            head.spouse = spouse
            dirty_members.add(head)
        if spouse.spouse_id != head.id:
            spouse.spouse = head
            dirty_members.add(spouse)

    # 4. Heal Head & Parents
    if father:
        if head.father_id != father.id:
            head.father = father
            dirty_members.add(head)
    if mother:
        if head.mother_id != mother.id:
            head.mother = mother
            dirty_members.add(head)
    if father and mother:
        if father.spouse_id != mother.id:
            father.spouse = mother
            dirty_members.add(father)
        if mother.spouse_id != father.id:
            mother.spouse = father
            dirty_members.add(mother)

    # 5. Heal Grandparents
    if grandfather and father:
        if father.father_id != grandfather.id:
            father.father = grandfather
            dirty_members.add(father)
    if grandmother and father:
        if father.mother_id != grandmother.id:
            father.mother = grandmother
            dirty_members.add(father)
    if grandfather and grandmother:
        if grandfather.spouse_id != grandmother.id:
            grandfather.spouse = grandmother
            dirty_members.add(grandfather)
        if grandmother.spouse_id != grandfather.id:
            grandmother.spouse = grandfather
            dirty_members.add(grandmother)

    # 6. Heal Siblings (Brothers and Sisters of Head)
    effective_father = father or head.father
    effective_mother = mother or head.mother
    for sib in brothers + sisters:
        if effective_father and sib.father_id != effective_father.id:
            sib.father = effective_father
            dirty_members.add(sib)
        if effective_mother and sib.mother_id != effective_mother.id:
            sib.mother = effective_mother
            dirty_members.add(sib)

    # 7. Heal Children (Sons and Daughters of Head)
    effective_spouse = spouse or head.spouse
    children = sons + daughters
    for child in children:
        if head.gender == MemberGender.FEMALE:
            if child.mother_id != head.id:
                child.mother = head
                dirty_members.add(child)
            if effective_spouse and child.father_id != effective_spouse.id:
                child.father = effective_spouse
                dirty_members.add(child)
        else:
            if child.father_id != head.id:
                child.father = head
                dirty_members.add(child)
            if effective_spouse and child.mother_id != effective_spouse.id:
                child.mother = effective_spouse
                dirty_members.add(child)

    # 8. Heal Uncle & Bua
    for u in uncles + buas:
        if grandfather and u.father_id != grandfather.id:
            u.father = grandfather
            dirty_members.add(u)
        if grandmother and u.mother_id != grandmother.id:
            u.mother = grandmother
            dirty_members.add(u)

    # 9. Cross-heal Spouses & Children across all members
    for m in members:
        # If member has a spouse and children
        if m.spouse_id and m.spouse_id in member_map:
            sp = member_map[m.spouse_id]
            if sp.spouse_id != m.id:
                sp.spouse = m
                dirty_members.add(sp)

            # Any child having m as father should have sp as mother (if sp is female)
            if m.gender == MemberGender.MALE or sp.gender == MemberGender.FEMALE:
                father_m = m if m.gender == MemberGender.MALE else sp
                mother_m = sp if sp.gender == MemberGender.FEMALE else m
                for child in members:
                    if child.father_id == father_m.id and child.mother_id != mother_m.id:
                        child.mother = mother_m
                        dirty_members.add(child)
                    elif child.mother_id == mother_m.id and child.father_id != father_m.id:
                        child.father = father_m
                        dirty_members.add(child)

    # 10. Save all modified members atomically
    if dirty_members:
        with transaction.atomic():
            for m in dirty_members:
                m.save(update_fields=["father", "mother", "spouse"])


def get_relationship(viewer: Member, target: Member) -> str:
    """
    Calculates the relationship of the target relative to the viewer.
    Returns strings like 'Father', 'Mother', 'Son', 'Daughter', 'Brother', 'Sister',
    'Husband', 'Wife', 'Grandfather', 'Grandmother', 'Grandson', 'Granddaughter',
    'Uncle', 'Bua', 'Nephew', 'Niece', etc.
    """
    if not viewer or not target:
        return "Unknown"

    if viewer.id == target.id:
        return "Self"

    target_gender = target.gender
    is_male = (target_gender == MemberGender.MALE)
    is_female = (target_gender == MemberGender.FEMALE)

    def gender_label(male_label, female_label, default_label):
        if is_male:
            return male_label
        if is_female:
            return female_label
        return default_label

    # 1. Spouse
    if (viewer.spouse_id == target.id) or (target.spouse_id == viewer.id):
        return gender_label("Husband", "Wife", "Spouse")

    # 2. Parents
    if viewer.father_id == target.id:
        return "Father"
    if viewer.mother_id == target.id:
        return "Mother"

    # 3. Children
    if target.father_id == viewer.id or target.mother_id == viewer.id:
        return gender_label("Son", "Daughter", "Child")

    # 4. Siblings (Sharing at least one parent or marked as brother/sister)
    share_father = (viewer.father_id is not None and viewer.father_id == target.father_id)
    share_mother = (viewer.mother_id is not None and viewer.mother_id == target.mother_id)
    
    if share_father or share_mother:
        return gender_label("Brother", "Sister", "Sibling")

    # 5. Grandparents
    if viewer.father_id:
        viewer_father = viewer.father
        if viewer_father:
            if viewer_father.father_id == target.id:
                return "Grandfather"
            if viewer_father.mother_id == target.id:
                return "Grandmother"
            
    if viewer.mother_id:
        viewer_mother = viewer.mother
        if viewer_mother:
            if viewer_mother.father_id == target.id:
                return "Grandfather"
            if viewer_mother.mother_id == target.id:
                return "Grandmother"

    # 6. Grandchildren
    if target.father_id:
        target_father = target.father
        if target_father and (target_father.father_id == viewer.id or target_father.mother_id == viewer.id):
            return gender_label("Grandson", "Granddaughter", "Grandchild")
            
    if target.mother_id:
        target_mother = target.mother
        if target_mother and (target_mother.father_id == viewer.id or target_mother.mother_id == viewer.id):
            return gender_label("Grandson", "Granddaughter", "Grandchild")

    # 7. Uncle & Aunt (Father's or Mother's siblings)
    if viewer.father_id and viewer.father:
        vf = viewer.father
        vf_share_father = (vf.father_id is not None and vf.father_id == target.father_id)
        vf_share_mother = (vf.mother_id is not None and vf.mother_id == target.mother_id)
        if vf_share_father or vf_share_mother:
            return "Uncle" if is_male else ("Bua" if is_female else "Uncle/Aunt")

    if viewer.mother_id and viewer.mother:
        vm = viewer.mother
        vm_share_father = (vm.father_id is not None and vm.father_id == target.father_id)
        vm_share_mother = (vm.mother_id is not None and vm.mother_id == target.mother_id)
        if vm_share_father or vm_share_mother:
            return "Uncle" if is_male else "Aunt"

    # 8. Nephew & Niece (Sibling's children)
    if target.father_id and target.father:
        tf = target.father
        tf_share_father = (viewer.father_id is not None and viewer.father_id == tf.father_id)
        tf_share_mother = (viewer.mother_id is not None and viewer.mother_id == tf.mother_id)
        if tf_share_father or tf_share_mother:
            return gender_label("Nephew", "Niece", "Nephew/Niece")

    if target.mother_id and target.mother:
        tm = target.mother
        tm_share_father = (viewer.father_id is not None and viewer.father_id == tm.father_id)
        tm_share_mother = (viewer.mother_id is not None and viewer.mother_id == tm.mother_id)
        if tm_share_father or tm_share_mother:
            return gender_label("Nephew", "Niece", "Nephew/Niece")

    # 9. In-laws (Spouse's parents)
    if viewer.spouse_id and viewer.spouse:
        vs = viewer.spouse
        if vs.father_id == target.id:
            return "Father-in-law"
        if vs.mother_id == target.id:
            return "Mother-in-law"

    # Fallback to the stored relation
    if target.relation:
        return str(target.relation).capitalize()

    return "Relative"
