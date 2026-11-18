# members/views.py
from datetime import date

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from members.signals import sync_member_to_profile_helper
from notifications.models import Notification

from .models import (
    Community,
    Family,
    FamilyHeadRequest,
    HeadRequestKind,
    Member,
    MemberRelation,
    MemberRole,
    MemberStatus,
    ProfileChangeRequest,
    RelationshipRequest,
    RelationshipRequestStatus,
    ReviewStatus,
)
from .permissions import (
    IsActiveMember,
    IsAppAdmin,
    IsFamilyHead,
    get_member,
    is_app_admin,
)
from .serializers import (
    MemberCreateSerializer,
    MemberProfileUpdateSerializer,
    MemberSelfUpdateSerializer,
    MemberSerializer,
    check_circular_dependency,
    handle_spouse_link,
)
from .services import households
from .services.changes import (
    KEY_FIELDS,
    accept_change_request,
    audit,
    queue_changes,
    reject_change_request,
    split_key_changes,
)
from .services.kinship import KinshipGraph, build_edges, collect_ego_tree, generation_span, relations_from

MEMBER_SELECT = ("user__user_profile__personal", "family__head")


def _members_qs():
    return Member.objects.select_related(*MEMBER_SELECT)


def _head_member(user):
    return (
        Member.objects.filter(user=user, role=MemberRole.FAMILY_HEAD, status=MemberStatus.ACTIVE)
        .order_by("id")
        .first()
    )


def _fail(message, code=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({"success": False, "message": message, **extra}, status=code)


# ============================================================
# FAMILY HEAD → ADD MEMBER
# ============================================================
class FamilyHeadAddMember(APIView):
    permission_classes = [IsAuthenticated, IsFamilyHead]

    @swagger_auto_schema(request_body=MemberCreateSerializer, responses={201: MemberSerializer})
    @transaction.atomic
    def post(self, request):
        user = request.user
        head_member = _head_member(user)
        if not head_member:
            return _fail("Unauthorized", status.HTTP_403_FORBIDDEN)

        # Ensure the head's family exists (exactly one family per head)
        family = head_member.family
        if family is None:
            family, _ = Family.objects.get_or_create(head=user)
            head_member.family = family
            head_member.save(update_fields=["family"])

        serializer = MemberCreateSerializer(
            data=request.data, context={"request": request, "family": family}
        )
        serializer.is_valid(raise_exception=True)

        spouse_id = serializer.validated_data.get("spouse_id")
        if spouse_id == head_member.id:
            return _fail("Cannot select yourself as spouse")

        mobile = serializer.validated_data.get("mobile")
        if mobile:
            if Member.objects.filter(mobile=mobile).exclude(family=family).exists():
                return _fail("This mobile is already registered under another family.",
                             status.HTTP_409_CONFLICT)

        if not mobile:
            serializer.validated_data["mobile"] = head_member.mobile

        if Member.objects.filter(family=family, mobile=serializer.validated_data.get("mobile")).exists():
            return _fail("This mobile is already used in your family.", status.HTTP_409_CONFLICT)

        # Members added by a head are reviewed by an admin (unless auto-approve is on).
        # A head can NEVER create another head.
        new_status = (
            MemberStatus.ACTIVE
            if getattr(settings, "HEAD_ADDED_MEMBERS_AUTO_APPROVE", False)
            else MemberStatus.PENDING
        )
        try:
            member = serializer.save(
                family=family,
                community=head_member.community or Community.SUTHAR,
                status=new_status,
                role=MemberRole.MEMBER,
            )
        except IntegrityError:
            return _fail("Member with this mobile already exists in the family.",
                         status.HTTP_409_CONFLICT)

        audit(user, "member_added_by_head", "member", member.id, family=family.id)
        return Response(
            {"success": True, "member": MemberSerializer(member, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# FAMILY HEAD → UPDATE MEMBER
# ============================================================
class FamilyHeadUpdateMember(APIView):
    permission_classes = [IsAuthenticated, IsFamilyHead]

    @swagger_auto_schema(request_body=MemberProfileUpdateSerializer, responses={200: MemberSerializer})
    @transaction.atomic
    def put(self, request, member_id):
        user = request.user
        head_member = _head_member(user)
        if not head_member or not head_member.family_id:
            return _fail("Unauthorized", status.HTTP_403_FORBIDDEN)

        member = get_object_or_404(Member, id=member_id, family=head_member.family)

        spouse_id = request.data.get("spouse_id")
        if spouse_id and str(spouse_id) == str(member.id):
            return _fail("Cannot select yourself as spouse")

        new_mobile = request.data.get("mobile")
        if new_mobile and Member.objects.filter(mobile=new_mobile).exclude(id=member.id).exists():
            return _fail("This mobile number is already used by another member.",
                         status.HTTP_409_CONFLICT)

        serializer = MemberProfileUpdateSerializer(member, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Key fields of an approved member wait for admin review
        vd = serializer.validated_data
        proposed = {k: vd[k] for k in KEY_FIELDS if k in vd}
        _, queued = split_key_changes(member, proposed)
        for field in queued:
            vd.pop(field)
        serializer.save()
        if queued:
            queue_changes(member, queued, user)

        member.refresh_from_db()
        return Response(
            {
                "success": True,
                "data": MemberSerializer(member, context={"request": request}).data,
                "pending_review": sorted(queued),
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# FAMILY HEAD → REMOVE MEMBER FROM HOUSEHOLD (soft)
# ============================================================
class FamilyHeadDeleteMember(APIView):
    permission_classes = [IsAuthenticated, IsFamilyHead]

    @transaction.atomic
    def delete(self, request, member_id):
        head_member = _head_member(request.user)
        if not head_member or not head_member.family_id:
            return _fail("Unauthorized", status.HTTP_403_FORBIDDEN)

        member = get_object_or_404(Member, id=member_id, family=head_member.family)

        if member.id == head_member.id or member.role == MemberRole.FAMILY_HEAD:
            return _fail("You cannot remove the family head from the family.")

        # The person and all tree links are kept; only the household link ends.
        member.family = None
        member.save(update_fields=["family"])
        audit(request.user, "member_removed_from_household", "member", member.id,
              family=head_member.family_id)

        return Response(
            {"success": True, "message": "Family member removed from your family."},
            status=status.HTTP_200_OK,
        )


# ============================================================
# MY FAMILY MEMBERS
# ============================================================
class MyFamilyMembers(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get(self, request):
        member = get_member(request.user)
        if not member or not member.family_id:
            return Response({"success": True, "familyMembers": []})

        members = list(_members_qs().filter(family=member.family))

        # relation of every household member TO THE LOGGED-IN PERSON
        # (father, kaka, saala ...) computed once from a bounded neighbourhood.
        neighbourhood = collect_ego_tree(member, up=3, down=3, collateral=1, include_inlaws=True, include_household=True)
        relations = relations_from(KinshipGraph.from_members(neighbourhood.values()), member.id)

        return Response(
            {
                "success": True,
                "familyMembers": MemberSerializer(
                    members, many=True, context={"request": request, "relations": relations, "root_member": member}
                ).data,
            }
        )


# ============================================================
# MEMBER LIST (admin: everyone, member: approved directory)
# ============================================================
class MemberListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsActiveMember]
    serializer_class = MemberSerializer

    def get_queryset(self):
        qs = _members_qs()
        if is_app_admin(self.request.user):
            wanted = self.request.query_params.get("status")
            if wanted in MemberStatus.values:
                qs = qs.filter(status=wanted)
            return self._filtered(qs).order_by("-created_at")
        me = get_member(self.request.user)
        qs = qs.filter(status=MemberStatus.ACTIVE, community=me.community, user__isnull=False)
        return self._filtered(qs).order_by("name")

    def _filtered(self, qs):
        """Directory filters: q (name / village / occupation), village,
        occupation, gotra, blood_group."""
        p = self.request.query_params
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(native_place__icontains=q) | Q(city__icontains=q) | Q(occupation__icontains=q)
            )
        if p.get("village"):
            v = p["village"].strip()
            qs = qs.filter(Q(native_place__iexact=v) | Q(city__iexact=v))
        if p.get("occupation"):
            qs = qs.filter(occupation__icontains=p["occupation"].strip())
        if p.get("gotra"):
            qs = qs.filter(gotra__iexact=p["gotra"].strip())
        if p.get("blood_group"):
            qs = qs.filter(blood_group__iexact=p["blood_group"].strip())
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return Response(
            {
                "success": True,
                "count": qs.count(),
                "familyMembers": self.get_serializer(qs, many=True).data,
            }
        )


# ============================================================
# ADMIN → APPROVE / REJECT MEMBER
# ============================================================
class ApproveMemberView(APIView):
    permission_classes = [IsAuthenticated, IsAppAdmin]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING, enum=[MemberStatus.ACTIVE, MemberStatus.REJECTED]),
                "reason": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
    )
    @transaction.atomic
    def post(self, request, pk):
        member = get_object_or_404(Member, id=pk)
        status_value = request.data.get("status")
        reason = (request.data.get("reason") or "").strip() or None

        if status_value not in [MemberStatus.ACTIVE, MemberStatus.REJECTED]:
            return _fail("Invalid status")

        # A pending "I want to be a family head" request is decided together
        # with the membership.
        head_req = FamilyHeadRequest.objects.filter(
            member=member, kind=HeadRequestKind.NEW_HOUSEHOLD, status=ReviewStatus.PENDING
        ).first()
        if head_req and status_value == MemberStatus.ACTIVE:
            try:
                households.validate_new_household(member)
            except households.HeadRequestError as e:
                return _fail(str(e))

        member.status = status_value
        member.status_reason = reason if status_value == MemberStatus.REJECTED else None
        member.status_changed_at = timezone.now()
        member.status_changed_by = request.user
        member.save(update_fields=["status", "status_reason", "status_changed_at", "status_changed_by"])
        sync_member_to_profile_helper(member)

        if head_req:
            if status_value == MemberStatus.ACTIVE:
                households.approve_head_request(head_req, request.user)
            else:
                households.reject_head_request(head_req, request.user, reason)

        audit(request.user, f"member_{status_value}", "member", member.id, reason=reason)

        if member.user_id:  # head-added members may not have a login yet
            if status_value == MemberStatus.ACTIVE:
                message, ntype = "Your membership has been approved.", "approve"
            else:
                message = "Your membership has been rejected." + (f" Reason: {reason}" if reason else "")
                ntype = "reject"
            Notification.objects.create(
                user=member.user,
                title="Membership Update",
                message=message,
                type=ntype,
                reference_id=member.id,
                reference_type="member",
                action_date=timezone.now(),
            )

        return Response({"success": True, "message": f"Member {status_value} successfully"}, status=200)


# ============================================================
# Member Detail (Retrieve & Update)
# ============================================================
class MemberDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get_queryset(self):
        qs = _members_qs()
        if is_app_admin(self.request.user):
            return qs
        me = get_member(self.request.user)
        return qs.filter(community=me.community)

    @swagger_auto_schema(responses={200: MemberSerializer})
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response({"success": True, "familyMembers": self.get_serializer(instance).data})

    @swagger_auto_schema(request_body=MemberSerializer, responses={200: MemberSerializer})
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if is_app_admin(request.user):
            partial = kwargs.pop("partial", False)
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, "member_edited_by_admin", "member", instance.id)
            return Response({"success": True, "familyMembers": serializer.data})

        # Normal members may only edit THEIR OWN record, whitelisted fields.
        if instance.user_id != request.user.id:
            return _fail("You can only edit your own profile.", status.HTTP_403_FORBIDDEN)

        serializer = MemberSelfUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        proposed = {k: vd[k] for k in KEY_FIELDS if k in vd}
        _, queued = split_key_changes(instance, proposed)
        for field in queued:
            vd.pop(field)
        serializer.save()
        if queued:
            queue_changes(instance, queued, request.user)

        instance.refresh_from_db()
        return Response(
            {
                "success": True,
                "familyMembers": MemberSerializer(instance, context={"request": request}).data,
                "pending_review": sorted(queued),
            }
        )


# ============================================================
# FAMILY TREE  (READ ONLY - never writes to the database)
# ============================================================
class FamilyTreeView(APIView):
    """
    Hourglass tree centred on `ego` (the logged-in member, or <pk>):
    ancestors, siblings, uncles/aunts, cousins, spouse side (in-laws),
    descendants and the whole household (even members not linked yet).
    Every node carries `relation_key` / `calculated_relation` = relation to ego.
    Query params: up (3), down (3), collateral (2), inlaws (true), maternal (true)
    """
    permission_classes = [IsAuthenticated, IsActiveMember]

    @staticmethod
    def _int(request, name, default):
        try:
            return int(request.query_params.get(name, default))
        except (TypeError, ValueError):
            return default

    def get(self, request, pk=None):
        viewer = get_member(request.user)

        if pk:
            ego = get_object_or_404(_members_qs(), pk=pk)
            if not is_app_admin(request.user):
                if viewer is None or ego.community != viewer.community:
                    return _fail("Unauthorized", status.HTTP_403_FORBIDDEN)
        else:
            if viewer is None:
                return _fail("Member not found", status.HTTP_404_NOT_FOUND)
            ego = _members_qs().get(pk=viewer.pk)

        inlaws = str(request.query_params.get("inlaws", "true")).lower() != "false"
        members = collect_ego_tree(
            ego,
            up=self._int(request, "up", 3),
            down=self._int(request, "down", 3),
            collateral=self._int(request, "collateral", 2),
            include_inlaws=inlaws,
            include_maternal=str(request.query_params.get("maternal", "true")).lower() != "false",
        )

        graph = KinshipGraph.from_members(members.values())
        relations = relations_from(graph, ego.id)

        nodes = MemberSerializer(
            list(members.values()),
            many=True,
            context={"request": request, "relations": relations, "root_member": ego},
        ).data

        return Response(
            {
                "success": True,
                "ego_id": ego.id,
                "meta": {
                    "generations": generation_span(members, ego.id),
                    "people": len(members),
                    "ego_name": ego.name,
                },
                "tree": {"nodes": nodes, "edges": build_edges(members)},
            }
        )


# ============================================================
# MEMBER SEARCH (For linking existing members)
# ============================================================
class MemberSearchView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get(self, request):
        query = request.GET.get("q", "").strip()
        if not query:
            return Response({"success": True, "members": []})

        qs = _members_qs().filter(Q(mobile__icontains=query) | Q(name__icontains=query)).exclude(
            status=MemberStatus.REJECTED
        )
        if not is_app_admin(request.user):
            me = get_member(request.user)
            qs = qs.filter(community=me.community).exclude(id=me.id)

        return Response(
            {
                "success": True,
                "members": MemberSerializer(qs[:20], many=True, context={"request": request}).data,
            }
        )


# ============================================================
# RELATIONSHIP REQUESTS (tree links between two people)
# ============================================================
class RelationshipRequestView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    def get(self, request):
        member = get_member(request.user)
        if not member:
            return _fail("Member not found", status.HTTP_404_NOT_FOUND)

        requests = RelationshipRequest.objects.filter(
            receiver=member, status=RelationshipRequestStatus.PENDING
        ).select_related("sender__user__user_profile__personal", "sender__family__head")
        data = [
            {
                "id": req.id,
                "sender": MemberSerializer(req.sender, context={"request": request}).data,
                "proposed_relation": req.proposed_relation,
                "created_at": req.created_at,
            }
            for req in requests
        ]
        return Response({"success": True, "requests": data})

    def post(self, request):
        member = get_member(request.user)
        if not member:
            return _fail("Member not found", status.HTTP_404_NOT_FOUND)

        receiver_id = request.data.get("receiver_id")
        proposed_relation = request.data.get("proposed_relation")
        if not receiver_id or not proposed_relation:
            return _fail("Missing fields")
        if proposed_relation not in MemberRelation.values:
            return _fail("Invalid relation")

        receiver = get_object_or_404(Member, id=receiver_id)
        if receiver == member:
            return _fail("Cannot send request to yourself")
        if receiver.community != member.community:
            return _fail("Member belongs to another community", status.HTTP_403_FORBIDDEN)

        if RelationshipRequest.objects.filter(
            sender=member, receiver=receiver, status=RelationshipRequestStatus.PENDING
        ).exists():
            return _fail("Pending request already exists")

        req = RelationshipRequest.objects.create(
            sender=member, receiver=receiver, proposed_relation=proposed_relation
        )

        if receiver.user:
            Notification.objects.create(
                user=receiver.user,
                title="New Family Request",
                message=f"{member.name} has added you as their {proposed_relation}. Please review.",
                type="family_request",
                reference_id=req.id,
                reference_type="relationship_request",
                action_date=timezone.now(),
            )
        return Response({"success": True, "message": "Request sent"})


class RelationshipRequestRespondView(APIView):
    permission_classes = [IsAuthenticated, IsActiveMember]

    @transaction.atomic
    def post(self, request, pk):
        member = get_member(request.user)
        if not member:
            return _fail("Member not found", status.HTTP_404_NOT_FOUND)

        req = get_object_or_404(RelationshipRequest, id=pk, receiver=member)
        action = request.data.get("action")

        if req.status != RelationshipRequestStatus.PENDING:
            return _fail("Request already processed")

        if action == "accept":
            sender, relation = req.sender, req.proposed_relation
            circular = "Circular dependency detected"

            if relation == MemberRelation.FATHER:
                if check_circular_dependency(sender.id, member.id):
                    return _fail(circular)
                sender.father = member
                sender.save(update_fields=["father"])
            elif relation == MemberRelation.MOTHER:
                if check_circular_dependency(sender.id, member.id):
                    return _fail(circular)
                sender.mother = member
                sender.save(update_fields=["mother"])
            elif relation == MemberRelation.SPOUSE:
                try:
                    handle_spouse_link(sender, member.id, allow_cross_family=True)
                except Exception as e:  # ValidationError
                    return _fail(str(getattr(e, "detail", e)))
            elif relation in (MemberRelation.SON, MemberRelation.DAUGHTER):
                if check_circular_dependency(member.id, sender.id):
                    return _fail(circular)
                if sender.gender == "female":
                    member.mother = sender
                    member.save(update_fields=["mother"])
                else:
                    member.father = sender
                    member.save(update_fields=["father"])
            elif relation in (MemberRelation.BROTHER, MemberRelation.SISTER):
                # siblings share parents: copy whatever one side knows to the other
                changed = []
                for slot in ("father", "mother"):
                    mine, theirs = getattr(sender, slot), getattr(member, slot)
                    if theirs and not mine:
                        setattr(sender, slot, theirs)
                        changed.append(slot)
                    elif mine and not theirs:
                        setattr(member, slot, mine)
                        member.save(update_fields=[slot])
                if changed:
                    sender.save(update_fields=changed)
            else:
                return _fail("This relation cannot be linked automatically; ask an admin.")

            req.status = RelationshipRequestStatus.ACCEPTED
            if sender.user:
                Notification.objects.create(
                    user=sender.user,
                    title="Family Request Accepted",
                    message=f"{member.name} accepted your family request.",
                    type="family_request_accepted",
                    reference_id=req.id,
                    reference_type="relationship_request",
                    action_date=timezone.now(),
                )
            audit(request.user, "relationship_accepted", "member", sender.id, relation=relation, with_=member.id)
        elif action == "reject":
            req.status = RelationshipRequestStatus.REJECTED
        else:
            return _fail("Invalid action")

        req.save()
        return Response({"success": True, "message": f"Request {action}ed"})


# ============================================================
# ME → STATUS (called at every app start)
# ============================================================
PROFILE_FIELDS = (
    ("name", "name"), ("gender", "gender"), ("date_of_birth", "dob"), ("native_place", "native_place"),
    ("city", "city"), ("email", "email"), ("occupation", "occupation"),
    ("highest_qualification", "qualification"), ("blood_group", "blood_group"), ("address", "address"),
)


def profile_completion(member):
    """{"percent": 80, "missing": ["blood_group", ...]} over the profile fields."""
    missing = [label for field, label in PROFILE_FIELDS if not getattr(member, field)]
    percent = round(100 * (len(PROFILE_FIELDS) - len(missing)) / len(PROFILE_FIELDS))
    return {"percent": percent, "missing": missing}


class MeStatusView(APIView):
    """Any logged-in user: where am I in the approval flow?"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if is_app_admin(user):
            return Response({"success": True, "status": "active", "isAdmin": True,
                             "role": "admin", "isFamilyHead": False})

        member = get_member(user)
        if member is None:
            return Response({"success": True, "status": "incomplete", "isAdmin": False,
                             "role": None, "isFamilyHead": False})

        state = member.status
        if state == MemberStatus.PENDING and not member.profile_completed:
            state = "incomplete"

        head_req = FamilyHeadRequest.objects.filter(
            member=member, status=ReviewStatus.PENDING
        ).first()
        change = ProfileChangeRequest.objects.filter(member=member, status=ReviewStatus.PENDING).first()

        return Response(
            {
                "success": True,
                "status": state,
                "reason": member.status_reason,
                "isAdmin": False,
                "memberId": member.id,
                "role": member.role,
                "isFamilyHead": member.role == MemberRole.FAMILY_HEAD,
                "familyId": member.family_id,
                "community": member.community,
                "profileCompleted": member.profile_completed,
                "completion": profile_completion(member),
                "village": member.native_place or member.city or "",
                "hideContact": bool(member.hide_contact),
                "registeredOn": member.created_at.date().isoformat() if member.created_at else None,
                "decidedOn": member.status_changed_at.date().isoformat() if member.status_changed_at else None,
                "committeePhone": getattr(settings, "COMMITTEE_PHONE", "") or "",
                "headRequest": {"kind": head_req.kind, "status": head_req.status} if head_req else None,
                "pendingChangeFields": sorted(change.changes) if change else [],
            }
        )


class MyPrivacyView(APIView):
    """A member decides whether their phone number is hidden in the directory.
    Only this one flag can be changed here, so it needs no admin review."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = get_member(request.user)
        if member is None:
            return Response({"success": False, "message": "No member profile."}, status=404)
        return Response({"success": True, "hideContact": bool(member.hide_contact)})

    def patch(self, request):
        member = get_member(request.user)
        if member is None:
            return Response({"success": False, "message": "No member profile."}, status=404)
        value = request.data.get("hideContact", request.data.get("hide_contact"))
        if not isinstance(value, bool):
            return Response({"success": False, "message": "hideContact must be true or false."}, status=400)
        member.hide_contact = value
        member.save(update_fields=["hide_contact"])
        return Response({"success": True, "hideContact": value})

    put = patch  # the mobile network helper only has PUT


# ============================================================
# ADMIN → QUEUES
# ============================================================
def _short(m: Member):
    return {"id": m.id, "name": m.name, "mobile": m.mobile, "status": m.status,
            "family_id": m.family_id, "created_at": m.created_at}


class AdminQueueView(APIView):
    """Everything an admin has to review, in one call."""
    permission_classes = [IsAuthenticated, IsAppAdmin]

    def get(self, request):
        pending = Member.objects.filter(status=MemberStatus.PENDING)
        incomplete = pending.filter(profile_completed=False)
        ready = pending.filter(profile_completed=True)
        rejected = Member.objects.filter(status=MemberStatus.REJECTED)
        changes = ProfileChangeRequest.objects.filter(status=ReviewStatus.PENDING).select_related("member")
        heads = FamilyHeadRequest.objects.filter(status=ReviewStatus.PENDING).select_related("member")

        return Response(
            {
                "success": True,
                "counts": {
                    "newRegistrations": ready.count(),
                    "incomplete": incomplete.count(),
                    "profileChanges": changes.count(),
                    "headRequests": heads.count(),
                    "rejected": rejected.count(),
                },
                "newRegistrations": [_short(m) for m in ready[:100]],
                "incomplete": [_short(m) for m in incomplete[:100]],
                "profileChanges": [
                    {"id": c.id, "member": _short(c.member), "changes": c.changes, "created_at": c.created_at}
                    for c in changes[:100]
                ],
                "headRequests": [
                    {"id": h.id, "kind": h.kind, "member": _short(h.member), "family_id": h.family_id,
                     "note": h.note, "created_at": h.created_at}
                    for h in heads[:100]
                ],
                "rejected": [dict(_short(m), reason=m.status_reason) for m in rejected[:100]],
            }
        )


class ChangeRequestRespondView(APIView):
    permission_classes = [IsAuthenticated, IsAppAdmin]

    @transaction.atomic
    def post(self, request, pk):
        req = get_object_or_404(ProfileChangeRequest, id=pk)
        if req.status != ReviewStatus.PENDING:
            return _fail("Request already processed")
        action = request.data.get("action")
        if action == "accept":
            accept_change_request(req, request.user)
        elif action == "reject":
            reject_change_request(req, request.user, (request.data.get("reason") or "").strip() or None)
        else:
            return _fail("Invalid action")
        return Response({"success": True, "message": f"Request {action}ed"})


# ============================================================
# FAMILY HEAD REQUESTS
# ============================================================
class HeadRequestView(APIView):
    """
    GET  admin: all pending | head: own family's | member: own requests
    POST {kind:"transfer", member_id}  head -> hand headship to a family member
    POST {kind:"new_household"}        member -> ask for a separate household
    """
    permission_classes = [IsAuthenticated, IsActiveMember]

    @staticmethod
    def _row(h):
        return {"id": h.id, "kind": h.kind, "status": h.status, "member": _short(h.member),
                "family_id": h.family_id, "reason": h.reason, "created_at": h.created_at}

    def get(self, request):
        qs = FamilyHeadRequest.objects.select_related("member")
        if is_app_admin(request.user):
            qs = qs.filter(status=ReviewStatus.PENDING)
        else:
            me = get_member(request.user)
            qs = qs.filter(Q(member=me) | Q(family_id=me.family_id) if me.family_id else Q(member=me))
        return Response({"success": True, "requests": [self._row(h) for h in qs]})

    @transaction.atomic
    def post(self, request):
        me = get_member(request.user)
        if me is None:
            return _fail("Member not found", status.HTTP_404_NOT_FOUND)
        kind = request.data.get("kind")

        if kind == HeadRequestKind.TRANSFER:
            head = _head_member(request.user)
            if head is None:
                return _fail("Only the family head can transfer headship.", status.HTTP_403_FORBIDDEN)
            target = get_object_or_404(Member, id=request.data.get("member_id"), family=head.family)
            if target.id == head.id:
                return _fail("You are already the head.")
            if target.date_of_birth and (date.today() - target.date_of_birth).days < 18 * 365:
                return _fail("The new head must be an adult.")
            req = FamilyHeadRequest(kind=kind, member=target, family=head.family, requested_by=request.user,
                                    note=request.data.get("note"))
            try:
                households.validate_transfer(req)
            except households.HeadRequestError as e:
                return _fail(str(e))
            if FamilyHeadRequest.objects.filter(family=head.family, kind=kind, status=ReviewStatus.PENDING).exists():
                return _fail("A transfer request is already pending for this family.", status.HTTP_409_CONFLICT)
            req.save()
            audit(request.user, "head_request_created", "member", target.id, kind=kind)
        elif kind == HeadRequestKind.NEW_HOUSEHOLD:
            if me.role == MemberRole.FAMILY_HEAD:
                return _fail("You are already a family head.")
            try:
                households.validate_new_household(me)
            except households.HeadRequestError as e:
                return _fail(str(e))
            req, created = households.request_new_household(me, request.user, request.data.get("note"))
            if not created:
                return _fail("A request is already pending.", status.HTTP_409_CONFLICT)
        else:
            return _fail("Invalid kind")

        return Response({"success": True, "request": self._row(req)}, status=status.HTTP_201_CREATED)


class HeadRequestRespondView(APIView):
    permission_classes = [IsAuthenticated, IsAppAdmin]

    @transaction.atomic
    def post(self, request, pk):
        req = get_object_or_404(FamilyHeadRequest, id=pk)
        action = request.data.get("action")
        try:
            if action == "accept":
                households.approve_head_request(req, request.user)
            elif action == "reject":
                households.reject_head_request(req, request.user, (request.data.get("reason") or "").strip() or None)
            else:
                return _fail("Invalid action")
        except households.HeadRequestError as e:
            return _fail(str(e))
        return Response({"success": True, "message": f"Request {action}ed"})


class AdminActivityView(APIView):
    """Latest audit-log entries for the admin dashboard."""
    permission_classes = [IsAuthenticated, IsAppAdmin]

    def get(self, request):
        from .models import AuditLog

        rows = AuditLog.objects.select_related("actor").order_by("-created_at")[:15]
        data = []
        for row in rows:
            actor = row.actor
            who = (getattr(actor, "email", None) or getattr(actor, "phone", None) or "system") if actor else "system"
            data.append({
                "id": row.id,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "actor": who,
                "data": row.data,
                "created_at": row.created_at,
            })
        return Response({"success": True, "activity": data})
