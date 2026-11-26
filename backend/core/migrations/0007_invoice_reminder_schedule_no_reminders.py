# Generated migration for invoice reminder schedule selection

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_add_social_account'),
        ('reminders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='reminder_schedule',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='invoices',
                to='reminders.reminderschedule'
            ),
        ),
        migrations.AddField(
            model_name='invoice',
            name='no_reminders',
            field=models.BooleanField(default=False),
        ),
    ]
