from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=200)


class ApplicationDocumentationSchemaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "name": "Mind Care Hub API",
                "version": "2.0.0",
                "description": "A comprehensive mental health support platform offering personalized",
            },
            status=200,
        )
