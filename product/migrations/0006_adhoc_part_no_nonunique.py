# Generated manually for one-time AdHoc (non-unique part_no)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0005_alter_productimage_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adhoc',
            name='part_no',
            field=models.CharField(
                help_text='Part number for this one-time quote item',
                max_length=20,
            ),
        ),
    ]
