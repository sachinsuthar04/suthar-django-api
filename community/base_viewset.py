# base_viewset.py
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class BaseModelViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]

    # 🔥 FIX: set created_by here
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            return Response(
                {
                    "success": True,
                    "message": "Created successfully",
                },
                status=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            message = list(e.detail.values())[0][0]
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return Response(
                {
                    "success": True,
                    "message": "Updated successfully",
                }
            )

        except ValidationError as e:
            message = list(e.detail.values())[0][0]
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)

            return Response(
                {
                    "success": True,
                    "message": "Deleted successfully",
                }
            )
        except Exception:
            return Response(
                {
                    "success": False,
                    "message": "Unable to delete",
                },
                status=status.HTTP_400_BAD_REQUEST
            )
