from rest_framework import serializers

from .models import Image


class ImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ('image_src', 'alt_text', 'image_url')

    @staticmethod
    def get_image_url(image):
        return image.image_url
