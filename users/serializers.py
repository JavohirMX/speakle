from rest_framework import serializers
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password',
                  'bio', 'profile_picture',
                  'native_language', 'target_language',
                  'proficiency', 'interests')

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            native_language=validated_data['native_language'],
            target_language=validated_data['target_language'],
            proficiency=validated_data.get('proficiency', ''),
            interests=validated_data.get('interests', ''),
            bio=validated_data.get('bio', ''),
            profile_picture=validated_data.get('profile_picture', None)
        )
        user.set_password(validated_data['password'])  # Hash the password!
        user.save()
        return user
