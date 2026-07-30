from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0015_add_fund_estimate_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="source_market_value",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="数据源仅提供金额时的持仓市值快照",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="positionoperation",
            name="source_market_value",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="数据源仅提供金额时的当前市值快照",
                max_digits=20,
                null=True,
            ),
        ),
    ]
