def calculate_relation(viewer, target, all_members_map):
    v_id = viewer.get('id')
    t_id = target.get('id')
    t_gender = target.get('gender')

    # 0. Check Self
    if v_id == t_id:
        return "self"

    # 1. Direct Parent Check
    v_parent_id = viewer.get('parent_id')
    if v_parent_id == t_id:
        return "father" if t_gender == "male" else "mother"

    # 2. Direct Child Check
    t_parent_id = target.get('parent_id')
    if t_parent_id == v_id:
        return "son" if t_gender == "male" else "daughter"

    # 3. Handle NULL Parent (Check via Spouse)
    # If my parent_id is null, but my other parent (the spouse of my father/mother) is the target
    if v_parent_id:
        parent_obj = all_members_map.get(v_parent_id)
        if parent_obj and parent_obj.get('spouse_id') == t_id:
            return "mother" if t_gender == "female" else "father"

    # 4. Sibling Check (Same parents)
    if v_parent_id and t_parent_id and v_parent_id == t_parent_id:
        return "brother" if t_gender == "male" else "sister"

    # 5. Grandparents & Uncle/Bua Check
    if v_parent_id:
        v_parent_obj = all_members_map.get(v_parent_id)
        if v_parent_obj and v_parent_obj.get('parent_id'):
            v_grandparent_id = v_parent_obj.get('parent_id')
            if v_grandparent_id == t_id:
                return "grandfather" if t_gender == "male" else "grandmother"
            if v_grandparent_id == t_parent_id:
                return "uncle" if t_gender == "male" else "bua"

    # 6. Handle Sibling/Spouse when parent_id is null
    if v_parent_id is None and t_parent_id is None:
        # Check if they share a child
        viewer_children = [m['id'] for m in all_members_map.values() if m.get('parent_id') == v_id]
        target_children = [m['id'] for m in all_members_map.values() if m.get('parent_id') == t_id]
        
        # If they share a child, they are spouses, not siblings
        if any(child_id in target_children for child_id in viewer_children):
            return "spouse"

    return "relative"