# Generated by Django 5.1.7 on 2025-04-10 21:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('puzzle', '0003_chatmessage_session_duration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chatmessage',
            name='session_duration',
        ),
    ]
