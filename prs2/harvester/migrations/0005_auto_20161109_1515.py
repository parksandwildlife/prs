# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-11-09 07:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('harvester', '0004_regionassignee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailattachment',
            name='name',
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name='emailedreferral',
            name='subject',
            field=models.CharField(max_length=512),
        ),
    ]