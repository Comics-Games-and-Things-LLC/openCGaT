# Generated by Django 4.2.2 on 2023-06-10 20:00

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('credit', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('partner', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usercredit',
            name='partner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='partner.partner'),
        ),
        migrations.AddField(
            model_name='usercredit',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='usercredit',
            constraint=models.UniqueConstraint(fields=('user', 'partner'), name='one_balance_per_user_per_partner'),
        ),
    ]
