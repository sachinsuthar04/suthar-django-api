# members/views.py

from django.utils import timezone

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from members.signals import sync_member_to_profile_helper
from notifications.models import Notification
from django.db.models import Q
from .models import Member, Family, MemberRole, MemberStatus, Community, RelationshipRequest, RelationshipRequestStatus, MemberRelation
from .serializers import (
    MemberSerializer,
    MemberCreateSerializer,
    MemberProfileUpdateSerializer,
)


# ============================================================
# FAMILY HEAD → ADD MEMBER
# ============================================================
class FamilyHeadAddMember(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=MemberCreateSerializer,
        responses={201: MemberSerializer},
    )
    @transaction.atomic
    def post(self, request):
        user = request.user

        # 1️⃣ Verify Family Head
        try:
            head_member = Member.objects.get(user=user, role=MemberRole.FAMILY_HEAD)
        except Member.DoesNotExist:
            return Response(
                {"success": False, "message": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2️⃣ Ensure Family exists
        family, _ = Family.objects.get_or_create(head=user)
        if head_member.family_id != family.id:
            head_member.family = family
            head_member.save(update_fields=["family"])

        # 3️⃣ Validate payload
        serializer = MemberCreateSerializer(
        data=request.data,
        context={
            "request": request,
            "family": family,
        }
    )
        serializer.is_valid(raise_exception=True)

        # 4️⃣ Prevent self-selection as spouse
        spouse_id = serializer.validated_data.get("spouse_id")
        if spouse_id == head_member.id:
            return Response({"success": False, "message": "Cannot select yourself as spouse"}, status=400)

        # 5️⃣ Check mobile uniqueness across other families
        mobile = serializer.validated_data.get("mobile")
        if mobile:
            duplicate = Member.objects.filter(mobile=mobile).exclude(family=family).exists()
            if duplicate:
                return Response(
                    {"success": False, "message": "This mobile is already registered under another family."},
                    status=status.HTTP_409_CONFLICT
                )

        # 6️⃣ Optionally handle empty mobile (use Family Head's number)
        if not mobile:
            serializer.validated_data["mobile"] = head_member.mobile

        # 7️⃣ Prevent duplicate mobile inside the same family
        existing_member_same_family = Member.objects.filter(
            family=family,
            mobile=serializer.validated_data.get("mobile")
        ).first()
        if existing_member_same_family:
            return Response(
                {"success": False, "message": "This mobile is already used in your family."},
                status=status.HTTP_409_CONFLICT
            )

        # 8️⃣ Create member (serializer handles spouse linking)
        try:
            member = serializer.save(
                family=family,
                community=head_member.community or Community.SUTHAR,
                status=MemberStatus.ACTIVE,
            )
        except IntegrityError:
            return Response(
                {"success": False, "message": "Member with this mobile already exists in the family."},
                status=status.HTTP_409_CONFLICT
            )

        return Response(
    {
        "success": True,
        "member": MemberSerializer(
            member,
            context={"request": request}
        ).data,
    },
    status=status.HTTP_201_CREATED,
)



# ============================================================
# FAMILY HEAD → UPDATE MEMBER
# ============================================================
class FamilyHeadUpdateMember(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=MemberProfileUpdateSerializer,
        responses={200: MemberSerializer},
    )
    @transaction.atomic
    def put(self, request, member_id):
        user = request.user

        # 1️⃣ Verify Family Head
        try:
            head_member = Member.objects.get(user=user, role=MemberRole.FAMILY_HEAD)
        except Member.DoesNotExist:
            return Response({"success": False, "message": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        # 2️⃣ Ensure Family exists
        family, _ = Family.objects.get_or_create(head=user)
        if head_member.family != family:
            head_member.family = family
            head_member.save(update_fields=["family"])

        # 3️⃣ Fetch member from same family
        member = get_object_or_404(Member, id=member_id, family=family)

        # 4️⃣ Prevent self as spouse
        spouse_id = request.data.get("spouse_id")
        if spouse_id and spouse_id == member.id:
            return Response({"success": False, "message": "Cannot select yourself as spouse"}, status=400)

        # 5️⃣ Prevent changing mobile to one used by another family member
        new_mobile = request.data.get("mobile")
        if new_mobile and Member.objects.filter(mobile=new_mobile).exclude(id=member.id).exists():
            return Response(
                {"success": False, "message": "This mobile number is already used by another member."},
                status=status.HTTP_409_CONFLICT
            )

        # 6️⃣ Update member (serializer handles spouse linking)
        serializer = MemberProfileUpdateSerializer(member, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"success": True, "data": MemberSerializer(member).data},
            status=status.HTTP_200_OK,
        )


# ============================================================
# MY FAMILY MEMBERS
# ============================================================
class MyFamilyMembers(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = Member.objects.filter(user=request.user).first()

        if not member or not member.family:
            return Response({"success": True, "familyMembers": []})

        members = Member.objects.filter(family=member.family).select_related("user")

        return Response(
        {
            "success": True,
            "familyMembers": MemberSerializer(
                members,
                many=True,
                context={"request": request}  # ✅ REQUIRED
            ).data,
        }
)



# ============================================================
# ADMIN → LIST MEMBERS
# ============================================================
class MemberListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MemberSerializer

    def get_queryset(self):
        return Member.objects.select_related("user", "family").filter(user__isnull=False)

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
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[MemberStatus.ACTIVE, MemberStatus.REJECTED],
                )
            },
        ),
    )
    def post(self, request, pk):
        member = get_object_or_404(Member, id=pk)
        status_value = request.data.get("status")

        if status_value not in [MemberStatus.ACTIVE, MemberStatus.REJECTED]:
            return Response({"success": False, "message": "Invalid status"}, status=400)

        member.status = status_value
        member.save(update_fields=["status"])

        sync_member_to_profile_helper(member)
            
        Notification.objects.create(
        user=member.user,          # 🔥 RECEIVER (approved user)
        title="Membership Update",
        message=(
            "Your membership has been approved."
            if status_value == MemberStatus.ACTIVE
            else "Your membership has been rejected."
        ),
        type="approve" if status_value == MemberStatus.ACTIVE else "reject",
        reference_id=member.id,
        reference_type="member",
        action_date=timezone.now(), )


        return Response(
            {"success": True, "message": f"Member {status_value} successfully"},
            status=200,
        )


# ============================================================
# Member Detail (Retrieve & Update)
# ============================================================
class MemberDetailView(generics.RetrieveUpdateAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(responses={200: MemberSerializer})
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "familyMembers": serializer.data})

    @swagger_auto_schema(request_body=MemberSerializer, responses={200: MemberSerializer})
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

# ============================================================
# FAMILY TREE VIEW
# ============================================================
class FamilyTreeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        member = Member.objects.filter(user=user).first()
        if not member:
            return Response({"success": False, "message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        nodes_to_return = set()
        edges = []

        def add_member(m):
            if m not in nodes_to_return:
                nodes_to_return.add(m)

        family_members = Member.objects.filter(family=member.family).select_related('father', 'mother', 'spouse')
        for fm in family_members:
            add_member(fm)
            if fm.father:
                add_member(fm.father)
                edges.append({"source": fm.father.id, "target": fm.id, "type": "father"})
            if fm.mother:
                add_member(fm.mother)
                edges.append({"source": fm.mother.id, "target": fm.id, "type": "mother"})
            if fm.spouse:
                add_member(fm.spouse)
                if fm.id < fm.spouse.id:
                    edges.append({"source": fm.id, "target": fm.spouse.id, "type": "spouse"})

        serialized_nodes = MemberSerializer(nodes_to_return, many=True, context={'request': request}).data

        return Response({
            "success": True,
            "tree": {
                "nodes": serialized_nodes,
                "edges": edges
            }
        })

# ============================================================
# MEMBER SEARCH (For linking existing members)
# ============================================================
class MemberSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return Response({"success": True, "members": []})

        members = Member.objects.filter(
            Q(mobile__icontains=query) | Q(name__icontains=query)
        ).exclude(user=request.user)[:20]

        return Response({
            "success": True,
            "members": MemberSerializer(members, many=True, context={'request': request}).data
        })

# ============================================================
# RELATIONSHIP REQUESTS
# ============================================================
class RelationshipRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return Response({"success": False, "message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        requests = RelationshipRequest.objects.filter(receiver=member, status=RelationshipRequestStatus.PENDING)
        data = []
        for req in requests:
            data.append({
                "id": req.id,
                "sender": MemberSerializer(req.sender, context={'request': request}).data,
                "proposed_relation": req.proposed_relation,
                "created_at": req.created_at
            })
        return Response({"success": True, "requests": data})

    def post(self, request):
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return Response({"success": False, "message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        receiver_id = request.data.get('receiver_id')
        proposed_relation = request.data.get('proposed_relation')

        if not receiver_id or not proposed_relation:
            return Response({"success": False, "message": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST)

        receiver = get_object_or_404(Member, id=receiver_id)

        if receiver == member:
            return Response({"success": False, "message": "Cannot send request to yourself"}, status=status.HTTP_400_BAD_REQUEST)

        if RelationshipRequest.objects.filter(sender=member, receiver=receiver, status=RelationshipRequestStatus.PENDING).exists():
            return Response({"success": False, "message": "Pending request already exists"}, status=status.HTTP_400_BAD_REQUEST)

        req = RelationshipRequest.objects.create(
            sender=member,
            receiver=receiver,
            proposed_relation=proposed_relation
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
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return Response({"success": False, "message": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        req = get_object_or_404(RelationshipRequest, id=pk, receiver=member)
        action = request.data.get('action')

        if req.status != RelationshipRequestStatus.PENDING:
            return Response({"success": False, "message": "Request already processed"}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'accept':
            req.status = RelationshipRequestStatus.ACCEPTED
            sender = req.sender
            relation = req.proposed_relation
            
            from .serializers import check_circular_dependency
            
            if relation == MemberRelation.FATHER:
                if check_circular_dependency(sender.id, member.id):
                    return Response({"success": False, "message": "Circular dependency detected"}, status=status.HTTP_400_BAD_REQUEST)
                sender.father = member
                sender.save()
            elif relation == MemberRelation.MOTHER:
                if check_circular_dependency(sender.id, member.id):
                    return Response({"success": False, "message": "Circular dependency detected"}, status=status.HTTP_400_BAD_REQUEST)
                sender.mother = member
                sender.save()
            elif relation == MemberRelation.SPOUSE:
                from .serializers import handle_spouse_link
                try:
                    handle_spouse_link(sender, member.id)
                except Exception as e:
                    return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            elif relation == MemberRelation.SON or relation == MemberRelation.DAUGHTER:
                if check_circular_dependency(member.id, sender.id):
                    return Response({"success": False, "message": "Circular dependency detected"}, status=status.HTTP_400_BAD_REQUEST)
                if sender.gender == 'female':
                    member.mother = sender
                else:
                    member.father = sender
                member.save()

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
        elif action == 'reject':
            req.status = RelationshipRequestStatus.REJECTED
        else:
            return Response({"success": False, "message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        req.save()

        return Response({"success": True, "message": f"Request {action}ed"})
