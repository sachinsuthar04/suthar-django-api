from members.models import Member, MemberGender

def get_relationship(viewer: Member, target: Member) -> str:
    """
    Calculates the relationship of the target relative to the viewer.
    Returns strings like 'Father', 'Mother', 'Son', 'Daughter', 'Brother', 'Sister', 'Husband', 'Wife', etc.
    """
    if not viewer or not target:
        return "Unknown"

    if viewer.id == target.id:
        return "Self"

    target_gender = target.gender
    is_male = (target_gender == MemberGender.MALE)
    is_female = (target_gender == MemberGender.FEMALE)

    def gender_label(male_label, female_label, default_label):
        if is_male: return male_label
        if is_female: return female_label
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

    # 4. Siblings (Sharing at least one parent)
    share_father = (viewer.father_id is not None and viewer.father_id == target.father_id)
    share_mother = (viewer.mother_id is not None and viewer.mother_id == target.mother_id)
    
    if share_father or share_mother:
        return gender_label("Brother", "Sister", "Sibling")

    # 5. Grandparents
    if viewer.father_id:
        viewer_father = viewer.father
        if viewer_father.father_id == target.id:
            return "Grandfather"
        if viewer_father.mother_id == target.id:
            return "Grandmother"
            
    if viewer.mother_id:
        viewer_mother = viewer.mother
        if viewer_mother.father_id == target.id:
            return "Grandfather"
        if viewer_mother.mother_id == target.id:
            return "Grandmother"

    # 6. Grandchildren
    if target.father_id:
        target_father = target.father
        if target_father.father_id == viewer.id or target_father.mother_id == viewer.id:
            return gender_label("Grandson", "Granddaughter", "Grandchild")
            
    if target.mother_id:
        target_mother = target.mother
        if target_mother.father_id == viewer.id or target_mother.mother_id == viewer.id:
            return gender_label("Grandson", "Granddaughter", "Grandchild")

    # Fallback to the stored relation
    if target.relation:
        return str(target.relation).capitalize()

    return "Relative"
