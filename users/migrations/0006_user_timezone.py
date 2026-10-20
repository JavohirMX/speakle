from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_share_email_with_matches'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='timezone',
            field=models.CharField(blank=True, help_text='Optional. Shown to people you have a request or match with, as your local time.', max_length=64),
        ),
    ]
