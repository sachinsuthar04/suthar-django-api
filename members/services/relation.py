def calculate_relation(viewer, target, all_members_map):
    v_id = viewer.get('id')
    t_id = target.get('id')
    t_gender = target.get('gender')

    # 1. Direct Parent Check
    v_parent_id = viewer.get('parent_id')
    if v_parent_id == t_id:
        return "father" if t_gender == "male" else "mother"

    # 2. Handle NULL Parent (Check via Spouse)
    # If my parent_id is null, but my other parent (the spouse of my father/mother) is the target
    if v_parent_id:
        parent_obj = all_members_map.get(v_parent_id)
        if parent_obj and parent_obj.get('spouse_id') == t_id:
            return "mother" if t_gender == "female" else "father"

    # 3. Handle Sibling when parent_id is null
    # If both have null parents, they might still be siblings if they share the same spouse 
    # (not applicable) OR if they are both listed as parents of the same child.
    t_parent_id = target.get('parent_id')
    if v_parent_id is None and t_parent_id is None:
        # Check if they share a child
        viewer_children = [m['id'] for m in all_members_map.values() if m.get('parent_id') == v_id]
        target_children = [m['id'] for m in all_members_map.values() if m.get('parent_id') == t_id]
        
        # If they share a child, they are spouses, not siblings
        if any(child_id in target_children for child_id in viewer_children):
            return "spouse"

    return "relative"