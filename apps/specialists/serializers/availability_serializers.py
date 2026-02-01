from rest_framework import serializers
from ..models import Availability


class AvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for specialist availability"""

    day_name = serializers.SerializerMethodField()

    class Meta:
        model = Availability
        fields = [
            "id",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "is_recurring",
            "valid_from",
            "valid_until",
        ]

    def get_day_name(self, obj):
        return obj.get_day_of_week_display()
